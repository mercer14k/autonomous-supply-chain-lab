FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY apps/api ./apps/api
COPY data/sample ./data/sample
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 lab
USER lab
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--limit-concurrency", "32"]
