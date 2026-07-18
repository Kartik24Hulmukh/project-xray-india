FROM python:3.13-slim-bookworm

WORKDIR /app

# Install available security patches for OS packages
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -r -u 10001 app && mkdir -p /app/data/uploads && chown -R app:app /app
USER app
ENV PORT=8080 DB_PATH=/app/data/project_xray.db
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["python3", "app/server.py"]
