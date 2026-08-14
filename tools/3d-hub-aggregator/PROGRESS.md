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