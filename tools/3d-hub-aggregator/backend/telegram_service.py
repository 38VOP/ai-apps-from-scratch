import os
import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta
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
        self.pending_auth: Dict[int, Dict[str, Any]] = {}
        self.parse_queue: deque = deque()
        self.active_tasks: Dict[int, ParseTask] = {}
        self.account_last_used: Dict[int, datetime] = {}
        self.is_processing_queue = False

        # --- Анти-бан таймінги (ANCHOR.md р.54, р.60) ---------------------
        # Непомітність важливіша за швидкість. Основний ризик — backlog-скан
        # (первинний повний прохід історії), тому там паузи довгі; monitoring
        # добирає лише нові пости, йому достатньо коротких.
        self.min_delay = 2.0          # monitoring: пауза між пачками, с
        self.max_delay = 5.0
        self.backlog_batch_size = 12  # постів у пачці під час backlog
        self.backlog_min_delay = 25.0  # backlog: пауза між пачками, с
        self.backlog_max_delay = 70.0
        self.long_pause_every = 8     # раз на стільки пачок — «перекур»
        self.long_pause_min = 180.0   # тривалість «перекуру», с
        self.long_pause_max = 360.0
        self.channel_gap_min = 120.0  # пауза між каналами в черзі, с
        self.channel_gap_max = 300.0
        self.flood_extra_cooldown = 600  # запас після FloodWait, с

    async def get_client_for_account(self, db: Session, account_id: int) -> Optional[Any]:
        if not TELETHON_AVAILABLE:
            return None
        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
        if not account or not account.api_id or not account.api_hash:
            return None
        if account_id in self.clients and self.clients[account_id].is_connected():
            return self.clients[account_id]
        try:
            session = StringSession(account.session_string or "")
            client = TelegramClient(session, int(account.api_id), account.api_hash)
            await client.connect()
            self.clients[account_id] = client
            return client
        except Exception as e:
            logger.error(f"Telegram client connection error for account {account_id}: {e}")
            # Сесія невалідна — прибираємо кеш, щоб наступний виклик теж не падав
            self.clients.pop(account_id, None)
            return None

    def _get_best_account(self, db: Session) -> Optional[int]:
        accounts = db.query(TelegramAccount).filter(TelegramAccount.is_authorized == True).all()
        if not accounts:
            return None
        now = datetime.utcnow()
        best_account = None
        earliest_usage = None
        for acc in accounts:
            last_used = self.account_last_used.get(acc.id)
            if last_used is None:
                return acc.id
            # Час у майбутньому = акаунт під витримкою після FloodWait.
            # Такий не беремо взагалі, інакше запас нічого не дає.
            if last_used > now:
                continue
            if earliest_usage is None or last_used < earliest_usage:
                earliest_usage = last_used
                best_account = acc.id
        if best_account is None:
            held = [
                f"{aid} до {t.isoformat(timespec='seconds')}"
                for aid, t in self.account_last_used.items() if t > now
            ]
            if held:
                logger.warning(f"All accounts on cooldown: {', '.join(held)}")
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
                    # Не збиваємо витримку, яку виставив FloodWait: там час
                    # у майбутньому, і перезапис на utcnow() зняв би запас.
                    prev = self.account_last_used.get(task.account_id)
                    now = datetime.utcnow()
                    if prev is None or prev < now:
                        self.account_last_used[task.account_id] = now
                # Пауза між каналами: людина не переходить до наступного
                # джерела за секунди.
                gap = random.uniform(self.channel_gap_min, self.channel_gap_max)
                logger.info(f"Queue: waiting {gap:.0f}s before the next channel")
                await asyncio.sleep(gap)
        finally:
            self.is_processing_queue = False

    # Куди Telegram доставляє код. Тип запиту визначає, чи користувач узагалі
    # має шанс його побачити, тому це має доходити до інтерфейсу, а не тонути в логах.
    _DELIVERY_HINTS = {
        "SentCodeTypeApp": ("у застосунок Telegram", True),
        "SentCodeTypeSms": ("як SMS", False),
        "SentCodeTypeCall": ("голосовим дзвінком", False),
        "SentCodeTypeFlashCall": ("скинутим дзвінком — код у номері, що дзвонив", False),
        "SentCodeTypeMissedCall": ("пропущеним дзвінком — код у номері, що дзвонив", False),
        "SentCodeTypeEmailCode": ("на email, привʼязаний до акаунта", False),
        "SentCodeTypeFragmentSms": ("через Fragment (анонімний номер)", False),
    }

    @classmethod
    def _describe_delivery(cls, sent) -> Dict[str, Any]:
        """Перекладає тип доставки Telegram у зрозуміле повідомлення.

        SentCodeTypeApp — окремий випадок: код приходить ЛИШЕ в уже
        авторизований Telegram на цьому номері. Для номера без активної сесії
        він не прийде нікуди, хоча API повертає успіх. Без цієї підказки
        користувач марно чекає SMS.
        """
        type_name = type(sent.type).__name__
        where, app_only = cls._DELIVERY_HINTS.get(type_name, ("невідомим способом", False))
        has_fallback = getattr(sent, "next_type", None) is not None

        if app_only:
            msg = ("Telegram надіслав код " + where + ". Він приходить лише на "
                   "пристрій, де цей номер уже авторизований — SMS не буде.")
            if not has_fallback:
                msg += " Резервної доставки для цього номера Telegram не пропонує."
        else:
            msg = "Код надіслано " + where + ". Дійсний ~120 секунд."

        return {
            "message": msg,
            "delivery": type_name,
            "app_only": app_only,
            "has_fallback": has_fallback,
        }

    async def request_code(self, db: Session, account_id: int, phone_number: str) -> Dict[str, Any]:
        account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
        if not account or not account.api_id or not account.api_hash:
            return {"success": False, "message": "Спочатку збережіть API ID та API Hash для цього акаунту"}

        phone_number = (phone_number or "").strip()
        if not phone_number:
            return {"success": False, "message": "Вкажіть номер телефону"}
        account.phone_number = phone_number
        db.commit()

        try:
            # Один кешований клієнт на акаунт: phone_code_hash дійсний лише для
            # того зʼєднання, яке його видало, тому sign_in мусить потім взяти
            # ЦЕЙ САМИЙ клієнт (get_client_for_account повертає його з кешу).
            client = await self.get_client_for_account(db, account_id)
            if not client:
                return {"success": False, "message": "Не вдалося ініціалізувати Telegram клієнт"}
            res = await client.send_code_request(phone_number)
            info = self._describe_delivery(res)
            self.pending_auth[account_id] = {
                "phone_code_hash": res.phone_code_hash,
                "temp_phone": phone_number,
                "created_at": datetime.utcnow(),
            }
            logger.info(
                f"Account {account_id}: code requested for {phone_number}, "
                f"delivery={info['delivery']}, fallback={info['has_fallback']}, "
                f"client=0x{id(client):x}, hash={res.phone_code_hash}"
            )
            return {
                "success": True,
                "message": info["message"],
                "phone_code_hash": res.phone_code_hash,
                "delivery": info["delivery"],
                "app_only": info["app_only"],
            }
        except Exception as e:
            return {"success": False, "message": self._humanize_auth_error(e)}

    async def _drop_pending(self, account_id: int):
        """Прибирає незавершену спробу авторизації."""
        self.pending_auth.pop(account_id, None)

    async def cancel_pending_auth(self, account_id: int):
        """Публічна відмова від незавершеної авторизації."""
        await self._drop_pending(account_id)

    async def release_account(self, account_id: int):
        """Повністю відпускає акаунт: зʼєднання і незавершену авторизацію.
        Викликається при видаленні акаунта і при зміні номера, щоб не
        залишати відкритих сокетів і чужого phone_code_hash."""
        client = self.clients.pop(account_id, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        self.pending_auth.pop(account_id, None)
        self.account_last_used.pop(account_id, None)

    @staticmethod
    def _humanize_auth_error(e: Exception) -> str:
        """Технічну помилку Telegram — у дію, зрозумілу без документації."""
        msg = str(e)
        low = msg.lower()

        # FloodWaitError несе точний час очікування в .seconds, але його текст
        # виглядає як "A wait of 22713 seconds is required" — без слова flood,
        # тому перевіряти тільку підрядок недостатньо.
        wait = getattr(e, "seconds", None)
        if wait is None:
            m = re.search(r"wait of (\d+) seconds", low)
            if m:
                wait = int(m.group(1))
        if wait:
            if wait >= 3600:
                h = wait // 3600
                m_ = (wait % 3600) // 60
                left = f"{h} год {m_} хв" if m_ else f"{h} год"
            elif wait >= 60:
                left = f"{wait // 60} хв"
            else:
                left = f"{wait} с"
            return (f"Telegram заблокував запити для цього номера на {left}. "
                    f"Це ліміт на боці Telegram — скористайтеся іншим номером "
                    f"або зачекайте.")

        if "all available options" in low or "already used" in low:
            return ("Telegram вичерпав способи доставки коду на цей номер. "
                    "Зачекайте 10–15 хв і спробуйте знову.")
        if "flood" in low:
            return "Telegram обмежив кількість запитів → зачекайте і спробуйте знову."
        if "phone number invalid" in low:
            return "Невірний формат номера. Приклад: +380671234567"
        if "phone number banned" in low:
            return "Цей номер заблокований у Telegram."
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
        if not pending:
            return {"success": False, "message": "Спочатку натисніть «Запитати код»"}

        code = (code or "").strip()
        if not code:
            return {"success": False, "message": "Введіть код з Telegram"}

        try:
            # Той самий кешований клієнт, що видав hash у request_code.
            client = await self.get_client_for_account(db, account_id)
            if not client:
                return {"success": False, "message": "Telegram клієнт недоступний"}
            logger.info(
                f"Account {account_id}: sign_in with client=0x{id(client):x}, "
                f"hash={pending['phone_code_hash']}, code_len={len(code)}"
            )
            await client.sign_in(
                pending["temp_phone"], code, phone_code_hash=pending["phone_code_hash"]
            )
            session_str = client.session.save()
            account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
            if account:
                account.is_authorized = True
                account.session_string = session_str
                db.commit()
            self.pending_auth.pop(account_id, None)
            return {"success": True, "message": "Успішно авторизовано у Telegram!"}
        except Exception as e:
            name = type(e).__name__
            low = str(e).lower()
            if "SessionPasswordNeeded" in name:
                return {"success": False, "message": "Акаунт захищено паролем 2FA — цей спосіб входу поки не підтримується"}
            if "expired" in low:
                # Hash мертвий: наступний «Запитати код» мусить почати заново.
                self.pending_auth.pop(account_id, None)
                return {"success": False, "message": "Код прострочений → натисніть «Запитати код» і введіть новий"}
            if "invalid" in low:
                # Hash ще живий — користувач може просто ввести код правильно.
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
        batches_done = 0

        # Backlog проходить усю історію каналу — саме він виглядає підозріло,
        # тому дрібніші пачки й довгі паузи. Monitoring добирає кілька нових
        # постів, йому вистачає коротких (ANCHOR.md р.54).
        if is_initial_scan:
            batch_size = self.backlog_batch_size
            batch_min, batch_max = self.backlog_min_delay, self.backlog_max_delay
        else:
            batch_size = 20
            batch_min, batch_max = self.min_delay, self.max_delay

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
                if batch_counter >= batch_size:
                    if highest_msg_id > 0:
                        channel.last_scanned_id = highest_msg_id
                    channel.processed_count = db.query(ModelItem).filter(ModelItem.channel_id == channel.id).count()
                    db.commit()
                    batch_counter = 0
                    batches_done += 1

                    # Раз на N пачок — довга пауза-«перекур». Рівний темп
                    # годинами виглядає як бот, навіть із випадковими паузами.
                    if is_initial_scan and batches_done % self.long_pause_every == 0:
                        pause = random.uniform(self.long_pause_min, self.long_pause_max)
                        channel.status_message = (
                            f"Пауза {int(pause // 60)} хв — анти-бан "
                            f"(зібрано {new_items_count})"
                        )
                        db.commit()
                        logger.info(
                            f"Channel {channel.id}: long pause {pause:.0f}s "
                            f"after {batches_done} batches"
                        )
                        await asyncio.sleep(pause)
                        channel.status_message = "Первинне сканування історії каналу..."
                        db.commit()
                    else:
                        await asyncio.sleep(random.uniform(batch_min, batch_max))

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
            channel.status_message = f"Telegram обмежив запити → зачекайте ~{wait_minutes} хв., продовжиться само"
            channel.last_synced_at = datetime.utcnow()
            db.commit()
            await self._save_session(client, db, account_id)
            # Витримка з запасом: позначаємо акаунт використаним у МАЙБУТНЬОМУ,
            # тому _get_best_account природно оминатиме його, поки час не мине.
            # Запас понад вимогу Telegram — щоб не впертися в межу знову.
            if account_id:
                self.account_last_used[account_id] = (
                    datetime.utcnow()
                    + timedelta(seconds=wait_seconds + self.flood_extra_cooldown)
                )
                logger.warning(
                    f"Account {account_id}: FloodWait {wait_seconds}s "
                    f"+{self.flood_extra_cooldown}s buffer — held until "
                    f"{self.account_last_used[account_id].isoformat(timespec='seconds')}"
                )
            return {"success": False, "message": f"Telegram обмежив запити. Прогрес збережено ({new_items_count} моделей). Зачекайте ~{wait_minutes} хв.", "added_count": new_items_count}

        except (UserDeactivatedBanError, AuthKeyUnregisteredError) as auth_err:
            channel.status = "error"
            channel.scan_mode = "idle"
            channel.status_message = "Сесія застаріла → переавторизуйте акаунт у розділі Джерела"
            account.is_authorized = False
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
                account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id).first()
            else:
                channel.status = "error"
                channel.status_message = "Увійдіть у Telegram у розділі Джерела — акаунт не авторизований"
                db.commit()
                return {"success": False, "message": "Акаунт не авторизований, синхронізація неможлива"}

        # Реальна перевірка сесії: поле в БД is_authorized може бути 1,
        # але сесія вже мертва. Інакше Telethon підключиться й відразу
        # впаде з AuthKeyUnregistered під час парсингу.
        client = await self.get_client_for_account(db, account_id)
        if not client or not await client.is_user_authorized():
            channel.status = "error"
            channel.status_message = "Сесія застаріла → переавторизуйте акаунт у розділі Джерела"
            account.is_authorized = False
            db.commit()
            return {"success": False, "message": "Сесія застаріла. Переавторизуйте акаунт у розділі Джерела."}
        mode = "backlog" if not channel.initial_scan_completed else "monitoring"
        task = ParseTask(channel_id=channel_id, account_id=account_id, mode=mode)
        self.parse_queue.append(task)
        channel.status = "queued"
        channel.status_message = "У черзі на обробку"
        db.commit()
        asyncio.create_task(self._process_queue(db))
        return {"success": True, "message": f"Канал додано у чергу ({mode})"}


telegram_manager = MultiAccountTelegramServiceManager()
