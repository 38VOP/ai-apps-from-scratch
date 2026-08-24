from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Channel, ModelItem, TelegramAccount
from telegram_service import telegram_manager

router = APIRouter(tags=["sources"])


class AccountCreate(BaseModel):
    name: str
    api_id: str
    api_hash: str
    phone_number: str


class AccountCodeRequest(BaseModel):
    code: str
    phone_code_hash: Optional[str] = None


class ChannelCreate(BaseModel):
    telegram_id_or_username: str
    title: Optional[str] = None
    account_id: Optional[int] = None


class ChannelUpdate(BaseModel):
    enabled: Optional[bool] = None
    account_id: Optional[int] = None
    title: Optional[str] = None


@router.get("/api/accounts")
def get_telegram_accounts(db: Session = Depends(get_db)):
    accounts = db.query(TelegramAccount).all()
    res = []
    for acc in accounts:
        ch_count = db.query(func.count(Channel.id)).filter(Channel.account_id == acc.id).scalar()
        res.append({
            "id": acc.id,
            "name": acc.name,
            "phone_number": acc.phone_number or "",
            "api_id": acc.api_id or "",
            "api_hash": acc.api_hash or "",
            "is_authorized": acc.is_authorized,
            "channels_count": ch_count or 0,
            "created_at": acc.created_at.isoformat() if acc.created_at else None
        })
    return res


@router.post("/api/accounts")
def create_telegram_account(body: AccountCreate, db: Session = Depends(get_db)):
    acc = TelegramAccount(
        name=body.name.strip(),
        api_id=body.api_id.strip(),
        api_hash=body.api_hash.strip(),
        phone_number=body.phone_number.strip(),
        is_authorized=False
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return {"id": acc.id, "name": acc.name, "message": "Акаунт додано"}


@router.post("/api/accounts/{account_id}/request-code")
async def request_account_code(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Акаунт не знайдено")
    if not acc.phone_number:
        raise HTTPException(status_code=400, detail="Укажіть номер телефону")
    res = await telegram_manager.request_code(db, account_id, acc.phone_number)
    return res


@router.post("/api/accounts/{account_id}/sign-in")
async def sign_in_account(account_id: int, body: AccountCodeRequest, db: Session = Depends(get_db)):
    res = await telegram_manager.sign_in(db, account_id, body.code, body.phone_code_hash)
    return res


@router.get("/api/accounts/{account_id}/session-status")
async def check_session_status(account_id: int, db: Session = Depends(get_db)):
    """Повертає стан сесії: valid (працює), expired (застаріла), none (відсутня)."""
    acc = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Акаунт не знайдено")
    if not acc.session_string:
        return {"status": "none", "message": "Сесія відсутня"}
    try:
        client = await telegram_manager.get_client_for_account(db, account_id)
        if client and await client.is_user_authorized():
            return {"status": "valid", "message": "Сесія активна"}
        return {"status": "expired", "message": "Сесія застаріла"}
    except Exception:
        return {"status": "expired", "message": "Сесія застаріла"}


@router.delete("/api/accounts/{account_id}")
async def delete_telegram_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Акаунт не знайдено")

    # Канали переживають свій акаунт: моделі та історія сканування належать
    # каналу, не акаунту. Відвʼязуємо, щоб їх можна було перепризначити.
    detached = db.query(Channel).filter(Channel.account_id == account_id).update(
        {Channel.account_id: None}, synchronize_session=False
    )

    # Закриваємо зʼєднання: і робоче, і незавершену спробу авторизації —
    # інакше сокети Telethon залишаються відкритими до перезапуску процесу.
    await telegram_manager.release_account(account_id)

    name = acc.name
    db.delete(acc)
    db.commit()
    return {
        "success": True,
        "message": f"Акаунт «{name}» видалено",
        "detached_channels": detached
    }


@router.get("/api/channels")
def get_channels(db: Session = Depends(get_db)):
    channels = db.query(Channel).all()
    res = []
    for ch in channels:
        model_count = db.query(func.count(ModelItem.id)).filter(ModelItem.channel_id == ch.id).scalar()
        acc_name = ch.account.name if ch.account else "Не призначено"
        res.append({
            "id": ch.id,
            "telegram_id": ch.telegram_id,
            "title": ch.title,
            "username": ch.username,
            "account_id": ch.account_id,
            "account_name": acc_name,
            "enabled": ch.enabled,
            "initial_scan_completed": ch.initial_scan_completed or False,
            "status": ch.status or "idle",
            "status_message": ch.status_message or "",
            "last_synced_at": ch.last_synced_at.isoformat() if ch.last_synced_at else None,
            "processed_count": model_count or 0
        })
    return res


@router.post("/api/channels")
def add_channel(body: ChannelCreate, db: Session = Depends(get_db)):
    identifier = body.telegram_id_or_username.strip()
    if identifier.startswith("https://t.me/"):
        identifier = identifier.replace("https://t.me/", "")
    elif identifier.startswith("t.me/"):
        identifier = identifier.replace("t.me/", "")
    if identifier.startswith("@"):
        identifier = identifier[1:]

    existing = db.query(Channel).filter(
        (Channel.telegram_id == identifier) | (Channel.username == identifier)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Канал вже додано")

    ch = Channel(
        telegram_id=identifier,
        username=identifier if not identifier.startswith("-100") and not identifier.isdigit() else None,
        title=body.title.strip() if body.title else identifier,
        account_id=body.account_id,
        enabled=True,
        status="idle",
        status_message="Очікує синхронізації"
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"id": ch.id, "title": ch.title, "message": "Канал додано до черги"}


@router.patch("/api/channels/{channel_id}")
def update_channel(channel_id: int, body: ChannelUpdate, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не знайдено")
    if body.enabled is not None:
        ch.enabled = body.enabled
        if not body.enabled:
            ch.status = "disabled"
            ch.status_message = "Моніторинг вимкнено"
    if body.account_id is not None:
        ch.account_id = body.account_id
    if body.title is not None:
        ch.title = body.title
    db.commit()
    return {"success": True, "message": "Оновлено налаштування каналу"}


@router.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не знайдено")
    db.delete(ch)
    db.commit()
    return {"success": True, "message": "Канал видалено з моніторингу"}


@router.post("/api/channels/{channel_id}/sync")
async def sync_channel(channel_id: int, db: Session = Depends(get_db)):
    res = await telegram_manager.queue_channel(db, channel_id)
    return res
