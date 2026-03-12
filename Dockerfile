# Slim Python image to keep container memory low
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sensor_service.py .

EXPOSE 8000

CMD ["python", "sensor_service.py"]
