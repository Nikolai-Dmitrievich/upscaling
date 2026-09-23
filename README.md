# Image Upscaler

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking: MyPy](https://img.shields.io/badge/types-mypy-000000.svg)](https://mypy.readthedocs.io/)

A production-ready, asynchronous image upscaling microservice built with **Flask**, **Celery**, **Redis**, and **OpenCV/EDSR**.

## Features

- **Dual Upscaling Modes**: 
  - *Fast Mode*: OpenCV Bicubic interpolation (~0.1s).
  - *High-Quality Mode*: EDSR (Enhanced Deep Super-Resolution) x2 neural network.
- **Asynchronous Processing**: Non-blocking task execution via Celery + Redis, with client-side status polling.
- **Robust Validation**: Deep MIME-type inspection using `python-magic` (prevents extension spoofing) and strict file size/dimension limits.
- **Resource Protection**: Safeguards against OOM (Out-Of-Memory) by capping input resolution and file size before processing.
- **Production-Ready Docker**: Multi-stage builds, healthchecks, read-only volumes, and non-root user execution.
- **High Test Coverage**: 94% coverage with isolated unit and integration tests (`pytest`), enforced by `ruff` and `mypy`.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development without Docker)

## Quick Start (Docker)

1. Clone the repository and navigate to the project directory.
2. Initialize the environment file:
   ```bash
   cp .env.example .env
   ```
   *(Optional: Edit `.env` to change limits or the secret key).*
3. Build and start the services:
   ```bash
   docker compose up --build
   ```
4. Open your browser and go to: **http://localhost:5002**

## Local Development

If you prefer to run the services locally without Docker:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install the project and development dependencies
pip install -e ".[dev]"

# 3. Start a local Redis instance
docker run -d -p 6379:6379 redis:alpine

# 4. Start the Flask application (Terminal 1)
python -m app.main

# 5. Start the Celery worker (Terminal 2)
celery -A app.tasks.celery_app worker --loglevel=info
```

### Testing & Linting

The test suite runs independently of a real Redis instance by utilizing Celery's `task_always_eager` mode.

```bash
# Linting and formatting check
ruff check app && ruff format --check app

# Static type checking
mypy app

# Run tests with coverage report
pytest --cov=app --cov-report=term-missing
```

## Environment Variables

A complete list of variables is available in `.env.example`.

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` / `PORT` | `0.0.0.0` / `5001` | Flask server binding address |
| `DEBUG` | `False` | Enable Flask debug mode |
| `SECRET_KEY` | *(dev placeholder)* | Session encryption key (must be changed in production) |
| `MAX_FILE_SIZE_MB` | `20` | Maximum allowed uploaded file size |
| `MAX_IMAGE_DIMENSION` | `4000` | Maximum allowed dimension (width or height) of the input image |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery message broker URL |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result storage URL |
| `EDSR_MODEL_PATH` | `models/EDSR_x2.pb` | Path to the EDSR neural network weights |

> **💡 Note on Resource Limits:** `MAX_FILE_SIZE_MB` and `MAX_IMAGE_DIMENSION` are critical safeguards. Image pixel buffers expand significantly in RAM. Without dimension limits, a single 40MP image could consume several gigabytes of memory on the worker, leading to OOM crashes.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main HTML upload page |
| `POST` | `/upscale` | Uploads file, validates it, and returns a `302 Redirect` to the result page |
| `GET` | `/upscale/<task_id>` | Returns JSON status of the background task (used for polling) |
| `GET` | `/result/<task_id>` | HTML page displaying the task status and the final image (if successful) |
| `GET` | `/health` | Liveness probe for Docker/compose healthchecks |

## Architecture

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│   Flask     │────▶│    Redis    │
│  (polling)  │◀────│  (Web API)  │────▶│ (Broker)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                        ┌──────▼──────┐
                                        │   Celery    │
                                        │   Worker    │──▶ OpenCV / EDSR
                                        └─────────────┘
```

## Project Structure

```text
upscaling/
├── app/
│   ├── main.py                  # Application factory, entry point
│   ├── api/
│   │   └── views.py             # HTTP route handlers
│   ├── core/
│   │   ├── config.py            # Pydantic V2 settings management
│   │   └── validator.py         # MIME and size validation logic
│   ├── services/
│   │   └── image_processor.py   # Core OpenCV / EDSR upscaling logic
│   ├── tasks/
│   │   ├── celery_app.py        # Celery application instance
│   │   └── worker.py            # Background task definitions
│   └── templates/               # Jinja2 HTML templates
├── tests/                       # Pytest unit and integration tests
├── models/                      # EDSR model weights (mounted as read-only volume)
├── docker-compose.yaml          # Service orchestration
├── Dockerfile                   # Multi-stage production build
├── pyproject.toml               # Dependencies, ruff, mypy, pytest configs
└── .env.example                 # Environment variables template
```

## Constraints & Limitations

- **Max File Size**: 20 MB
- **Max Input Resolution**: 4000 px (longest side)
- **Supported Formats**: JPG, PNG, GIF, WEBP
- **Upscaling Factor**: 2x (fixed)
- **Output Format**: Always returned as optimized PNG (Compression level 1)
```