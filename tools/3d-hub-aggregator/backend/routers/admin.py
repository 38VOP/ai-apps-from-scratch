from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, Category, Channel, ModelItem, Project, CartItem

router = APIRouter(tags=["admin"])


@router.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_models = db.query(ModelItem).count()
    total_channels = db.query(Channel).count()
    active_channels = db.query(Channel).filter(Channel.enabled == True).count()
    total_categories = db.query(Category).count()
    active_categories = db.query(Category).filter(Category.is_active == True).count()
    total_projects = db.query(Project).count()
    cart_count = db.query(CartItem).count()
    channel_stats = [{
        "id": ch.id, "title": ch.title, "status": ch.status or "idle",
        "scan_mode": ch.scan_mode or "idle", "processed_count": ch.processed_count or 0,
        "total_posts": ch.total_posts or 0, "enabled": ch.enabled
    } for ch in db.query(Channel).all()]
    return {
        "total_models": total_models, "total_channels": total_channels,
        "active_channels": active_channels, "total_categories": total_categories,
        "active_categories": active_categories, "total_projects": total_projects,
        "cart_count": cart_count, "channel_stats": channel_stats
    }
