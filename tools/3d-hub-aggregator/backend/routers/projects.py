from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Project, ProjectItem
from routers.models import serialize_model

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    name: str


class ProjectRename(BaseModel):
    name: str


@router.get("/api/projects")
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    result = []
    for proj in projects:
        item_count = db.query(ProjectItem).filter(ProjectItem.project_id == proj.id).count()
        result.append({"id": proj.id, "name": proj.name, "item_count": item_count,
                       "created_at": proj.created_at.isoformat() if proj.created_at else None})
    return result


@router.get("/api/projects/{project_id}")
def get_project_detail(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не знайдено")
    items = db.query(ProjectItem).filter(ProjectItem.project_id == project_id).all()
    models = [serialize_model(item.model) for item in items if item.model]
    return {"id": project.id, "name": project.name,
            "created_at": project.created_at.isoformat() if project.created_at else None, "models": models}


@router.post("/api/projects")
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=body.name.strip())
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "message": "Проект створено"}


@router.patch("/api/projects/{project_id}")
def rename_project(project_id: int, body: ProjectRename, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не знайдено")
    project.name = body.name.strip()
    db.commit()
    return {"success": True, "message": "Проект перейменовано"}


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не знайдено")
    db.delete(project)
    db.commit()
    return {"success": True, "message": "Проект видалено"}


@router.delete("/api/projects/{project_id}/models/{model_id}")
def remove_model_from_project(project_id: int, model_id: int, db: Session = Depends(get_db)):
    item = db.query(ProjectItem).filter(ProjectItem.project_id == project_id, ProjectItem.model_id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Модель не знайдено у проекті")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Модель видалено з проекту"}
