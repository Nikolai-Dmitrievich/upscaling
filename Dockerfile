FROM python:3.11.8-slim-bookworm
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxcb1 \
    libgomp1 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD sh -c "python celery_app.py & celery -A celery_app:celery_app worker --loglevel=info & tail -f /dev/null"
