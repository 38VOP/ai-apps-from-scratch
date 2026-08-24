import os
import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, event
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


# SQLite ігнорує FOREIGN KEY, поки їх не увімкнути на КОЖНОМУ зʼєднанні.
# Без цього БД не заперечує проти записів, що вказують у нікуди, і цілісність
# тримається лише на дисципліні прикладного коду — тобто не тримається.
@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, default="Основний акаунт")
    api_id = Column(String, nullable=True)
    api_hash = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    is_authorized = Column(Boolean, default=False)
    session_string = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    channels = relationship("Channel", back_populates="account")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    icon = Column(String, default="box")
    sort_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    is_marked_for_deletion = Column(Boolean, default=False)
    is_custom = Column(Boolean, default=False)

    models = relationship("ModelItem", back_populates="category")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    title = Column(String, nullable=False)
    username = Column(String, nullable=True)
    account_id = Column(Integer, ForeignKey("telegram_accounts.id"), nullable=True)
    
    enabled = Column(Boolean, default=True)
    initial_scan_completed = Column(Boolean, default=False)
    status = Column(String, default="idle")  # 'idle', 'queued', 'backlog', 'monitoring', 'error', 'disabled'
    status_message = Column(String, nullable=True)
    scan_mode = Column(String, default="idle")  # 'idle', 'backlog', 'monitoring'
    
    last_scanned_id = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    processed_count = Column(Integer, default=0)
    total_posts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("TelegramAccount", back_populates="channels")
    models = relationship("ModelItem", back_populates="channel", cascade="all, delete-orphan")


class ModelItem(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    telegram_message_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    
    preview_path = Column(String, nullable=True)
    telegram_post_url = Column(String, nullable=False)
    post_date = Column(DateTime, nullable=True)
    raw_text = Column(Text, nullable=True)
    file_formats = Column(Text, nullable=True)     # JSON list, e.g. ["3ds Max","FBX"]
    archive_types = Column(Text, nullable=True)   # JSON list, e.g. ["ZIP"]
    render_engines = Column(Text, nullable=True)  # JSON list, e.g. ["V-Ray","Corona"]
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="models")
    channel = relationship("Channel", back_populates="models")

    # Видалення моделі мусить прибирати її з кошика і з усіх проектів.
    # Без цих каскадів залишаються записи, що вказують на неіснуючу модель.
    cart_entries = relationship("CartItem", back_populates="model", cascade="all, delete-orphan")
    project_entries = relationship("ProjectItem", back_populates="model", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    model = relationship("ModelItem", back_populates="cart_entries")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("ProjectItem", back_populates="project", cascade="all, delete-orphan")


class ProjectItem(Base):
    __tablename__ = "project_items"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="items")
    model = relationship("ModelItem", back_populates="project_entries")


class TelegramConfig(Base):
    __tablename__ = "telegram_config"

    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(String, nullable=True)
    api_hash = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    is_authorized = Column(Boolean, default=False)
    session_string = Column(Text, nullable=True)


DEFAULT_USER_CATEGORIES = [
    {"name": "Меблі", "slug": "furniture", "icon": "armchair", "sort_order": 1, "is_visible": True},
    {"name": "Освітлення", "slug": "lighting", "icon": "lamp", "sort_order": 2, "is_visible": True},
    {"name": "Декор", "slug": "decor", "icon": "flower", "sort_order": 3, "is_visible": True},
    {"name": "Рослини & Зелень", "slug": "plants", "icon": "tree", "sort_order": 4, "is_visible": True},
    {"name": "Техніка & Електроніка", "slug": "appliances", "icon": "tv", "sort_order": 5, "is_visible": True},
    {"name": "Архітектура & Екстер'єр", "slug": "architecture", "icon": "building", "sort_order": 6, "is_visible": True},
    {"name": "Текстури & Матеріали", "slug": "textures", "icon": "layers", "sort_order": 7, "is_visible": True},
    {"name": "Транспорт", "slug": "vehicles", "icon": "car", "sort_order": 8, "is_visible": True},
    {"name": "Інше", "slug": "other", "icon": "box", "sort_order": 99, "is_visible": True},
]


def migrate_sqlite_columns():
    """Migrates existing SQLite tables if new columns are added."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check categories table
    cursor.execute("PRAGMA table_info(categories)")
    cat_cols = [row[1] for row in cursor.fetchall()]
    if cat_cols:
        if "sort_order" not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0")
        if "is_visible" not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN is_visible BOOLEAN DEFAULT 1")
        if "is_active" not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT 1")
        if "is_marked_for_deletion" not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN is_marked_for_deletion BOOLEAN DEFAULT 0")

    # Check channels table
    cursor.execute("PRAGMA table_info(channels)")
    ch_cols = [row[1] for row in cursor.fetchall()]
    if ch_cols:
        if "account_id" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN account_id INTEGER")
        if "initial_scan_completed" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN initial_scan_completed BOOLEAN DEFAULT 0")
        if "status" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN status TEXT DEFAULT 'idle'")
        if "status_message" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN status_message TEXT")
        if "last_synced_at" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN last_synced_at TIMESTAMP")
        if "processed_count" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN processed_count INTEGER DEFAULT 0")
        if "total_posts" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN total_posts INTEGER DEFAULT 0")
        if "scan_mode" not in ch_cols:
            cursor.execute("ALTER TABLE channels ADD COLUMN scan_mode TEXT DEFAULT 'idle'")

    # Check models table
    cursor.execute("PRAGMA table_info(models)")
    m_cols = [row[1] for row in cursor.fetchall()]
    if m_cols:
        if "file_formats" not in m_cols:
            cursor.execute("ALTER TABLE models ADD COLUMN file_formats TEXT")
        if "archive_types" not in m_cols:
            cursor.execute("ALTER TABLE models ADD COLUMN archive_types TEXT")
        if "render_engines" not in m_cols:
            cursor.execute("ALTER TABLE models ADD COLUMN render_engines TEXT")

    # Create cart_items table if not exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cart_items'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        """)

    # QA-001: enforce one cart row per model. Existing installs have no UNIQUE
    # constraint, so parallel POSTs could both pass the "already in cart" check
    # and insert duplicates. Dedupe leftovers first, then add the unique index.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ux_cart_items_model_id'")
    if not cursor.fetchone():
        cursor.execute("""
            DELETE FROM cart_items
            WHERE id NOT IN (SELECT MIN(id) FROM cart_items GROUP BY model_id)
        """)
        cursor.execute("CREATE UNIQUE INDEX ux_cart_items_model_id ON cart_items(model_id)")

    # Create projects table if not exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Create project_items table if not exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_items'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE project_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                model_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
            )
        """)

    # --- Rebuild FKs to add ON DELETE CASCADE -------------------------------
    # SQLite cannot ALTER a constraint: the table has to be recreated. Older
    # installs have cart_items / project_items without CASCADE, which leaves
    # rows pointing at deleted models. Detect by inspecting the stored DDL.
    def _needs_cascade(table):
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        row = cursor.fetchone()
        return bool(row) and "ON DELETE CASCADE" not in (row[0] or "")

    cursor.execute("PRAGMA foreign_keys=OFF")

    if _needs_cascade("cart_items"):
        cursor.execute("""
            CREATE TABLE cart_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
            )
        """)
        # Only carry over rows whose model still exists.
        cursor.execute("""
            INSERT INTO cart_items_new (id, model_id, created_at)
            SELECT id, model_id, created_at FROM cart_items
            WHERE model_id IN (SELECT id FROM models)
        """)
        cursor.execute("DROP TABLE cart_items")
        cursor.execute("ALTER TABLE cart_items_new RENAME TO cart_items")

    if _needs_cascade("project_items"):
        cursor.execute("""
            CREATE TABLE project_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                model_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            INSERT INTO project_items_new (id, project_id, model_id, added_at)
            SELECT id, project_id, model_id, added_at FROM project_items
            WHERE model_id IN (SELECT id FROM models)
              AND project_id IN (SELECT id FROM projects)
        """)
        cursor.execute("DROP TABLE project_items")
        cursor.execute("ALTER TABLE project_items_new RENAME TO project_items")

    # Clean up any orphans left by pre-CASCADE deletions.
    cursor.execute("DELETE FROM cart_items WHERE model_id NOT IN (SELECT id FROM models)")
    cursor.execute("DELETE FROM project_items WHERE model_id NOT IN (SELECT id FROM models)")
    cursor.execute("UPDATE channels SET account_id = NULL WHERE account_id IS NOT NULL AND account_id NOT IN (SELECT id FROM telegram_accounts)")

    cursor.execute("PRAGMA foreign_keys=ON")

    conn.commit()
    conn.close()


def init_db():
    migrate_sqlite_columns()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed default categories if missing
        if db.query(Category).count() == 0:
            for cat_data in DEFAULT_USER_CATEGORIES:
                cat = Category(
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    icon=cat_data["icon"],
                    sort_order=cat_data["sort_order"],
                    is_visible=cat_data["is_visible"],
                    is_custom=False
                )
                db.add(cat)
            db.commit()

        # Seed default main account if missing
        if db.query(TelegramAccount).count() == 0:
            old_cfg = db.query(TelegramConfig).first()
            acc = TelegramAccount(
                name="Основний Telegram Акаунт",
                api_id=old_cfg.api_id if old_cfg else None,
                api_hash=old_cfg.api_hash if old_cfg else None,
                phone_number=old_cfg.phone_number if old_cfg else None,
                is_authorized=old_cfg.is_authorized if old_cfg else False,
                session_string=old_cfg.session_string if old_cfg else None
            )
            db.add(acc)
            db.commit()
            db.refresh(acc)

            # Bind existing channels to main account
            channels = db.query(Channel).all()
            for ch in channels:
                if not ch.account_id:
                    ch.account_id = acc.id
            db.commit()

    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
