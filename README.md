# Image Upscaler

Веб-приложение для увеличения разрешения изображений с использованием OpenCV и EDSR.

## Возможности

- **Два режима апскейла:**
  - OpenCV (быстро, базовое качество)
  - EDSR (медленнее, высокое качество)
- **Асинхронная обработка** через Celery + Redis
- **Ограничение размера файла** — 50 MB
- **MIME-валидация** загружаемых файлов
- **Docker-контейнеризация**

## Требования

- Docker + Docker Compose
- Python 3.11+ (для локальной разработки)

## Быстрый старт

```bash
docker-compose up --build
```

Приложение доступно по адресу: **http://localhost:5002**

## Локальная разработка

```bash
# Создать окружение
python -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Запустить Redis (требуется)
docker run -d -p 6379:6379 redis:alpine

# Запустить Flask
python app.py

# Запустить Celery worker
celery -A tasks worker --loglevel=info
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PORT` | 5001 | Порт Flask |
| `HOST` | 0.0.0.0 | Хост Flask |
| `DEBUG` | False | Режим отладки |
| `CELERY_BROKER_URL` | redis://redis:6379/0 | URL брокера Celery |
| `CELERY_RESULT_BACKEND` | redis://redis:6379/1 | URL бэкенда результатов |

## API

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/` | Главная страница |
| POST | `/upscale` | Загрузка изображения |
| GET | `/upscale/<task_id>` | Получение результата |
| GET | `/result/<task_id>` | Страница статуса задачи |

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│   Flask     │────▶│    Redis    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Celery    │◀────│    Redis    │
                    │   Worker    │     └─────────────┘
                    └─────────────┘
```

## Структура проекта

```
.
├── app.py              # Flask приложение
├── tasks.py            # Celery задачи
├── upscale.py          # Логика апскейла
├── requirements.txt    # Python зависимости
├── Dockerfile          # Docker образ
├── docker-compose.yaml # Оркестрация сервисов
├── templates/          # HTML шаблоны
└── models/             # Модели EDSR
```

## Ограничения

- Максимальный размер файла: **50 MB**
- Поддерживаемые форматы: **JPG, PNG, GIF, WEBP**
- Коэффициент увеличения: **2x**

