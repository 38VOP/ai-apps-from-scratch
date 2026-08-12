import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from database import DB_DIR, PREVIEWS_DIR, Category, Channel, ModelItem, TelegramAccount
from classifier import classify_text, extract_metadata

logger = logging.getLogger("telegram_service")

# Lazy Telethon import handling
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, UserDeactivatedBanError, AuthKeyUnregisteredError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    FloodWaitError = Exception
    UserDeactivatedBanError = Exception
    AuthKeyUnregisteredError = Exception


class MultiAccountTelegramServiceManager:
    def __init__(self):
        self.clients: Dict[int, Any] = {}
        self.pending_auth: Dict[int, Dict[str, str]] = {}

    async def get_client_for_account(self, db: Session, account_id: int) -> Optional[Any]:
        if not TELETHON_AVAILABLE:
            return None

        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
        if not account or not account.api_id or not account.api_hash:
            return None

        if account_id in self.clients and self.clients[account_id].is_connected():
            return self.clients[account_id]

        session = StringSession(account.session_string or "")
        try:
            client = TelegramClient(session, int(account.api_id), account.api_hash)
            await client.connect()
            self.clients[account_id] = client
            return client
        except Exception as e:
            logger.error(f"Telegram client connection error for account {account_id}: {e}")
            return None

    async def request_code(self, db: Session, account_id: int, phone_number: str) -> Dict[str, Any]:
        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
        if not account or not account.api_id or not account.api_hash:
            return {"success": False, "message": "Спочатку збережіть API ID та API Hash для цього акаунту"}

        account.phone_number = phone_number.strip()
        db.commit()

        try:
            client = await self.get_client_for_account(db, account_id)
            if not client:
                return {"success": False, "message": "Не вдалося ініціалізувати Telegram клієнт"}

            res = await client.send_code_request(phone_number)
            self.pending_auth[account_id] = {
                "phone_code_hash": res.phone_code_hash,
                "temp_phone": phone_number
            }
            return {"success": True, "message": "Код підтвердження надіслано в Telegram"}
        except Exception as e:
            return {"success": False, "message": f"Помилка надсилання коду: {str(e)}"}

    async def sign_in(self, db: Session, account_id: int, code: str) -> Dict[str, Any]:
        pending = self.pending_auth.get(account_id)
        if not pending:
            return {"success": False, "message": "Запит коду застарів. Запитайте код знову."}

        try:
            client = await self.get_client_for_account(db, account_id)
            if not client:
                return {"success": False, "message": "Telegram клієнт недоступний"}

            await client.sign_in(pending["temp_phone"], code, phone_code_hash=pending["phone_code_hash"])
            session_str = client.session.save()

            account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
            if account:
                account.is_authorized = True
                account.session_string = session_str
                db.commit()

            return {"success": True, "message": "Успішно авторизовано у Telegram!"}
        except Exception as e:
            return {"success": False, "message": f"Помилка авторизації: {str(e)}"}

    async def sync_channel_posts(self, db: Session, channel_db_id: int) -> Dict[str, Any]:
        channel = db.query(Channel).filter(Channel.id == channel_db_id).first()
        if not channel:
            return {"success": False, "message": "Канал не знайдено"}

        if not channel.enabled:
            return {"success": False, "message": "Моніторинг цього каналу вимкнено"}

        account_id = channel.account_id
        if not account_id:
            first_acc = db.query(TelegramAccount).filter(TelegramAccount.is_authorized == True).first()
            if first_acc:
                account_id = first_acc.id
                channel.account_id = account_id
                db.commit()

        client = await self.get_client_for_account(db, account_id) if account_id else None

        # --- Fallback: demo mode if not authorized ---
        if not client or not await client.is_user_authorized():
            added_count = seed_demo_data_if_needed(db, channel)
            channel.initial_scan_completed = True
            channel.status = "up_to_date"
            channel.status_message = "Актуальний (демо режим)"
            channel.last_synced_at = datetime.utcnow()
            channel.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
            db.commit()
            return {
                "success": True,
                "message": f"Синхронізовано {added_count} моделей (демонстраційний режим)",
                "added_count": added_count
            }

        # Determine scan mode
        is_initial_scan = not channel.initial_scan_completed

        if is_initial_scan:
            channel.status = "initial_scan"
            channel.status_message = "Первинне сканування повної історії каналу..."
        else:
            channel.status = "syncing"
            channel.status_message = "Синхронізація нових постів..."
        db.commit()

        new_items_count = 0
        # Tracks the highest message ID seen — needed to set last_scanned_id
        # iter_messages goes newest->oldest, so first message has the highest ID
        highest_msg_id = channel.last_scanned_id or 0
        batch_counter = 0

        # Build iter_messages kwargs:
        #   Initial scan:  no min_id -> walks full history, newest to oldest
        #   Incremental:   min_id = last_scanned_id -> only posts newer than last known
        iter_kwargs: Dict[str, Any] = {}
        if not is_initial_scan and channel.last_scanned_id:
            iter_kwargs["min_id"] = channel.last_scanned_id

        try:
            entity = await client.get_entity(channel.username or channel.telegram_id)
            categories_by_slug = {c.slug: c.id for c in db.query(Category).all()}
            other_cat_id = categories_by_slug.get("other", 1)

            async for msg in client.iter_messages(entity, **iter_kwargs):
                if not msg or not msg.id:
                    continue

                # Update highest_msg_id (first iteration = newest message = highest ID)
                if msg.id > highest_msg_id:
                    highest_msg_id = msg.id

                if not msg.text:
                    continue

                formats, archives, renders, title = extract_metadata(msg.text)

                # Skip posts with no photo and no 3D-related keywords
                if not (formats or archives or renders or msg.photo):
                    continue

                # Deduplication
                existing = db.query(ModelItem).filter(
                    ModelItem.channel_id == channel.id,
                    ModelItem.telegram_message_id == msg.id
                ).first()
                if existing:
                    continue

                # Download preview image only — NEVER model archives
                preview_rel_path = None
                if msg.photo:
                    filename = f"preview_{channel.id}_{msg.id}.jpg"
                    full_path = os.path.join(PREVIEWS_DIR, filename)
                    if os.path.exists(full_path):
                        # Already cached from a previous sync run
                        preview_rel_path = f"/previews/{filename}"
                    else:
                        try:
                            await client.download_media(msg.photo, file=full_path)
                            preview_rel_path = f"/previews/{filename}"
                        except Exception as img_err:
                            logger.warning(f"Could not download photo for msg {msg.id}: {img_err}")

                # Permanent source link to original Telegram post
                if channel.username:
                    post_url = f"https://t.me/{channel.username}/{msg.id}"
                else:
                    clean_id = str(channel.telegram_id).replace("-100", "")
                    post_url = f"https://t.me/c/{clean_id}/{msg.id}"

                cat_slug = classify_text(msg.text)
                cat_id = categories_by_slug.get(cat_slug, other_cat_id)

                model = ModelItem(
                    telegram_message_id=msg.id,
                    channel_id=channel.id,
                    title=title,
                    description=msg.text,
                    category_id=cat_id,
                    preview_path=preview_rel_path,
                    telegram_post_url=post_url,
                    post_date=msg.date or datetime.utcnow(),
                    raw_text=msg.text
                )
                db.add(model)
                new_items_count += 1
                batch_counter += 1

                # Commit every 20 records + save progress checkpoint.
                # Guarantees we lose at most 20 records if interrupted mid-scan.
                if batch_counter >= 20:
                    if highest_msg_id > 0:
                        channel.last_scanned_id = highest_msg_id
                    channel.processed_count = (
                        db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
                    )
                    db.commit()
                    batch_counter = 0
                    # Brief pause — polite rate limiting
                    await asyncio.sleep(0.15)

            # --- Successful completion ---
            channel.initial_scan_completed = True
            channel.status = "up_to_date"
            channel.status_message = "Актуальний"
            channel.last_synced_at = datetime.utcnow()
            if highest_msg_id > 0:
                channel.last_scanned_id = highest_msg_id
            channel.processed_count = (
                db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
            )
            db.commit()

            scan_type_name = "Первинне сканування" if is_initial_scan else "Оновлення"
            return {
                "success": True,
                "message": f"{scan_type_name} завершено: додано {new_items_count} нових 3D моделей",
                "added_count": new_items_count
            }

        except FloodWaitError as fw:
            # Telegram rate-limited us. Save progress, do NOT retry or wait.
            wait_seconds = getattr(fw, 'seconds', 60)
            wait_minutes = round(wait_seconds / 60, 1)

            # Flush remaining uncommitted batch
            if batch_counter > 0:
                if highest_msg_id > 0:
                    channel.last_scanned_id = highest_msg_id
                channel.processed_count = (
                    db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
                )

            channel.status = "error"
            channel.status_message = f"Telegram FloodWait: зачекайте ~{wait_minutes} хв. і синхронізуйте знову."
            channel.last_synced_at = datetime.utcnow()
            db.commit()

            logger.warning(f"FloodWaitError on channel {channel.id}: {wait_seconds}s required")
            return {
                "success": False,
                "message": (
                    f"Telegram обмежив запити. Прогрес збережено ({new_items_count} моделей). "
                    f"Зачекайте ~{wait_minutes} хв. та натисніть «Синхронізувати» знову."
                ),
                "added_count": new_items_count
            }

        except (UserDeactivatedBanError, AuthKeyUnregisteredError) as auth_err:
            channel.status = "error"
            channel.status_message = "Сесія Telegram недійсна. Переавторизуйте акаунт."
            db.commit()
            logger.error(f"Auth error on channel {channel.id}: {auth_err}")
            return {
                "success": False,
                "message": "Сесія Telegram більше не дійсна. Перейдіть у «Джерела Telegram» та переавторизуйте акаунт."
            }

        except Exception as e:
            # Unknown error — flush uncommitted batch before marking error
            if batch_counter > 0:
                if highest_msg_id > 0:
                    channel.last_scanned_id = highest_msg_id
                channel.processed_count = (
                    db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
                )

            channel.status = "error"
            channel.status_message = f"Помилка: {str(e)[:80]}"
            channel.last_synced_at = datetime.utcnow()
            db.commit()

            logger.error(f"Error scanning channel {channel.id}: {e}")
            return {"success": False, "message": f"Помилка сканування каналу: {str(e)}"}


telegram_manager = MultiAccountTelegramServiceManager()


def seed_demo_data_if_needed(db: Session, channel: Channel) -> int:
    """Populates realistic demo 3D model metadata for instant visual testing without needing external files."""
    existing_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
    if existing_count > 0:
        return 0

    categories = {c.slug: c.id for c in db.query(Category).all()}

    demo_models = [
        {
            "title": "Сучасний Диван Velvet Minimalist Sofa",
            "desc": "Стильний тримісний диван в оксамитовій оббивці. 3ds Max 2021 + Corona Renderer.",
            "cat": "furniture",
            "post_id": 101,
            "img": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Дизайнерська Люстра Nordic Brass Pendant Lamp",
            "desc": "Підвісний латунний світильник для вітальні або їдальні. 3ds Max 2020, V-Ray, Corona Renderer.",
            "cat": "lighting",
            "post_id": 102,
            "img": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Скандинавський Набір Декору та Вази",
            "desc": "Набір керамічних ваз з гілками евкаліпта та свічками. 3ds Max + Blender.",
            "cat": "decor",
            "post_id": 103,
            "img": "https://images.unsplash.com/photo-1581783342308-f792dbdd27c5?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Кімнатний Фікус Monstera та Ficus Plant Set",
            "desc": "Високодеталізовані кімнатні рослини в бетонних вазонах. PBR текстури 4K.",
            "cat": "plants",
            "post_id": 104,
            "img": "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Кухонна Кавомашина DeLonghi Specialista",
            "desc": "Детальна модель ріжкової кавоварки DeLonghi для інтерєрних візуалізацій кухонь.",
            "cat": "appliances",
            "post_id": 105,
            "img": "https://images.unsplash.com/photo-1517668808822-9e428824603b?auto=format&fit=crop&w=800&q=80"
        },
        {
            "title": "Безшовний Деревяний Паркет Oak Flooring PBR",
            "desc": "Набір 4K безшовних текстур паркету ялинкою Herringbone. Дифуз, нормалі, шорсткість.",
            "cat": "textures",
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
            preview_path=d["img"],
            telegram_post_url=f"https://t.me/{username}/{d['post_id']}",
            post_date=datetime.utcnow(),
            raw_text=d["desc"]
        )
        db.add(model)
        added += 1

    db.commit()
    return added
