FROM python:3.12-slim
WORKDIR /app
COPY services/gateway3pl/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/gateway3pl/ .
COPY pkg /app/pkg
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
