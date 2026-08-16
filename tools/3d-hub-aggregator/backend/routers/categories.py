from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, asc

from database import get_db, Category, ModelItem

router = APIRouter(tags=["categories"])


class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = "box"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    is_visible: Optional[bool] = None


class CategoryReorderRequest(BaseModel):
    category_ids: List[int]


class CategoryStatusUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_visible: Optional[bool] = None
    is_marked_for_deletion: Optional[bool] = None


@router.get("/api/categories")
def get_categories(visible_only: bool = Query(False), db: Session = Depends(get_db)):
    query = db.query(Category)
    if visible_only:
        query = query.filter(Category.is_visible == True)
    categories = query.order_by(asc(Category.sort_order), asc(Category.id)).all()
    result = []
    for cat in categories:
        count = db.query(func.count(ModelItem.id)).filter(ModelItem.category_id == cat.id).scalar()
        result.append({
            "id": cat.id, "name": cat.name, "slug": cat.slug, "icon": cat.icon,
            "sort_order": cat.sort_order, "is_visible": cat.is_visible,
            "is_custom": cat.is_custom, "count": count or 0
        })
    return result


@router.post("/api/categories")
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    slug = body.name.lower().strip().replace(" ", "-")
    existing = db.query(Category).filter(Category.slug == slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Категорія з такою назвою вже існує")
    max_order = db.query(func.max(Category.sort_order)).scalar() or 0
    cat = Category(name=body.name.strip(), slug=slug, icon=body.icon or "box",
                   sort_order=max_order + 1, is_visible=True, is_custom=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "slug": cat.slug, "icon": cat.icon, "is_visible": True, "count": 0}


@router.patch("/api/categories/{category_id}")
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


@router.put("/api/categories/reorder")
def reorder_categories(body: CategoryReorderRequest, db: Session = Depends(get_db)):
    for idx, cat_id in enumerate(body.category_ids):
        cat = db.query(Category).filter(Category.id == cat_id).first()
        if cat:
            cat.sort_order = idx + 1
    db.commit()
    return {"success": True, "message": "Порядок категорій збережено"}


@router.patch("/api/categories/{category_id}/status")
def update_category_status(category_id: int, body: CategoryStatusUpdate, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")
    if body.is_active is not None:
        cat.is_active = body.is_active
    if body.is_visible is not None:
        cat.is_visible = body.is_visible
    if body.is_marked_for_deletion is not None:
        cat.is_marked_for_deletion = body.is_marked_for_deletion
    db.commit()
    return {"success": True, "message": "Статус категорії оновлено"}


@router.post("/api/categories/apply")
def apply_category_changes(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    blocked_cats = []
    deleted_count = 0
    for cat in categories:
        if cat.is_marked_for_deletion:
            model_count = db.query(ModelItem).filter(ModelItem.category_id == cat.id).count()
            if model_count > 0:
                blocked_cats.append({"id": cat.id, "name": cat.name, "model_count": model_count})
            else:
                db.delete(cat)
                deleted_count += 1
    db.commit()
    if blocked_cats:
        return {"success": False, "message": "Деякі категорії містять моделі і не можуть бути видалені", "blocked_categories": blocked_cats}
    return {"success": True, "message": f"Зміни застосовано. Видалено {deleted_count} порожніх категорій"}
