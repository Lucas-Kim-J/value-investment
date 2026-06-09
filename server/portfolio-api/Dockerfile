# Portfolio input API — used for local dev (docker-compose) and as a reference
# for the server install. Production runs the same app.py via setup-api.sh (venv).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8787
CMD ["gunicorn", "-w", "2", "--timeout", "300", "-b", "0.0.0.0:8787", "app:app"]
