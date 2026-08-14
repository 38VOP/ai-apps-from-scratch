import os
import json
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc, func

from database import init_db, get_db, DB_DIR, PREVIEWS_DIR, Category, Channel, ModelItem, TelegramAccount, CartItem, Project, ProjectItem
from telegram_service import telegram_manager, seed_demo_data_if_needed

app = FastAPI(title="3D Model Telegram Aggregator API v1.2.0", version="1.2.0")

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
    db = next(get_db())
    # Seed default main channel if none exist
    if db.query(Channel).count() == 0:
        main_acc = db.query(TelegramAccount).first()
        default_ch = Channel(
            telegram_id="3d_models_free",
            title="3D Models Free Catalog",
            username="3d_models_free",
            account_id=main_acc.id if main_acc else None,
            enabled=True,
            status="active",
            status_message="Активний"
        )
        db.add(default_ch)
        db.commit()
        db.refresh(default_ch)
        seed_demo_data_if_needed(db, default_ch)
        default_ch.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == default_ch.id).count()
        db.commit()


# Pydantic Schemas
class AccountCreate(BaseModel):
    name: str
    api_id: str
    api_hash: str
    phone_number: str


class AccountCodeRequest(BaseModel):
    code: str


class ChannelCreate(BaseModel):
    telegram_id_or_username: str
    title: Optional[str] = None
    account_id: Optional[int] = None


class ChannelUpdate(BaseModel):
    enabled: Optional[bool] = None
    account_id: Optional[int] = None
    title: Optional[str] = None


class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = "box"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    is_visible: Optional[bool] = None


class CategoryReorderRequest(BaseModel):
    category_ids: List[int]


class ModelUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None


class CategoryStatusUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_visible: Optional[bool] = None


class ProjectCreate(BaseModel):
    name: str


class ProjectRename(BaseModel):
    name: str


class SaveToProject(BaseModel):
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    model_ids: List[int]


# --- TELEGRAM ACCOUNTS ENDPOINTS ---

@app.get("/api/accounts")
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


@app.post("/api/accounts")
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


@app.post("/api/accounts/{account_id}/request-code")
async def request_account_code(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Акаунт не знайдено")
    if not acc.phone_number:
        raise HTTPException(status_code=400, detail="Укажіть номер телефону")
    res = await telegram_manager.request_code(db, account_id, acc.phone_number)
    return res


@app.post("/api/accounts/{account_id}/sign-in")
async def sign_in_account(account_id: int, body: AccountCodeRequest, db: Session = Depends(get_db)):
    res = await telegram_manager.sign_in(db, account_id, body.code)
    return res


@app.delete("/api/accounts/{account_id}")
def delete_telegram_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Акаунт не знайдено")
    db.delete(acc)
    db.commit()
    return {"success": True, "message": "Акаунт видалено"}


# --- TELEGRAM CHANNELS ENDPOINTS ---

@app.get("/api/channels")
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
        account_id=body.account_id,
        enabled=True,
        status="idle",
        status_message="Очікує моніторингу"
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"id": ch.id, "title": ch.title, "username": ch.username}


@app.patch("/api/channels/{channel_id}")
def update_channel(channel_id: int, body: ChannelUpdate, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не знайдено")

    if body.enabled is not None:
        ch.enabled = body.enabled
        ch.status = "idle" if body.enabled else "disabled"
        ch.status_message = "Моніторинг увімкнено" if body.enabled else "Моніторинг вимкнено"

    if body.account_id is not None:
        ch.account_id = body.account_id

    if body.title is not None:
        ch.title = body.title

    db.commit()
    return {"success": True, "message": "Оновлено налаштування каналу"}


@app.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не знайдено")
    db.delete(ch)
    db.commit()
    return {"success": True, "message": "Канал видалено з моніторингу"}


@app.post("/api/channels/{channel_id}/sync")
async def sync_channel(channel_id: int, db: Session = Depends(get_db)):
    res = await telegram_manager.queue_channel(db, channel_id)
    return res


# --- CATEGORIES ENDPOINTS (USER CUSTOMIZABLE) ---

@app.get("/api/categories")
def get_categories(visible_only: bool = Query(False), db: Session = Depends(get_db)):
    query = db.query(Category)
    if visible_only:
        query = query.filter(Category.is_visible == True)
    
    categories = query.order_by(asc(Category.sort_order), asc(Category.id)).all()
    result = []
    for cat in categories:
        count = db.query(func.count(ModelItem.id)).filter(ModelItem.category_id == cat.id).scalar()
        result.append({
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "sort_order": cat.sort_order,
            "is_visible": cat.is_visible,
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

    max_order = db.query(func.max(Category.sort_order)).scalar() or 0

    cat = Category(
        name=body.name.strip(),
        slug=slug,
        icon=body.icon or "box",
        sort_order=max_order + 1,
        is_visible=True,
        is_custom=True
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "slug": cat.slug, "icon": cat.icon, "is_visible": True, "count": 0}


@app.patch("/api/categories/{category_id}")
def update_category(category_id: int, body: CategoryUpdate, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")

    if body.name is not None:
        cat.name = body.name.strip()
    if body.icon is not None:
        cat.icon = body.icon
    if body.is_visible is not None:
        cat.is_visible = body.is_visible

    db.commit()
    return {"success": True, "message": "Категорію оновлено"}


@app.put("/api/categories/reorder")
def reorder_categories(body: CategoryReorderRequest, db: Session = Depends(get_db)):
    for idx, cat_id in enumerate(body.category_ids):
        cat = db.query(Category).filter(Category.id == cat_id).first()
        if cat:
            cat.sort_order = idx + 1
    db.commit()
    return {"success": True, "message": "Порядок категорій збережено"}


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")

    # Move models in this category to 'other' category
    other_cat = db.query(Category).filter(Category.slug == "other").first()
    if other_cat and other_cat.id != cat.id:
        db.query(ModelItem).filter(ModelItem.category_id == cat.id).update({"category_id": other_cat.id})

    db.delete(cat)
    db.commit()
    return {"success": True, "message": "Категорію видалено"}


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
        "id": item.id,
        "telegram_message_id": item.telegram_message_id,
        "channel_id": item.channel_id,
        "channel_title": item.channel.title if item.channel else "Канал",
        "title": item.title,
        "description": item.description,
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


# --- CATALOG MODELS ENDPOINTS ---

@app.get("/api/models")
def get_models(
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(ModelItem)

    # Filter to only show models in user-visible categories if category_id not explicitly set
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
        query = query.filter(
            or_(
                ModelItem.title.ilike(search_fmt),
                ModelItem.description.ilike(search_fmt),
                ModelItem.raw_text.ilike(search_fmt)
            )
        )

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
        result_items.append(serialize_model(item))

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
    detail = serialize_model(item)
    detail["raw_text"] = item.raw_text
    return detail


@app.patch("/api/models/{model_id}")
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


@app.delete("/api/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    item = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з каталогу"}


# --- CART ENDPOINTS (MOD-CART) ---

@app.get("/api/cart")
def get_cart(db: Session = Depends(get_db)):
    items = db.query(CartItem).all()
    result = []
    for item in items:
        model = item.model
        if model:
            result.append({
                "id": item.id,
                "model_id": model.id,
                "title": model.title,
                "preview_path": model.preview_path,
                "category_name": model.category.name if model.category else "Інше",
                "telegram_post_url": model.telegram_post_url,
                "created_at": item.created_at.isoformat() if item.created_at else None
            })
    return {"items": result, "count": len(result)}


@app.post("/api/cart")
def add_to_cart(body: dict, db: Session = Depends(get_db)):
    model_id = body.get("model_id")
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id обов'язковий")
    
    model = db.query(ModelItem).filter(ModelItem.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не знайдено")
    
    existing = db.query(CartItem).filter(CartItem.model_id == model_id).first()
    if existing:
        return {"success": True, "message": "Модель вже у кошику", "cart_item_id": existing.id}
    
    cart_item = CartItem(model_id=model_id)
    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)
    return {"success": True, "message": "Модель додано до кошика", "cart_item_id": cart_item.id}


@app.delete("/api/cart/{cart_item_id}")
def remove_from_cart(cart_item_id: int, db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(CartItem.id == cart_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Елемент кошика не знайдено")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з кошика"}


@app.delete("/api/cart")
def clear_cart(db: Session = Depends(get_db)):
    db.query(CartItem).delete()
    db.commit()
    return {"success": True, "message": "Кошик очищено"}


@app.post("/api/cart/save-to-project")
def save_to_project(body: SaveToProject, db: Session = Depends(get_db)):
    if not body.model_ids:
        raise HTTPException(status_code=400, detail="Оберіть моделі для збереження")
    
    # Get or create project
    project = None
    if body.project_id:
        project = db.query(Project).filter(Project.id == body.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не знайдено")
    elif body.project_name:
        project = Project(name=body.project_name.strip())
        db.add(project)
        db.commit()
        db.refresh(project)
    else:
        raise HTTPException(status_code=400, detail="Вкажіть project_id або project_name")
    
    # Add models to project
    added_count = 0
    for model_id in body.model_ids:
        model = db.query(ModelItem).filter(ModelItem.id == model_id).first()
        if not model:
            continue
        
        existing = db.query(ProjectItem).filter(
            ProjectItem.project_id == project.id,
            ProjectItem.model_id == model_id
        ).first()
        if existing:
            continue
        
        project_item = ProjectItem(project_id=project.id, model_id=model_id)
        db.add(project_item)
        added_count += 1
    
    # Remove from cart
    db.query(CartItem).filter(CartItem.model_id.in_(body.model_ids)).delete(synchronize_session='fetch')
    db.commit()
    
    return {
        "success": True, 
        "message": f"Додано {added_count} моделей у проект «{project.name}»",
        "project_id": project.id
    }


# --- PROJECTS ENDPOINTS (MOD-PROJECTS) ---

@app.get("/api/projects")
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    result = []
    for proj in projects:
        item_count = db.query(ProjectItem).filter(ProjectItem.project_id == proj.id).count()
        result.append({
            "id": proj.id,
            "name": proj.name,
            "item_count": item_count,
            "created_at": proj.created_at.isoformat() if proj.created_at else None
        })
    return result


@app.get("/api/projects/{project_id}")
def get_project_detail(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не знайдено")
    
    items = db.query(ProjectItem).filter(ProjectItem.project_id == project_id).all()
    models = []
    for item in items:
        model = item.model
        if model:
            models.append(serialize_model(model))
    
    return {
        "id": project.id,
        "name": project.name,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "models": models
    }


@app.post("/api/projects")
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=body.name.strip())
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "message": "Проект створено"}


@app.patch("/api/projects/{project_id}")
def rename_project(project_id: int, body: ProjectRename, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не знайдено")
    project.name = body.name.strip()
    db.commit()
    return {"success": True, "message": "Проект перейменовано"}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не знайдено")
    db.delete(project)
    db.commit()
    return {"success": True, "message": "Проект видалено"}


@app.delete("/api/projects/{project_id}/models/{model_id}")
def remove_model_from_project(project_id: int, model_id: int, db: Session = Depends(get_db)):
    item = db.query(ProjectItem).filter(
        ProjectItem.project_id == project_id,
        ProjectItem.model_id == model_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено у проекті")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з проекту"}


# --- ENHANCED CATEGORY ENDPOINTS (MOD-CATEGORIZE) ---

@app.patch("/api/categories/{category_id}/status")
def update_category_status(category_id: int, body: CategoryStatusUpdate, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")
    
    if body.is_active is not None:
        cat.is_active = body.is_active
    if body.is_visible is not None:
        cat.is_visible = body.is_visible
    
    db.commit()
    return {"success": True, "message": "Статус категорії оновлено"}


@app.post("/api/categories/apply")
def apply_category_changes(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    inactive_cats = []
    deleted_count = 0
    
    for cat in categories:
        if not cat.is_active:
            model_count = db.query(ModelItem).filter(ModelItem.category_id == cat.id).count()
            if model_count > 0:
                inactive_cats.append({"id": cat.id, "name": cat.name, "model_count": model_count})
            else:
                db.delete(cat)
                deleted_count += 1
    
    db.commit()
    
    if inactive_cats:
        return {
            "success": False,
            "message": "Деякі категорії містять моделі і не можуть бути видалені",
            "blocked_categories": inactive_cats
        }
    
    return {"success": True, "message": f"Зміни застосовано. Видалено {deleted_count} порожніх категорій"}


@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_models = db.query(ModelItem).count()
    total_channels = db.query(Channel).count()
    active_channels = db.query(Channel).filter(Channel.enabled == True).count()
    total_categories = db.query(Category).count()
    active_categories = db.query(Category).filter(Category.is_active == True).count()
    total_projects = db.query(Project).count()
    cart_count = db.query(CartItem).count()
    
    channels = db.query(Channel).all()
    channel_stats = []
    for ch in channels:
        channel_stats.append({
            "id": ch.id,
            "title": ch.title,
            "status": ch.status or "idle",
            "scan_mode": ch.scan_mode or "idle",
            "processed_count": ch.processed_count or 0,
            "total_posts": ch.total_posts or 0,
            "enabled": ch.enabled
        })
    
    return {
        "total_models": total_models,
        "total_channels": total_channels,
        "active_channels": active_channels,
        "total_categories": total_categories,
        "active_categories": active_categories,
        "total_projects": total_projects,
        "cart_count": cart_count,
        "channel_stats": channel_stats
    }
