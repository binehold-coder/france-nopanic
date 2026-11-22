# Франція без паніки

Telegram-бот [@france_nopanic_bot](https://t.me/france_nopanic_bot) + канал [@france_nopanic](https://t.me/france_nopanic).
Пояснює французькі листи (фото/PDF) українською або російською: хто пише, чого хочуть, термін, що робити.

## Как устроено
- `nopanic/` — бот: aiogram 3, Anthropic, SQLite. Файлы писем не сохраняются.
- `deploy/settings.env` — несекретные настройки (режим, модели, лимит). Меняются коммитом.
- `deploy/server.sh` — серверная часть деплоя; `.github/workflows/deploy.yml` — пуш в `main` → тесты → деплой на IONOS.

## Секреты (GitHub → Settings → Secrets → Actions)
`FRANCE_NOPANIC_BOT`, `ANTHROPIC_API_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`.

## На сервере
`/opt/france_nopanic/{app,venv,data,.env}`, сервис `france-nopanic`.
Лог: `journalctl -u france-nopanic -n 100`.

## Команды владельца
`/stats` — статистика и расход токенов, `/channel_test` — проверить, что бот может постить в канал.

## Режимы
`ACCESS_MODE=owner` — бот отвечает только владельцу (`OWNER_IDS`), остальным «скоро запуск».
`ACCESS_MODE=public` — для всех, с лимитом `FREE_LETTERS` бесплатных писем (у владельца лимита нет).
