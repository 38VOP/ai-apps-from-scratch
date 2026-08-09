import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from database import DB_DIR, PREVIEWS_DIR, Category, Channel, ModelItem, TelegramConfig
from classifier import classify_text, extract_metadata

logger = logging.getLogger("telegram_service")

# Lazy Telethon import handling
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import Message, Photo
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False


class TelegramServiceManager:
    def __init__(self):
        self.client: Optional[Any] = None
        self.phone_code_hash: Optional[str] = None
        self.temp_phone: Optional[str] = None

    def get_config(self, db: Session) -> Optional[TelegramConfig]:
        return db.query(TelegramConfig).first()

    def save_config(self, db: Session, api_id: str, api_hash: str, phone_number: str) -> TelegramConfig:
        config = self.get_config(db)
        if not config:
            config = TelegramConfig()
            db.add(config)
        config.api_id = api_id.strip()
        config.api_hash = api_hash.strip()
        config.phone_number = phone_number.strip()
        db.commit()
        db.refresh(config)
        return config

    async def get_client(self, db: Session) -> Optional[Any]:
        if not TELETHON_AVAILABLE:
            return None

        config = self.get_config(db)
        if not config or not config.api_id or not config.api_hash:
            return None

        if self.client and self.client.is_connected():
            return self.client

        session = StringSession(config.session_string or "")
        try:
            self.client = TelegramClient(session, int(config.api_id), config.api_hash)
            await self.client.connect()
            return self.client
        except Exception as e:
            logger.error(f"Telegram client error: {e}")
            return None

    async def request_code(self, db: Session, phone_number: str) -> Dict[str, Any]:
        config = self.get_config(db)
        if not config or not config.api_id or not config.api_hash:
            return {"success": False, "message": "Спочатку збережіть API ID та API Hash"}

        try:
            client = await self.get_client(db)
            if not client:
                return {"success": False, "message": "Не вдалося ініціалізувати Telegram клієнт"}

            res = await client.send_code_request(phone_number)
            self.phone_code_hash = res.phone_code_hash
            self.temp_phone = phone_number
            return {"success": True, "message": "Код підтвердження надіслано в Telegram"}
        except Exception as e:
            return {"success": False, "message": f"Помилка надсилання коду: {str(e)}"}

    async def sign_in(self, db: Session, code: str) -> Dict[str, Any]:
        if not self.temp_phone or not self.phone_code_hash:
            return {"success": False, "message": "Сесію запиту коду застаріла. Запитайте код знову."}

        try:
            client = await self.get_client(db)
            if not client:
                return {"success": False, "message": "Telegram клієнт недоступний"}

            await client.sign_in(self.temp_phone, code, phone_code_hash=self.phone_code_hash)
            session_str = client.session.save()

            config = self.get_config(db)
            if config:
                config.is_authorized = True
                config.session_string = session_str
                db.commit()

            return {"success": True, "message": "Успішно авторизовано у Telegram!"}
        except Exception as e:
            return {"success": False, "message": f"Помилка авторизації: {str(e)}"}

    async def sync_channel_posts(self, db: Session, channel_db_id: int, limit: int = 30) -> Dict[str, Any]:
        channel = db.query(Channel).filter(Channel.id == channel_db_id).first()
        if not channel:
            return {"success": False, "message": "Канал не знайдено"}

        client = await self.get_client(db)
        if not client or not await client.is_user_authorized():
            # If Telegram client is not authorized, run demo generator to seed sample data if DB is empty
            added_count = seed_demo_data_if_needed(db, channel)
            return {
                "success": True, 
                "message": f"Синхронізовано {added_count} моделей (демонстраційний режим)",
                "added_count": added_count
            }

        try:
            entity = await client.get_entity(channel.username or channel.telegram_id)
            messages = await client.get_messages(entity, limit=limit)
            
            categories_by_slug = {c.slug: c.id for c in db.query(Category).all()}
            other_cat_id = categories_by_slug.get("other", 1)
            
            new_items_count = 0

            for msg in messages:
                if not msg.text:
                    continue

                # Check if message contains 3D model keywords or media
                formats, archives, renders, title = extract_metadata(msg.text)
                
                # Filter out messages that don't look like 3D model posts
                if not (formats or archives or renders or msg.photo):
                    continue

                existing = db.query(ModelItem).filter(
                    ModelItem.channel_id == channel.id,
                    ModelItem.telegram_message_id == msg.id
                ).first()

                if existing:
                    continue

                # Download preview photo if present
                preview_rel_path = None
                if msg.photo:
                    filename = f"preview_{channel.id}_{msg.id}.jpg"
                    full_path = os.path.join(PREVIEWS_DIR, filename)
                    if not os.path.exists(full_path):
                        await client.download_media(msg.photo, file=full_path)
                    preview_rel_path = f"/previews/{filename}"

                # Generate direct telegram post link
                if channel.username:
                    post_url = f"https://t.me/{channel.username}/{msg.id}"
                else:
                    clean_id = str(channel.telegram_id).replace("-100", "")
                    post_url = f"https://t.me/c/{clean_id}/{msg.id}"

                # Categorize
                cat_slug = classify_text(msg.text)
                cat_id = categories_by_slug.get(cat_slug, other_cat_id)

                model = ModelItem(
                    telegram_message_id=msg.id,
                    channel_id=channel.id,
                    title=title,
                    description=msg.text,
                    category_id=cat_id,
                    file_formats=json.dumps(formats),
                    archive_types=json.dumps(archives),
                    render_engines=json.dumps(renders),
                    preview_path=preview_rel_path,
                    telegram_post_url=post_url,
                    post_date=msg.date or datetime.utcnow(),
                    raw_text=msg.text
                )
                db.add(model)
                new_items_count += 1

                # Polite delay between downloads
                await asyncio.sleep(0.3)

            channel.last_scanned_id = max([m.id for m in messages], default=channel.last_scanned_id)
            db.commit()

            return {"success": True, "message": f"Додано {new_items_count} нових 3D моделей", "added_count": new_items_count}

        except Exception as e:
            logger.error(f"Error scanning channel: {e}")
            return {"success": False, "message": f"Помилка сканування каналу: {str(e)}"}


telegram_manager = TelegramServiceManager()


def seed_demo_data_if_needed(db: Session, channel: Channel) -> int:
    """Populates realistic demo 3D model metadata for instant visual testing."""
    existing_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
    if existing_count > 0:
        return 0

    categories = {c.slug: c.id for c in db.query(Category).all()}
    
    demo_models = [
        {
            "title": "Сучасний Диван Velvet Minimalist Sofa",
            "desc": "Стильний тримісний диван в оксамитовій оббивці. 3ds Max 2021 + Corona Renderer. Файли: .MAX, .FBX, .OBJ. Текстури в архіві ZIP.",
            "cat": "furniture",
            "formats": ["3ds Max", "FBX", "OBJ"],
            "archives": ["ZIP"],
            "renders": ["Corona", "V-Ray"],
            "post_id": 101,
            "img": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Дизайнерська Люстра Nordic Brass Pendant Lamp",
            "desc": "Підвісний латунний світильник для вітальні або їдальні. 3ds Max 2020, V-Ray, Corona Renderer. Формати .MAX, .FBX.",
            "cat": "lighting",
            "formats": ["3ds Max", "FBX"],
            "archives": ["RAR"],
            "renders": ["V-Ray", "Corona"],
            "post_id": 102,
            "img": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Скандинавський Набір Декору & Вази",
            "desc": "Набір керамічних ваз з гілками евкаліпта та свічками. 3ds Max + Blender, Corona Renderer + Cycles.",
            "cat": "decor",
            "formats": ["3ds Max", "Blender", "OBJ"],
            "archives": ["ZIP"],
            "renders": ["Corona", "Cycles"],
            "post_id": 103,
            "img": "https://images.unsplash.com/photo-1581783342308-f792dbdd27c5?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Кімнатний Фікус Monstera & Ficus Plant Set",
            "desc": "Високодеталізовані кімнатні рослини в бетонних вазонах. PBR текстури 4K. 3ds Max, FBX, OBJ, Corona Render.",
            "cat": "plants",
            "formats": ["3ds Max", "FBX", "OBJ"],
            "archives": ["7Z"],
            "renders": ["Corona"],
            "post_id": 104,
            "img": "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Кухонна Кавомашина DeLonghi Specialista",
            "desc": "Детальна модель ріжкової кавоварки DeLonghi для інтер'єрних візуалізацій кухонь. 3ds Max 2022, V-Ray, Corona.",
            "cat": "appliances",
            "formats": ["3ds Max", "FBX"],
            "archives": ["ZIP"],
            "renders": ["V-Ray", "Corona"],
            "post_id": 105,
            "img": "https://images.unsplash.com/photo-1517668808822-9e428824603b?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Безшовний Дерев'яний Паркет Oak Flooring PBR",
            "desc": "Набір 4K безшовних текстур паркету ялинкою (Herringbone). Дифуз, нормалі, шорсткість. Формати JPG, PNG, MAX.",
            "cat": "textures",
            "formats": ["3ds Max", "OBJ"],
            "archives": ["RAR"],
            "renders": ["V-Ray", "Corona"],
            "post_id": 106,
            "img": "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=800&q=80"
        }
    ]

    added = 0
    username = channel.username or "3d_models_free"

    for d in demo_models:
        cat_id = categories.get(d["cat"], categories.get("other", 1))
        model = ModelItem(
            telegram_message_id=d["post_id"],
            channel_id=channel.id,
            title=d["title"],
            description=d["desc"],
            category_id=cat_id,
            file_formats=json.dumps(d["formats"]),
            archive_types=json.dumps(d["archives"]),
            render_engines=json.dumps(d["renders"]),
            preview_path=d["img"],
            telegram_post_url=f"https://t.me/{username}/{d['post_id']}",
            post_date=datetime.utcnow(),
            raw_text=d["desc"]
        )
        db.add(model)
        added += 1

    db.commit()
    return added
