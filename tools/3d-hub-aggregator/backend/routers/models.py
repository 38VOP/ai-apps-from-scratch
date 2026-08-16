import os
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from database import get_db, PREVIEWS_DIR, Category, Channel, ModelItem
from telegram_service import telegram_manager

router = APIRouter(tags=["models"])


class ModelUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None


def serialize_model(item: ModelItem) -> dict:
    def parse_list(raw):
        if not raw:
            return []
        try:
            val = json.loads(raw)
            return val if isinstance(val, list) else [val]
        except (ValueError, TypeError):
            return [raw]
    return {
        "id": item.id, "telegram_message_id": item.telegram_message_id,
        "channel_id": item.channel_id,
        "channel_title": item.channel.title if item.channel else "Канал",
        "title": item.title, "description": item.description,
        "category_id": item.category_id,
        "category_name": item.category.name if item.category else "Інше",
        "preview_path": item.preview_path,
        "telegram_post_url": item.telegram_post_url,
        "post_date": item.post_date.isoformat() if item.post_date else None,
        "file_formats": parse_list(item.file_formats),
        "archive_types": parse_list(item.archive_types),
        "render_engines": parse_list(item.render_engines),
        "created_at": item.created_at.isoformat()
    }


@router.get("/api/models")
def get_models(
    search: Optional[str] = None, category_id: Optional[int] = None,
    channel_id: Optional[int] = None, sort: str = "newest",
    page: int = Query(1, ge=1), limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(ModelItem)
    if category_id:
        query = query.filter(ModelItem.category_id == category_id)
    else:
        visible_cat_ids = [c.id for c in db.query(Category.id).filter(Category.is_visible == True).all()]
        if visible_cat_ids:
            query = query.filter(ModelItem.category_id.in_(visible_cat_ids))
    if channel_id:
        query = query.filter(ModelItem.channel_id == channel_id)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(or_(ModelItem.title.ilike(search_fmt), ModelItem.description.ilike(search_fmt), ModelItem.raw_text.ilike(search_fmt)))
    total = query.count()
    if sort == "oldest":
        query = query.order_by(asc(ModelItem.id))
    elif sort == "alphabetical":
        query = query.order_by(asc(ModelItem.title))
    else:
        query = query.order_by(desc(ModelItem.id))
    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()
    return {"total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit if limit > 0 else 1, "items": [serialize_model(i) for i in items]}


@router.get("/api/models/{model_id}")
def get_model_detail(model_id: int, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    detail = serialize_model(item)
    detail["raw_text"] = item.raw_text
    return detail


@router.patch("/api/models/{model_id}")
def update_model(model_id: int, body: ModelUpdate, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    if body.category_id is not None:
        cat = db.query(Category).filter(Category.id == body.category_id).first()
        if not cat:
            raise HTTPException(status_code=400, detail="Категорію не знайдено")
        item.category_id = body.category_id
    if body.title is not None:
        item.title = body.title
    if body.description is not None:
        item.description = body.description
    db.commit()
    return {"success": True, "message": "Модель оновлено успішно"}


@router.delete("/api/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з каталогу"}


@router.post("/api/models/{model_id}/refresh-preview")
async def refresh_model_preview(model_id: int, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    channel = db.query(Channel).filter(Channel.id == item.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Канал не знайдено")
    client = await telegram_manager.get_client_for_account(db, channel.account_id) if channel.account_id else None
    if not client or not await client.is_user_authorized():
        return {"success": False, "message": "Telegram клієнт недоступний. Авторизуйте акаунт."}
    try:
        entity = await client.get_entity(channel.username or channel.telegram_id)
        msg = await client.get_messages(entity, ids=item.telegram_message_id)
        if not msg or not msg.photo:
            return {"success": False, "message": "Пост не містить фото"}
        filename = f"preview_{channel.id}_{item.telegram_message_id}.jpg"
        full_path = os.path.join(PREVIEWS_DIR, filename)
        await client.download_media(msg.photo, file=full_path)
        item.preview_path = f"/previews/{filename}"
        db.commit()
        return {"success": True, "message": "Прев'ю оновлено", "preview_path": item.preview_path}
    except Exception as e:
        return {"success": False, "message": f"Помилка оновлення прев'ю: {str(e)}"}
