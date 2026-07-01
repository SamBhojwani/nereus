# Backend image for Hugging Face Spaces (Docker SDK).
# HF routes external traffic to port 7860 (matches app_port in README.md front-matter).
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (see .dockerignore for what's excluded — .env, tests, venv, etc.)
COPY . .

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
