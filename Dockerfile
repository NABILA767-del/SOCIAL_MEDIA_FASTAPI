
FROM python:3.11-slim


RUN groupadd -r appuser && useradd -r -g appuser appuser


WORKDIR /app


COPY main.py database.py utils.py schemas.py models.py relationships.py routers/ ./routers/


RUN pip install --no-cache-dir fastapi uvicorn sqlalchemy pydantic python-multipart


EXPOSE 8000


USER appuser


ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]