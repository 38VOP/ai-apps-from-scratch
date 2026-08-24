import os
import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import deque

from sqlalchemy.orm import Session
from database import DB_DIR, PREVIEWS_DIR, Category, Channel, ModelItem, TelegramAccount
from classifier import classify_text, extract_metadata

logger = logging.getLogger("telegram_service")

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


class ParseTask:
    def __init__(self, channel_id: int, account_id: int, mode: str = "backlog"):
        self.channel_id = channel_id
        self.account_id = account_id
        self.mode = mode
        self.created_at = datetime.utcnow()


class MultiAccountTelegramServiceManager:
    def __init__(self):
        self.clients: Dict[int, Any] = {}
        self.pending_auth: Dict[int, Dict[str, str]] = {}
        self.parse_queue: deque = deque()
        self.active_tasks: Dict[int, ParseTask] = {}
        self.account_last_used: Dict[int, datetime] = {}
        self.is_processing_queue = False
        self.min_delay = 2.0
        self.max_delay = 5.0
        self.flood_cooldown = 300

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

    def _get_best_account(self, db: Session) -> Optional[int]:
        accounts = db.query(TelegramAccount).filter(TelegramAccount.is_authorized == True).all()
        if not accounts:
            return None
        best_account = None
        earliest_usage = None
        for acc in accounts:
            last_used = self.account_last_used.get(acc.id)
            if last_used is None:
                return acc.id
            if earliest_usage is None or last_used < earliest_usage:
                earliest_usage = last_used
                best_account = acc.id
        return best_account

    def _get_random_delay(self) -> float:
        return random.uniform(self.min_delay, self.max_delay)

    async def _process_queue(self, db: Session):
        if self.is_processing_queue:
            return
        self.is_processing_queue = True
        try:
            while self.parse_queue:
                task = self.parse_queue.popleft()
                if task.channel_id in self.active_tasks:
                    continue
                self.active_tasks[task.channel_id] = task
                try:
                    result = await self.sync_channel_posts(db, task.channel_id)
                    if result.get("success"):
                        channel = db.query(Channel).filter(Channel.id == task.channel_id).first()
                        if channel:
                            channel.scan_mode = task.mode
                            db.commit()
                except Exception as e:
                    logger.error(f"Error processing task for channel {task.channel_id}: {e}")
                finally:
                    self.active_tasks.pop(task.channel_id, None)
                    self.account_last_used[task.account_id] = datetime.utcnow()
                await asyncio.sleep(self._get_random_delay())
        finally:
            self.is_processing_queue = False

    async def request_code(self, db: Session, account_id: int, phone_number: str) -> Dict[str, Any]:
        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
        if not account or not account.api_id or not account.api_hash:
            return {"success": False, "message": "Спочатку збережіть API ID та API Hash для цього акаунту"}
        account.phone_number = phone_number.strip()
        db.commit()
        try:
            # Для переавторизації створюємо НОВУ сесію, інакше Telegram може відхилити запит
            session = StringSession()
            client = TelegramClient(session, int(account.api_id), account.api_hash)
            await client.connect()
            res = await client.send_code_request(phone_number)
            # Зберігаємо НОВИЙ phone_code_hash
            if account_id not in self.pending_auth:
                self.pending_auth[account_id] = {}
            self.pending_auth[account_id][res.phone_code_hash] = {
                "phone_code_hash": res.phone_code_hash,
                "temp_phone": phone_number,
                "created_at": datetime.utcnow().isoformat()
            }
            # Зберігаємо нову сесію в БД
            session_str = client.session.save()
            account.session_string = session_str
            db.commit()
            # Зберігаємо клієнт для наступного використання
            self.clients[account_id] = client
            return {"success": True, "message": f"Код підтвердження надіслано у Telegram. Дійсний 120 секунд.", "phone_code_hash": res.phone_code_hash}
        except Exception as e:
            err_msg = str(e)
            if "already used" in err_msg:
                return {"success": False, "message": "Telegram тимчасово обмежив запити. Зачекайте 10-15 хв і спробуйте знову."}
            return {"success": False, "message": f"Помилка надсилання коду: {err_msg}"}

    async def _save_session(self, client, db: Session, account_id: int):
        """Зберігає оновлену сесію Telethon назад у БД.
        Telethon оновлює сесію всередині після кожної операції (для безпеки),
        але не зберігає її автоматично — це треба робити вручну."""
        try:
            session_str = client.session.save()
            account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
            if account and account.session_string != session_str:
                account.session_string = session_str
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to save session for account {account_id}: {e}")

    async def sign_in(self, db: Session, account_id: int, code: str, phone_code_hash: str = None) -> Dict[str, Any]:
        pending = self.pending_auth.get(account_id)
        if not pending:
            return {"success": False, "message": "Запит коду застарів. Запитайте код знову."}
        
        # Якщо hash не передано — шукаємо серед останніх запитів
        if not phone_code_hash:
            # Беремо найсвіжіший hash
            latest = sorted(pending.values(), key=lambda x: x.get("created_at", ""), reverse=True)[0]
            phone_code_hash = latest["phone_code_hash"]
            phone_number = latest["temp_phone"]
        else:
            entry = pending.get(phone_code_hash)
            if not entry:
                return {"success": False, "message": "Запит коду застарів. Запитайте код знову."}
            phone_number = entry["temp_phone"]
        
        try:
            client = await self.get_client_for_account(db, account_id)
            if not client:
                return {"success": False, "message": "Telegram клієнт недоступний"}
            await client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            session_str = client.session.save()
            account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
            if account:
                account.is_authorized = True
                account.session_string = session_str
                db.commit()
            # Прибираючи використаний hash
            if phone_code_hash in pending:
                del pending[phone_code_hash]
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
            account_id = self._get_best_account(db)
            if account_id:
                channel.account_id = account_id
                db.commit()

        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first() if account_id else None
        if not account or not account.is_authorized:
                    best_id = self._get_best_account(db)
                    if best_id:
                        account_id = best_id
                        channel.account_id = best_id
                        db.commit()
                    else:
                        channel.status = "error"
                        channel.scan_mode = "idle"
                        channel.status_message = "Увійдіть у Telegram у розділі Джерела — акаунт не авторизований"
                        db.commit()
                        return {"success": False, "message": "Увійдіть у Telegram у розділі Джерела — акаунт не авторизований", "added_count": 0}

        client = await self.get_client_for_account(db, account_id) if account_id else None
        if not client or not await client.is_user_authorized():
            channel.status = "error"
            channel.scan_mode = "idle"
            channel.status_message = "Увійдіть у Telegram у розділі Джерела — сесія недійсна"
            db.commit()
            return {"success": False, "message": "Увійдіть у Telegram у розділі Джерела — сесія недійсна", "added_count": 0}

        is_initial_scan = not channel.initial_scan_completed
        if is_initial_scan:
            channel.status = "backlog"
            channel.scan_mode = "backlog"
            channel.status_message = "Первинне сканування історії каналу..."
        else:
            channel.status = "monitoring"
            channel.scan_mode = "monitoring"
            channel.status_message = "Моніторинг нових постів..."
        db.commit()

        new_items_count = 0
        highest_msg_id = channel.last_scanned_id or 0
        batch_counter = 0

        try:
            entity = await client.get_entity(channel.username or channel.telegram_id)
            if is_initial_scan:
                try:
                    channel.total_posts = await client.get_count(entity)
                    db.commit()
                except Exception as e:
                    logger.warning(f"Could not get total posts count: {e}")
        except Exception as e:
            logger.warning(f"Could not get entity: {e}")

        iter_kwargs: Dict[str, Any] = {}
        if not is_initial_scan and channel.last_scanned_id:
            iter_kwargs["min_id"] = channel.last_scanned_id

        try:
            entity = await client.get_entity(channel.username or channel.telegram_id)
            categories_by_slug = {c.slug: c.id for c in db.query(Category).filter(Category.is_active == True).all()}
            other_cat_id = categories_by_slug.get("other", 1)

            async for msg in client.iter_messages(entity, **iter_kwargs):
                if not msg or not msg.id:
                    continue
                if msg.id > highest_msg_id:
                    highest_msg_id = msg.id
                if not msg.text:
                    continue
                formats, archives, renders, title = extract_metadata(msg.text)
                if not (formats or archives or renders or msg.photo):
                    continue
                existing = db.query(ModelItem).filter(
                    ModelItem.channel_id == channel.id,
                    ModelItem.telegram_message_id == msg.id
                ).first()
                if existing:
                    continue
                preview_rel_path = None
                if msg.photo:
                    filename = f"preview_{channel.id}_{msg.id}.jpg"
                    full_path = os.path.join(PREVIEWS_DIR, filename)
                    if os.path.exists(full_path):
                        preview_rel_path = f"/previews/{filename}"
                    else:
                        try:
                            await client.download_media(msg.photo, file=full_path)
                            preview_rel_path = f"/previews/{filename}"
                        except Exception as img_err:
                            logger.warning(f"Could not download photo for msg {msg.id}: {img_err}")
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
                    raw_text=msg.text,
                    file_formats=json.dumps(formats, ensure_ascii=False),
                    archive_types=json.dumps(archives, ensure_ascii=False),
                    render_engines=json.dumps(renders, ensure_ascii=False)
                )
                db.add(model)
                new_items_count += 1
                batch_counter += 1
                if batch_counter >= 20:
                    if highest_msg_id > 0:
                        channel.last_scanned_id = highest_msg_id
                    channel.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
                    db.commit()
                    batch_counter = 0
                    await asyncio.sleep(self._get_random_delay())

            channel.initial_scan_completed = True
            channel.status = "up_to_date"
            channel.scan_mode = "monitoring"
            channel.status_message = "Актуальний"
            channel.last_synced_at = datetime.utcnow()
            if highest_msg_id > 0:
                channel.last_scanned_id = highest_msg_id
            channel.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
            db.commit()
            await self._save_session(client, db, account_id)
            scan_type_name = "Первинне сканування" if is_initial_scan else "Оновлення"
            return {"success": True, "message": f"{scan_type_name} завершено: додано {new_items_count} нових 3D моделей", "added_count": new_items_count}

        except FloodWaitError as fw:
            wait_seconds = getattr(fw, 'seconds', 60)
            wait_minutes = round(wait_seconds / 60, 1)
            if batch_counter > 0:
                if highest_msg_id > 0:
                    channel.last_scanned_id = highest_msg_id
                channel.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
            channel.status = "error"
            channel.scan_mode = "idle"
            channel.status_message = "Telegram обмежив запити → зачекайте ~{wait_minutes} хв., продовжиться само"
            channel.last_synced_at = datetime.utcnow()
            db.commit()
            await self._save_session(client, db, account_id)
            return {"success": False, "message": f"Telegram обмежив запити. Прогрес збережено ({new_items_count} моделей). Зачекайте ~{wait_minutes} хв.", "added_count": new_items_count}

        except (UserDeactivatedBanError, AuthKeyUnregisteredError) as auth_err:
            channel.status = "error"
            channel.scan_mode = "idle"
            channel.status_message = "Сесія застаріла → переавторизуйте акаунт у розділі Джерела"
            db.commit()
            return {"success": False, "message": "Сесія Telegram більше не дійсна. Переавторизуйте акаунт."}

        except Exception as e:
            if batch_counter > 0:
                if highest_msg_id > 0:
                    channel.last_scanned_id = highest_msg_id
                channel.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
            channel.status = "error"
            channel.scan_mode = "idle"
            channel.status_message = f"Збій синхронізації → перевірте канал або спробуйте пізніше ({str(e)[:60]})"
            channel.last_synced_at = datetime.utcnow()
            db.commit()
            await self._save_session(client, db, account_id)
            logger.error(f"Error scanning channel {channel.id}: {e}")
            return {"success": False, "message": f"Помилка сканування каналу: {str(e)}"}

    async def queue_channel(self, db: Session, channel_id: int) -> Dict[str, Any]:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            return {"success": False, "message": "Канал не знайдено"}
        if not channel.enabled:
            return {"success": False, "message": "Канал вимкнено"}
        if channel_id in self.active_tasks:
            return {"success": False, "message": "Канал вже в обробці"}
        account_id = channel.account_id
        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first() if account_id else None
        if not account or not account.is_authorized:
            account_id = self._get_best_account(db)
            if account_id:
                channel.account_id = account_id
                db.commit()
            else:
                channel.status = "error"
                channel.status_message = "Увійдіть у Telegram у розділі Джерела — акаунт не авторизований"
                db.commit()
        return {"success": False, "message": "Акаунт не авторизований, синхронізація неможлива"}
        mode = "backlog" if not channel.initial_scan_completed else "monitoring"
        task = ParseTask(channel_id=channel_id, account_id=account_id, mode=mode)
        self.parse_queue.append(task)
        channel.status = "queued"
        channel.status_message = "У черзі на обробку"
        db.commit()
        asyncio.create_task(self._process_queue(db))
        return {"success": True, "message": f"Канал додано у чергу ({mode})"}


telegram_manager = MultiAccountTelegramServiceManager()
