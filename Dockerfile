FROM python:3.14-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY ./pyproject.toml /code/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

COPY ./main.py /code/main.py
COPY ./src /code/src
COPY ./alembic /code/alembic
COPY ./alembic.ini /code/alembic.ini

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
