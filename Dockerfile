# Dukaan Dost backend as a container: for Nebius Serverless Endpoints / Jobs (optional; Render doesn't need it).
#   Build:  docker build -t <your-dockerhub-name>/dukaan-dost:1 .
#   Run:    docker run -p 8000:8000 --env-file backend/.env <your-dockerhub-name>/dukaan-dost:1
# Secrets are NOT baked in: pass them as environment variables when the container starts.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY sample_data/ /app/sample_data/

EXPOSE 8000
# Endpoint (default): the API.   Job: override the command with  python daily_report.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
