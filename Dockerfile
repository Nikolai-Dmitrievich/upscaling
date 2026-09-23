FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxcb1 \
    libgomp1 \
    libgl1 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .


FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxcb1 \
    libgomp1 \
    libgl1 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --from=builder /app /app

ENV PATH="/opt/venv/bin:$PATH"

RUN useradd -m -u 1000 app && \
    chown -R app:app /app /opt/venv

USER app

EXPOSE 5001

CMD ["python", "-m", "app.main"]