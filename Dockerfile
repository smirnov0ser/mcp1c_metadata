# Используем официальный облегченный образ Python.
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера.
WORKDIR /app

# Базовые переменные окружения для Python и пути для метаданных/логов.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    INPUT_METADATA_DIR=/app/metadata_src \
    DIST_METADATA_DIR=/app/metadata_dist \
    LOG_DIR=/app/logs

# Копируем файл с зависимостями, устанавливаем их и создаем необходимые каталоги.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения в контейнер.
COPY . .

# Определяем тома для входных/выходных метаданных и логов.
VOLUME [$INPUT_METADATA_DIR, $DIST_METADATA_DIR, $LOG_DIR]

# Указываем порт, который слушает приложение (если это веб-сервис).
EXPOSE 8000

# Приложение запускается от root.
USER root

# Команда для запуска приложения.
CMD ["python", "src/main.py"]