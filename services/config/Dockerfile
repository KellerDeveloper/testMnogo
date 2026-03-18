FROM python:3.12-slim
WORKDIR /app
COPY services/config/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/config/ .
COPY pkg /app/pkg
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
