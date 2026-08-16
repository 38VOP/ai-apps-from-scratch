from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, CartItem, ModelItem, Project, ProjectItem

router = APIRouter(tags=["cart"])


class SaveToProject(BaseModel):
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    model_ids: List[int]


@router.get("/api/cart")
def get_cart(db: Session = Depends(get_db)):
    items = db.query(CartItem).all()
    result = []
    for item in items:
        model = item.model
        if model:
            result.append({
                "id": item.id, "model_id": model.id, "title": model.title,
                "preview_path": model.preview_path,
                "category_name": model.category.name if model.category else "Інше",
                "telegram_post_url": model.telegram_post_url,
                "created_at": item.created_at.isoformat() if item.created_at else None
            })
    return {"items": result, "count": len(result)}


@router.post("/api/cart")
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


@router.delete("/api/cart/{cart_item_id}")
def remove_from_cart(cart_item_id: int, db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(CartItem.id == cart_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Елемент кошика не знайдено")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з кошика"}


@router.delete("/api/cart")
def clear_cart(db: Session = Depends(get_db)):
    db.query(CartItem).delete()
    db.commit()
    return {"success": True, "message": "Кошик очищено"}


@router.post("/api/cart/save-to-project")
def save_to_project(body: SaveToProject, db: Session = Depends(get_db)):
    if not body.model_ids:
        raise HTTPException(status_code=400, detail="Оберіть моделі для збереження")
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
    added_count = 0
    for model_id in body.model_ids:
        model = db.query(ModelItem).filter(ModelItem.id == model_id).first()
        if not model:
            continue
        existing = db.query(ProjectItem).filter(ProjectItem.project_id == project.id, ProjectItem.model_id == model_id).first()
        if existing:
            continue
        db.add(ProjectItem(project_id=project.id, model_id=model_id))
        added_count += 1
    db.query(CartItem).filter(CartItem.model_id.in_(body.model_ids)).delete(synchronize_session='fetch')
    db.commit()
    return {"success": True, "message": f"Додано {added_count} моделей у проект «{project.name}»", "project_id": project.id}
