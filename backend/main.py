import os
import json
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc, func

from database import init_db, get_db, DB_DIR, PREVIEWS_DIR, Category, Channel, ModelItem, TelegramConfig
from telegram_service import telegram_manager, seed_demo_data_if_needed

app = FastAPI(title="3D Model Telegram Aggregator API", version="1.0.0")

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount preview images directory
app.mount("/previews", StaticFiles(directory=PREVIEWS_DIR), name="previews")


@app.on_event("startup")
def on_startup():
    init_db()
    # Seed a default channel if none exist
    db = next(get_db())
    if db.query(Channel).count() == 0:
        default_ch = Channel(
            telegram_id="3d_models_free",
            title="3D Models Free Catalog",
            username="3d_models_free",
            enabled=True
        )
        db.add(default_ch)
        db.commit()
        db.refresh(default_ch)
        # Seed demo models for initial quick review
        seed_demo_data_if_needed(db, default_ch)


# Pydantic Models for Schemas
class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = "box"


class CategoryUpdate(BaseModel):
    name: str
    icon: Optional[str] = None


class ChannelCreate(BaseModel):
    telegram_id_or_username: str
    title: Optional[str] = None


class ModelUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None


class TelegramConfigRequest(BaseModel):
    api_id: str
    api_hash: str
    phone_number: str


class TelegramCodeRequest(BaseModel):
    code: str


# API ENDPOINTS

@app.get("/api/models")
def get_models(
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    file_format: Optional[str] = None,
    render_engine: Optional[str] = None,
    channel_id: Optional[int] = None,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(ModelItem)

    if category_id:
        query = query.filter(ModelItem.category_id == category_id)

    if channel_id:
        query = query.filter(ModelItem.channel_id == channel_id)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                ModelItem.title.ilike(search_fmt),
                ModelItem.description.ilike(search_fmt),
                ModelItem.raw_text.ilike(search_fmt)
            )
        )

    if file_format:
        query = query.filter(ModelItem.file_formats.ilike(f"%{file_format}%"))

    if render_engine:
        query = query.filter(ModelItem.render_engines.ilike(f"%{render_engine}%"))

    total = query.count()

    if sort == "oldest":
        query = query.order_by(asc(ModelItem.id))
    elif sort == "alphabetical":
        query = query.order_by(asc(ModelItem.title))
    else:
        query = query.order_by(desc(ModelItem.id))

    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()

    result_items = []
    for item in items:
        result_items.append({
            "id": item.id,
            "telegram_message_id": item.telegram_message_id,
            "channel_id": item.channel_id,
            "channel_title": item.channel.title if item.channel else "Канал",
            "title": item.title,
            "description": item.description,
            "category_id": item.category_id,
            "category_name": item.category.name if item.category else "Інше",
            "category_slug": item.category.slug if item.category else "other",
            "file_formats": item.get_formats_list(),
            "archive_types": item.get_archives_list(),
            "render_engines": item.get_renders_list(),
            "preview_path": item.preview_path,
            "telegram_post_url": item.telegram_post_url,
            "post_date": item.post_date.isoformat() if item.post_date else None,
            "created_at": item.created_at.isoformat()
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1,
        "items": result_items
    }


@app.get("/api/models/{model_id}")
def get_model_detail(model_id: int, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    return {
        "id": item.id,
        "telegram_message_id": item.telegram_message_id,
        "channel_id": item.channel_id,
        "channel_title": item.channel.title if item.channel else "Канал",
        "title": item.title,
        "description": item.description,
        "category_id": item.category_id,
        "category_name": item.category.name if item.category else "Інше",
        "file_formats": item.get_formats_list(),
        "archive_types": item.get_archives_list(),
        "render_engines": item.get_renders_list(),
        "preview_path": item.preview_path,
        "telegram_post_url": item.telegram_post_url,
        "post_date": item.post_date.isoformat() if item.post_date else None,
        "raw_text": item.raw_text
    }


@app.patch("/api/models/{model_id}")
def update_model(model_id: int, body: ModelUpdate, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")

    if body.category_id is not None:
        cat = db.query(Category).filter(Category.id == body.category_id).first()
        if not cat:
            raise HTTPException(status_code=400, detail="Вказану категорію не знайдено")
        item.category_id = body.category_id

    if body.title is not None:
        item.title = body.title

    if body.description is not None:
        item.description = body.description

    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Модель оновлено успішно"}


@app.delete("/api/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з каталогу"}


@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    result = []
    for cat in categories:
        count = db.query(func.count(ModelItem.id)).filter(ModelItem.category_id == cat.id).scalar()
        result.append({
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "is_custom": cat.is_custom,
            "count": count or 0
        })
    return result


@app.post("/api/categories")
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    slug = body.name.lower().strip().replace(" ", "-")
    existing = db.query(Category).filter(Category.slug == slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Категорія з такою назвою вже існує")

    cat = Category(name=body.name, slug=slug, icon=body.icon or "box", is_custom=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "slug": cat.slug, "icon": cat.icon, "is_custom": cat.is_custom, "count": 0}


@app.get("/api/channels")
def get_channels(db: Session = Depends(get_db)):
    channels = db.query(Channel).all()
    res = []
    for ch in channels:
        model_count = db.query(func.count(ModelItem.id)).filter(ModelItem.channel_id == ch.id).scalar()
        res.append({
            "id": ch.id,
            "telegram_id": ch.telegram_id,
            "title": ch.title,
            "username": ch.username,
            "enabled": ch.enabled,
            "last_scanned_id": ch.last_scanned_id,
            "model_count": model_count or 0
        })
    return res


@app.post("/api/channels")
def add_channel(body: ChannelCreate, db: Session = Depends(get_db)):
    identifier = body.telegram_id_or_username.strip().replace("https://t.me/", "").replace("@", "")
    existing = db.query(Channel).filter(
        or_(Channel.telegram_id == identifier, Channel.username == identifier)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Цей канал вже додано у список")

    ch = Channel(
        telegram_id=identifier,
        username=identifier if not identifier.startswith("-") else None,
        title=body.title or f"Канал @{identifier}",
        enabled=True
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"id": ch.id, "title": ch.title, "username": ch.username}


@app.post("/api/channels/{channel_id}/sync")
async def sync_channel(channel_id: int, db: Session = Depends(get_db)):
    res = await telegram_manager.sync_channel_posts(db, channel_id)
    return res


@app.get("/api/telegram/config")
def get_telegram_config(db: Session = Depends(get_db)):
    cfg = telegram_manager.get_config(db)
    if not cfg:
        return {"api_id": "", "api_hash": "", "phone_number": "", "is_authorized": False}
    return {
        "api_id": cfg.api_id or "",
        "api_hash": cfg.api_hash or "",
        "phone_number": cfg.phone_number or "",
        "is_authorized": cfg.is_authorized
    }


@app.post("/api/telegram/config")
def save_telegram_config(body: TelegramConfigRequest, db: Session = Depends(get_db)):
    cfg = telegram_manager.save_config(db, body.api_id, body.api_hash, body.phone_number)
    return {"success": True, "message": "Налаштування Telegram збережено"}


@app.post("/api/telegram/request-code")
async def request_telegram_code(db: Session = Depends(get_db)):
    cfg = telegram_manager.get_config(db)
    if not cfg or not cfg.phone_number:
        raise HTTPException(status_code=400, detail="Спочатку вкажіть номер телефону")
    res = await telegram_manager.request_code(db, cfg.phone_number)
    return res


@app.post("/api/telegram/sign-in")
async def sign_in_telegram(body: TelegramCodeRequest, db: Session = Depends(get_db)):
    res = await telegram_manager.sign_in(db, body.code)
    return res
