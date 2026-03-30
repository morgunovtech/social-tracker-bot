# Social Media Follower Tracker Bot

Telegram-бот для ежедневного отслеживания подписчиков в Telegram, YouTube и LinkedIn.

## Возможности

- Автоматический сбор данных каждый день в 09:00 (Ташкент, UTC+5)
- Отчёт с дельтой за день и неделю
- Ручной ввод данных LinkedIn через команду
- История по каждой платформе
- Хранение данных в SQLite

## Получение токенов

### Telegram Bot
1. Напишите [@BotFather](https://t.me/BotFather) в Telegram
2. Создайте бота командой `/newbot`
3. Скопируйте токен → `BOT_TOKEN`
4. Добавьте бота **администратором** в канал @raschet7
5. Узнайте свой chat ID через [@userinfobot](https://t.me/userinfobot) → `ADMIN_CHAT_ID`

### YouTube Data API
1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект → включите YouTube Data API v3
3. Создайте API Key → `YOUTUBE_API_KEY`
4. ID канала можно найти на странице канала → `YOUTUBE_CHANNEL_ID`

### LinkedIn (RapidAPI)
1. Зарегистрируйтесь на [RapidAPI](https://rapidapi.com/)
2. Подпишитесь на [Fresh LinkedIn Profile Data](https://rapidapi.com/freshdata-freshdata-default/api/fresh-linkedin-profile-data)
3. Скопируйте API Key → `RAPIDAPI_KEY`
4. Укажите URL профиля → `LINKEDIN_PROFILE_URL`

## Настройка

1. Скопируйте файл окружения:
   ```bash
   cp .env.example .env
   ```

2. Заполните `.env` реальными значениями.

## Запуск

```bash
docker-compose up -d
```

Логи:
```bash
docker-compose logs -f
```

Остановка:
```bash
docker-compose down
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие + список команд |
| `/stats` | Текущая сводка из БД |
| `/now` | Принудительный сбор данных + отчёт |
| `/linkedin <число>` | Ручной ввод подписчиков LinkedIn |
| `/history <platform> <days>` | История за N дней |
| `/help` | Список команд |

Команды `/stats`, `/now`, `/linkedin`, `/history` доступны только администратору.

## Формат отчёта

```
📊 Подписчики — 30.03.2026

Telegram: 1,102 (▲ +3 за день, ▲ +18 за неделю)
YouTube: 847 (▲ +1 за день, ▲ +12 за неделю)
LinkedIn: 4,520 (▲ +5 за день, ▲ +22 за неделю)

📈 Всего: 6,469 (▲ +9 за день, ▲ +52 за неделю)
```
