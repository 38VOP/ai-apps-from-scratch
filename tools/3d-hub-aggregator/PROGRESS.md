PROGRESS — 3d-hub-aggregator

Лог фактично зробленого. Кожен агент після роботи додає сюди новий запис знизу за форматом з AGENTS.md:

Дата: 14.08.2026
Агент: opencode
Зроблено: Повна реалізація MOD-SOURCES, MOD-PARSER, MOD-CATEGORIZE, MOD-CATALOG, MOD-CART, MOD-PROJECTS, MOD-ADMIN. Синхронізація AGENTS.md/ANCHOR.md з GitHub. Додано анти-бан парсер з чергою та backlog/monitoring. Керування категоріями з системою зелений/червоний. Кошик та проекти. Адмін-дашборд зі статистикою.
Файли / commit: backend/database.py, backend/main.py, backend/telegram_service.py, frontend/src/App.jsx, frontend/src/index.css, AGENTS.md, tools/3d-hub-aggregator/ANCHOR.md, tools/3d-hub-aggregator/PROGRESS.md

Дата: 14.08.2026
Агент: opencode
Зроблено: Виправлення: видалено DELETE /api/categories/{id} (порушення ANCHOR.md), додано endpoint POST /api/models/{id}/refresh-preview, перенесено backend/ і frontend/ в tools/3d-hub-aggregator/, повернуто AGENTS.md до оригіналу, зроблено сайдбар категорій та проектів згортними, перенесено кнопку "Налаштувати" ближче до списку, виправлено цикл перемикання статусу категорії (3 стани: нейтральний/зелений/червоний).
Файли / commit: tools/3d-hub-aggregator/backend/main.py, tools/3d-aggregator/backend/database.py, tools/3d-hub-aggregator/frontend/src/App.jsx, tools/3d-hub-aggregator/frontend/src/index.css, tools/3d-hub-aggregator/ANCHOR.md, tools/3d-hub-aggregator/PROGRESS.md
<!-- Записи агентів додаються нижче цього рядка -->

Дата: 14.08.2026
Агент: opencode
Зроблено: Виправлено дублювання розділу "Проекти": прибрано пункт з топ-меню (Каталог/Джерела/Статистика), додано "Всі проекти" в сайдбар під заголовком секції з FolderOpen іконкою. Тепер Проекти доступні тільки через лівий сайдбар.
Файли / commit: tools/3d-hub-aggregator/frontend/src/App.jsx, tools/3d-hub-aggregator/PROGRESS.md

Дата: 14.08.2026
Агент: grok
Зроблено:
1. ПРИБРАНО ФЕЙКОВИЙ РЕЖИМ: повністю видалено seed_demo_data_if_needed() з telegram_service.py і будь-які виклики (у т.ч. на startup у main.py). Якщо client недоступний / акаунт не авторизований — channel.status="error", status_message="Акаунт не авторизований, синхронізація неможлива", без створення ModelItem.
2. ОЧИЩЕННЯ ДЕМО-ДАНИХ: у init_db() додано one-time cleanup — видаляються всі ModelItem з preview_path що містить images.unsplash.com АБО telegram_message_id ∈ {101..106}. Для зачеплених каналів: initial_scan_completed=False, total_posts=None, last_scanned_id=None, processed_count=0, status=idle — щоб пройшли реальний backlog.
3. ТЕХНІЧНИЙ АКАУНТ: при чистій БД більше НЕ створюється порожній «Основний Telegram Акаунт» (лише міграція з TelegramConfig якщо є реальні credentials). Для існуючої БД: канали з неавторизованого placeholder перепризначаються на будь-який is_authorized=True акаунт, після чого порожній placeholder видаляється.
4. ВИБІР АКАУНТА: у sync_channel_posts і queue_channel завжди перевіряється is_authorized акаунта каналу; якщо ні — _get_best_account і переприв’язка; якщо авторизованих немає — error як у п.1.
5–6. КОШИК: чекбокс на кожній картці + «Вибрати всі»; «Зберегти у проект» шле лише model_ids відмічених; невідмічені лишаються. handleSaveToProject показує помилки (мережа / backend) через globalSyncMsg замість тихого fail.
7. ПРОЕКТИ: кнопка «+» біля заголовка секції «Проекти» в сайдбарі відкриває модалку створення порожнього проекту без кошика.
ANCHOR.md: версії MOD-PARSER, MOD-SOURCES, MOD-CART, MOD-PROJECTS → v1.1; якір 1.1.
Перевірка: py_compile backend OK. Реальне сканування Telegram-каналу до кінця в цьому середовищі НЕ виконувалось (немає сесії власника / API credentials у sandbox) — потрібна перевірка власником після рестарту backend: авторизований акаунт → Sync на канал → backlog з real posts, без рівно «6 моделей». Кількість видалених фейкових ModelItem залежить від локальної БД власника (cleanup спрацює при старті init_db); у репозиторії демо-функції більше немає.
Файли / commit: tools/3d-hub-aggregator/backend/telegram_service.py, database.py, main.py, frontend/src/App.jsx, ANCHOR.md, PROGRESS.md

Дата: 18.08.2026
Агент: Antigravity
Зроблено: Створено інтерактивний модульний HTML/Tailwind прототип preview.html та зразок preview_sample.html. Оформлено Блок 1 (логотип, поле пошуку, віджет кошика), Блок 2 (сайдбар з інтерактивними розгортними папками Категорії, Проекти, Налаштування з резервом слотів) та Блок 3 (сітка банерів чітко до границь блоку, нижня панель пагінації та перемикач кількості банерів 8/40/100).
Файли / commit: preview.html, preview_sample.html, tools/3d-hub-aggregator/PROGRESS.md
Перевірка або відхилення: Погоджено власником (вигляд відповідає вимогам).

Дата: 19.08.2026
Агент: cline
Зроблено: Створено відокремлений компонент кошика frontend/src/components/Cart.jsx (MOD-CART v1.1). Перенесено логіку відображення кошика з підтримкою чекбокса на кожній картці моделей, кнопкою «Вибрати всі» / «Зняти всі», кнопкою «Очистити кошик» та кнопкою «Зберегти у проект» з модалками вибору/створення проекту.
Файли / commit: tools/3d-hub-aggregator/frontend/src/components/Cart.jsx, tools/3d-hub-aggregator/PROGRESS.md
Перевірка або відхилення: npm run build успішно виконано без помилок.

Дата: 20.08.2026
Агент: Antigravity
Зроблено: Виправлено CSS та розташування сайдбару категорій: 1) У frontend/src/index.css для .sidebar додано order: -1 та у Catalog.jsx розміщено aside.sidebar перед main.content-area, що гарантує відображення сайдбару зліва. 2) Прибрано зайвий проміжок між шапкою та сайдбаром (скориговано padding у .sidebar до 16px та прибрано зайвий блок пошуку над main-layout у Catalog.jsx).
Файли / commit: tools/3d-hub-aggregator/frontend/src/index.css, tools/3d-hub-aggregator/frontend/src/components/Catalog.jsx, tools/3d-hub-aggregator/PROGRESS.md
Перевірка або відхилення: npm run build успішно виконано без помилок.

Дата: 21.08.2026
Агент: Antigravity
Зроблено: У frontend/src/components/Catalog.jsx повністю прибрано заголовок "Каталог моделей (N)" разом з лічильником для чистішого вигляду робочої області.
Файли / commit: tools/3d-hub-aggregator/frontend/src/components/Catalog.jsx, tools/3d-hub-aggregator/PROGRESS.md
Перевірка або відхилення: npm run build успішно виконано (0 помилок).

Дата: 21.08.2026
Агент: Antigravity
Зроблено: У frontend/src/components/Catalog.jsx змінено текст заголовка сайдбару з "Мої Категорії" на "Категорії".
Файли / commit: tools/3d-hub-aggregator/frontend/src/components/Catalog.jsx, tools/3d-hub-aggregator/PROGRESS.md
Перевірка або відхилення: npm run build успішно виконано (0 помилок).
Дата: 21.08.2026
Агент: Antigravity
Зроблено: У frontend/src/components/Catalog.jsx змінено компонування модалки деталей моделі з вертикального на горизонтальне (зображення зліва, інформація+кнопки справа). У frontend/src/index.css додано нові класи .model-detail (flex), .detail-media, .detail-img (max-height + object-fit:contain), .detail-info, .detail-meta.
Файли / commit: tools/3d-hub-aggregator/frontend/src/components/Catalog.jsx, tools/3d-hub-aggregator/frontend/src/index.css, tools/3d-hub-aggregator/PROGRESS.md
Перевірка або відхилення: npm run build успішно виконано (0 помилок).
