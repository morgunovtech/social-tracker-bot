# Social Media Follower Tracker Bot

Telegram-бот для отслеживания подписчиков в Telegram, YouTube и LinkedIn.

## Возможности

- Ежедневный сбор данных (хранится для трендов и графиков)
- Пуш-отчёт по настраиваемому дню недели (по умолчанию суббота 13:00 Ташкент)
- LinkedIn fetch автоматически через cookie `li_at` (RapidAPI как fallback)
- Inline-ввод LinkedIn через кнопку, без `/linkedin <число>`
- Sparkline за 14 дней, дельты день / неделя / месяц
- Milestone-алерт при пересечении круглых чисел (1k, 5k, 10k…)
- Лидер недели по % роста
- «Тихий режим»: пропустить пуш, если за неделю ничего не изменилось

## Получение токенов

### Telegram Bot
1. Напишите [@BotFather](https://t.me/BotFather) → `/newbot`
2. Скопируйте токен → `BOT_TOKEN`
3. Добавьте бота **администратором** в канал
4. Узнайте свой chat ID через [@userinfobot](https://t.me/userinfobot) → `ADMIN_CHAT_ID`

### YouTube Data API
1. [Google Cloud Console](https://console.cloud.google.com/) → новый проект → включите YouTube Data API v3
2. Создайте API Key → `YOUTUBE_API_KEY`
3. Найдите ID канала → `YOUTUBE_CHANNEL_ID`

### LinkedIn (cookie-based, рекомендуется)
1. Зайдите в [linkedin.com](https://www.linkedin.com/) в браузере под своим аккаунтом
2. DevTools → Application → Cookies → `linkedin.com` → скопируйте значение `li_at` → `LINKEDIN_LI_AT`
3. Укажите URL профиля → `LINKEDIN_PROFILE_URL`
4. Cookie живёт ~1 год; если истёк — бот пришлёт предупреждение в очередном отчёте

### LinkedIn (RapidAPI, fallback)
Используется автоматически, если `LINKEDIN_LI_AT` не задан или cookie сломан.
1. [RapidAPI](https://rapidapi.com/) → подпишитесь на LinkedIn data scraper
2. Скопируйте API Key → `RAPIDAPI_KEY`

## Настройка

```bash
cp .env.example .env
# заполните .env
docker-compose up -d
```

Логи: `docker-compose logs -f`. Остановка: `docker-compose down`.

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие + меню |
| `/stats` | Текущая сводка |
| `/now` | Принудительный сбор + отчёт |
| `/week` | Недельный дайджест |
| `/linkedin <число>` | Ввод LinkedIn вручную |
| `/history [platform] [days]` | История |
| `/settime HH:MM` | Время отчёта (UTC) |
| `/setday <дни>` | День(и) отчёта: `sat`, `mon,thu`, `mon-fri`, `daily` |
| `/setquiet on\|off` | Тихий режим (пропускать неинтересные отчёты) |

Все команды доступны только администратору (`ADMIN_CHAT_ID`).

## Расписание

- Бот **собирает данные ежедневно** в `REPORT_HOUR_UTC:REPORT_MINUTE` (для трендов).
- **Пушит отчёт** только в дни, выбранные через `/setday` (или `REPORT_DOW`).
- Дефолт: `sat` 08:00 UTC = суббота 13:00 Ташкент.

## Формат отчёта

```
📊 Подписчики — 02.05.2026

Telegram: 1,010  ▁▃▄▅▆█ (▲ +7 день, ▲ +20 неделя, ▲ +60 месяц)
YouTube: 850  ▁▂▃█ (▲ +30 неделя, ▲ +50 месяц)
LinkedIn: 4,520  ▁▅▇█ (▲ +5 день, ▲ +30 неделя, ▲ +120 месяц)

🎯 Telegram перешагнул 1,000!
🏆 Лидер недели: YouTube +3.7%

📈 Всего: 6,380 (▲ +80 неделя, ▲ +230 месяц)
```
