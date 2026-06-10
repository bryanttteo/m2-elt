FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py index.html ./

ENV PORT=8080
EXPOSE 8080

# Single worker is plenty; threads let the per-target probes run concurrently.
CMD ["sh", "-c", "gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 app:app"]
