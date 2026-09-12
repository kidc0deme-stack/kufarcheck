# Kufar Checker

Мониторинг новых объявлений на kufar.by с уведомлениями в Telegram.

## Что делает

- Периодически сканирует kufar.by по заданным фильтрам (город + категория + ключевые слова)
- Присылает уведомления в Telegram о новых объявлениях
- Веб-интерфейс для управления фильтрами (работает в браузере телефона)

## Запуск (Windows)

### 1. Установи Python 3.12+
Скачай с https://python.org/downloads/ (поставь галочку "Add Python to PATH")

### 2. Установи зависимости
```bash
cd "C:\Users\Qvantit\Downloads\kufar checker\backend"
python -m pip install -r requirements.txt
```

### 3. Настрой Telegram-бот

1. Напиши [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`, следуй инструкциям
3. Получи токен (вида `123456:ABC-DEF...`)
4. Напиши своему боту любое сообщение
5. Узнай свой chat_id: `https://api.telegram.org/bot<ТОКЕН>/getUpdates`
   В ответе найди `"id": 123456789` в поле `"from"` или `"chat"`

### 4. Настрой .env
Скопируй `.env.example` → `.env` и заполни:

```ini
TELEGRAM_BOT_TOKEN=123456:ABC-DEF-GHI...
TELEGRAM_CHAT_ID=123456789
POLL_INTERVAL=60
```

### 5. Запусти
```bash
cd "C:\Users\Qvantit\Downloads\kufar checker\backend"
python main.py
```

### 6. Открой
- Веб-интерфейс: http://127.0.0.1:8000
- Чтобы открыть с телефона в той же сети: замени `127.0.0.1` на IP компьютера (см. `ipconfig`)

## Веб-интерфейс

После запуска открой http://127.0.0.1:8000 — там:
- Выбор города (Минск, Брест, Гомель, Гродно, Могилёв, Витебск + Минская область)
- Выбор категории (Транспорт, Электроника, Недвижимость и т.д.)
- Поиск по ключевым словам
- Список активных фильтров с переключателем вкл/выкл
- Удаление фильтров

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Проверка работы |
| GET | `/cities` | Список городов |
| GET | `/categories` | Список категорий |
| POST | `/filters` | Добавить фильтр `{"city":"minsk","category":"electronics","query":"iPhone"}` |
| GET | `/filters` | Список фильтров |
| PUT | `/filters/{id}/toggle` | Вкл/выкл фильтр `{"active":true}` |
| DELETE | `/filters/{id}` | Удалить фильтр |
| GET | `/stats` | Статистика |

## Структура

```
backend/
├── main.py          # FastAPI сервер + планировщик
├── parser.py        # Парсер kufar.by
├── notifier.py      # Telegram-уведомления
├── db.py            # База данных (SQLite)
├── config.py        # Настройки из .env
├── static/
│   └── index.html   # Веб-интерфейс
├── requirements.txt
└── .env
```

## Архитектура

```
Планировщик (60с)
    ↓
Parser (kufar.by → HTML → JSON)
    ↓
Сравнение с БД (SQLite)
    ↓
Новые объявления → Telegram Bot API
```
