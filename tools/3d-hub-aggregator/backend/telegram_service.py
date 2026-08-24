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
    # Скільки секунд вважаємо надісланий код придатним. Telegram дає ~120 с;
    # у цьому вікні повторний натиск кнопки не витрачає ліміт доставки.
    CODE_TTL_SECONDS = 120

    def __init__(self):
        self.clients: Dict[int, Any] = {}
        self.pending_auth: Dict[int, Dict[str, Any]] = {}
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
        if not account:
            return {"success": False, "message": "Акаунт не знайдено"}
        if not account.api_id or not account.api_hash:
            return {"success": False, "message": "Спочатку збережіть API ID та API Hash для цього акаунту"}

        phone_number = (phone_number or "").strip()
        if not phone_number:
            return {"success": False, "message": "Вкажіть номер телефону"}
        account.phone_number = phone_number
        db.commit()

        # phone_code_hash у Telethon дійсний ЛИШЕ для того зʼєднання, яке його
        # видало: новий клієнт під кожен натиск кнопки вбиває вже надісланий код.
        # Тому поки попередня спроба свіжа — віддаємо той самий хеш і не турбуємо
        # Telegram. Це також не витрачає ліміт способів доставки на номер.
        pending = self.pending_auth.get(account_id)
        if pending and pending.get("client") and pending.get("temp_phone") == phone_number:
            age = (datetime.utcnow() - pending["created_at"]).total_seconds()
            if age < self.CODE_TTL_SECONDS:
                left = int(self.CODE_TTL_SECONDS - age)
                return {
                    "success": True,
                    "message": (f"Код уже надіслано — перевірте Telegram. "
                                f"Ще дійсний ~{left} с."),
                    "phone_code_hash": pending["phone_code_hash"],
                    "reused": True
                }
            # Код видихнув: просимо Telegram повторити на ТОМУ Ж зʼєднанні.
            client = pending["client"]
            try:
                if not client.is_connected():
                    await client.connect()
                res = await client.send_code_request(phone_number)
                pending["phone_code_hash"] = res.phone_code_hash
                pending["created_at"] = datetime.utcnow()
                return {
                    "success": True,
                    "message": "Код надіслано повторно. Дійсний ~120 секунд.",
                    "phone_code_hash": res.phone_code_hash
                }
            except Exception as e:
                # Resend вичерпано або зʼєднання зіпсоване — починаємо з чистого.
                await self._drop_pending(account_id)
                logger.warning(f"Resend failed for account {account_id}, restarting flow: {e}")

        # Новий цикл авторизації: окремий клієнт на порожній сесії.
        # Робочу сесію в БД НЕ чіпаємо, поки авторизація не завершиться успішно.
        client = None
        try:
            client = TelegramClient(StringSession(), int(account.api_id), account.api_hash)
            await client.connect()
            res = await client.send_code_request(phone_number)
            self.pending_auth[account_id] = {
                "client": client,
                "phone_code_hash": res.phone_code_hash,
                "temp_phone": phone_number,
                "created_at": datetime.utcnow()
            }
            return {
                "success": True,
                "message": "Код підтвердження надіслано у Telegram. Дійсний ~120 секунд.",
                "phone_code_hash": res.phone_code_hash
            }
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            return {"success": False, "message": self._humanize_auth_error(e)}

    async def _drop_pending(self, account_id: int):
        """Закриває і прибирає незавершену спробу авторизації."""
        pending = self.pending_auth.pop(account_id, None)
        if pending and pending.get("client"):
            try:
                await pending["client"].disconnect()
            except Exception:
                pass

    async def cancel_pending_auth(self, account_id: int):
        """Публічна відмова від незавершеної авторизації (кнопка «Інший номер»)."""
        await self._drop_pending(account_id)

    async def release_account(self, account_id: int):
        """Повністю відпускає акаунт: робоче зʼєднання і незавершену авторизацію.
        Викликається при видаленні акаунта, щоб не залишати відкритих сокетів."""
        client = self.clients.pop(account_id, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        await self._drop_pending(account_id)
        self.account_last_used.pop(account_id, None)

    @staticmethod
    def _humanize_auth_error(e: Exception) -> str:
        """Технічну помилку Telegram — у дію, зрозумілу без документації."""
        msg = str(e)
        low = msg.lower()
        if "all available options" in low or "already used" in low:
            return ("Telegram вичерпав способи доставки коду на цей номер. "
                    "Зачекайте 10–15 хв і спробуйте знову.")
        if "flood" in low:
            wait = getattr(e, "seconds", None)
            if wait:
                return f"Telegram обмежив запити → зачекайте ~{round(wait / 60, 1)} хв."
            return "Telegram обмежив кількість запитів → зачекайте і спробуйте знову."
        if "phone number invalid" in low:
            return "Невірний формат номера. Приклад: +380671234567"
        if "api_id" in low or "api_hash" in low:
            return "Невірні API ID / API Hash — перевірте дані з my.telegram.org"
        return f"Не вдалося надіслати код: {msg}"

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
        if not pending or not pending.get("client"):
            return {"success": False, "message": "Спочатку натисніть «Запитати код»"}

        code = (code or "").strip()
        if not code:
            return {"success": False, "message": "Введіть код з Telegram"}

        # Код мусить підтверджуватись ТИМ САМИМ зʼєднанням, яке його запросило,
        # інакше Telegram відповідає PhoneCodeExpired навіть на свіжий код.
        client = pending["client"]
        phone_number = pending["temp_phone"]
        # Фронтенд може надіслати свій hash; актуальним вважаємо серверний.
        active_hash = pending["phone_code_hash"]
        if phone_code_hash and phone_code_hash != active_hash:
            logger.info(f"Account {account_id}: client sent a stale phone_code_hash, using the current one")

        try:
            if not client.is_connected():
                await client.connect()
            await client.sign_in(phone_number, code, phone_code_hash=active_hash)

            # Успіх: аж ТЕПЕР ця сесія стає робочою сесією акаунта.
            session_str = client.session.save()
            account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
            if account:
                account.is_authorized = True
                account.session_string = session_str
                db.commit()

            # Авторизований клієнт переходить у робочий пул, pending закривається.
            old = self.clients.get(account_id)
            if old is not None and old is not client:
                try:
                    await old.disconnect()
                except Exception:
                    pass
            self.clients[account_id] = client
            self.pending_auth.pop(account_id, None)

            return {"success": True, "message": "Успішно авторизовано у Telegram!"}

        except Exception as e:
            low = str(e).lower()
            # Двофакторний пароль — окремий, ще не реалізований сценарій.
            if "password" in low and "2fa" in low or "SessionPasswordNeeded" in type(e).__name__:
                return {"success": False, "message": "Акаунт захищено паролем 2FA — цей спосіб входу поки не підтримується"}
            if "expired" in low:
                await self._drop_pending(account_id)
                return {"success": False, "message": "Код прострочений → натисніть «Запитати код» і введіть новий"}
            if "invalid" in low:
                # Хеш ще живий: користувач може просто ввести код правильно.
                return {"success": False, "message": "Невірний код — перевірте цифри та спробуйте ще раз"}
            return {"success": False, "message": self._humanize_auth_error(e)}

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
