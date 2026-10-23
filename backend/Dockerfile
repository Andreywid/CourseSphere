FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The app reads ./config.json, ./credentials.json and query_types.json relative to the working directory.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["flask", "--app", "endpoints", "run", "--host", "0.0.0.0", "--port", "5000"]
