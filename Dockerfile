FROM python:3.11.8-slim-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxcb1 \
    libgomp1 \
    libgl1-mesa-glx \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

FROM python:3.11.8-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxcb1 \
    libgomp1 \
    libgl1-mesa-glx \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
RUN mkdir -p files && \
    useradd -m -u 1000 app && \
    chown -R app:app /app /usr/local
USER app

CMD ["python", "/app/app.py"]