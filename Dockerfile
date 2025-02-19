# Используем официальный Python-образ
FROM python:3.11

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы приложения
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт 8000
EXPOSE 8000

# Запуск FastAPI-приложения
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
