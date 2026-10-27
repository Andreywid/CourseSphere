FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The app reads ./config.json, ./credentials.json and query_types.json relative to the working directory.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user. The mounted config.json/credentials.json are world-readable (0644),
# so this user can read them without changing the volume ownership.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 5000

# Servidor WSGI; 1 worker por instância, a escala é por mais instâncias atrás do Nginx.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "endpoints:app"]
