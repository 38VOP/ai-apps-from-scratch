import os
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
PREVIEWS_DIR = os.path.join(DB_DIR, "previews")
os.makedirs(PREVIEWS_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "catalog.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    icon = Column(String, default="box")
    is_custom = Column(Boolean, default=False)

    models = relationship("ModelItem", back_populates="category")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    title = Column(String, nullable=False)
    username = Column(String, nullable=True)
    last_scanned_id = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    models = relationship("ModelItem", back_populates="channel", cascade="all, delete-orphan")


class ModelItem(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    telegram_message_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    
    file_formats = Column(String, default="[]")  # JSON string
    archive_types = Column(String, default="[]")  # JSON string
    render_engines = Column(String, default="[]")  # JSON string
    
    preview_path = Column(String, nullable=True)
    telegram_post_url = Column(String, nullable=False)
    post_date = Column(DateTime, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="models")
    channel = relationship("Channel", back_populates="models")

    def get_formats_list(self) -> List[str]:
        try:
            return json.loads(self.file_formats) if self.file_formats else []
        except Exception:
            return []

    def get_archives_list(self) -> List[str]:
        try:
            return json.loads(self.archive_types) if self.archive_types else []
        except Exception:
            return []

    def get_renders_list(self) -> List[str]:
        try:
            return json.loads(self.render_engines) if self.render_engines else []
        except Exception:
            return []


class TelegramConfig(Base):
    __tablename__ = "telegram_config"

    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(String, nullable=True)
    api_hash = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    is_authorized = Column(Boolean, default=False)
    session_string = Column(Text, nullable=True)


DEFAULT_CATEGORIES = [
    {"name": "Меблі", "slug": "furniture", "icon": "armchair"},
    {"name": "Освітлення", "slug": "lighting", "icon": "lamp"},
    {"name": "Декор", "slug": "decor", "icon": "flower"},
    {"name": "Рослини & Зелень", "slug": "plants", "icon": "tree"},
    {"name": "Техніка & Електроніка", "slug": "appliances", "icon": "tv"},
    {"name": "Архітектура & Екстер'єр", "slug": "architecture", "icon": "building"},
    {"name": "Текстури & Матеріали", "slug": "textures", "icon": "layers"},
    {"name": "Транспорт", "slug": "vehicles", "icon": "car"},
    {"name": "Інше", "slug": "other", "icon": "box"},
]


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed default categories if missing
        existing_count = db.query(Category).count()
        if existing_count == 0:
            for cat_data in DEFAULT_CATEGORIES:
                cat = Category(
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    icon=cat_data["icon"],
                    is_custom=False
                )
                db.add(cat)
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
