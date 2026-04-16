# IVR Tester API

Backend del proyecto IVR Tester. Motor de orquestación de pruebas automatizadas para IVRs en Genesys Cloud, construido con **FastAPI** y **Arquitectura Hexagonal**.

## Prerrequisitos

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — gestor de entornos y dependencias

## Instalación

```bash
# 1. Clonar el repositorio y entrar a la carpeta del backend
cd ivr-tester-api

# 2. Instalar dependencias y crear el entorno virtual
uv sync
```

## Variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con los valores reales de Supabase, Twilio y Deepgram
```

| Variable              | Descripción                                         |
| --------------------- | --------------------------------------------------- |
| `SUPABASE_URL`        | URL del proyecto en Supabase                        |
| `SUPABASE_KEY`        | Clave anon o service role de Supabase               |
| `SUPABASE_DB_URL`     | Cadena de conexión PostgreSQL de Supabase           |
| `TWILIO_ACCOUNT_SID`  | Account SID de Twilio                               |
| `TWILIO_AUTH_TOKEN`   | Auth Token de Twilio                                |
| `TWILIO_PHONE_NUMBER` | Número de teléfono comprado en Twilio               |
| `DEEPGRAM_API_KEY`    | API Key de Deepgram                                 |
| `APP_ENV`             | Entorno de ejecución (`development` / `production`) |
| `APP_PORT`            | Puerto del servidor (default: `8000`)               |

## Migraciones de base de datos (Alembic)

El esquema de base de datos está gestionado con **Alembic** + **SQLAlchemy**. Los modelos viven en `src/infrastructure/database/models/`.

```bash
# Aplicar todas las migraciones pendientes (primera vez o después de un pull)
uv run alembic upgrade head

# Ver el estado actual de las migraciones
uv run alembic current

# Crear una nueva migración automáticamente al modificar un modelo
uv run alembic revision --autogenerate -m "descripcion_del_cambio"

# Revertir la última migración
uv run alembic downgrade -1
```

> **Requisito:** El archivo `.env` debe existir con `SUPABASE_DB_URL` apuntando a la **conexión directa** de Supabase (puerto `5432`, no el pooler en `6543`).

## Arrancar el servidor

### Desarrollo local

```bash
uv run uvicorn main:app --reload --port 8000
```

- API disponible en: `http://localhost:8000`
- Documentación interactiva (Swagger): `http://localhost:8000/docs`
- Health check: `GET http://localhost:8000/api/v1/health`

## Docker

### Build de la imagen

La imagen está optimizada usando **multistage build** para minimizar tamaño final (excluye tests, dependencias de desarrollo y herramientas de compilación).

```bash
# Buildear imagen desde ivr-tester-api/
docker build -t ivr-tester-api:latest .

# Ver layers y tamaño de la imagen
docker image ls ivr-tester-api:latest
docker history ivr-tester-api:latest
```

### Ejecutar el contenedor

```bash
# Copiar variables de entorno
cp .env.example .env
# ... editar .env con valores reales ...

# Ejecutar contenedor con variables de entorno
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  ivr-tester-api:latest
```

Valida que la API está respondiendo:
```bash
curl http://localhost:8000/api/v1/health
```

### Migraciones de base de datos en Docker

⚠️ **Importante:** Las migraciones se ejecutan **fuera del contenedor API**, como paso previo.

```bash
# Ejecutar migraciones antes de levantar la API
docker run --rm \
  --env-file .env \
  ivr-tester-api:latest \
  alembic upgrade head

# Ver estado actual de migraciones
docker run --rm \
  --env-file .env \
  ivr-tester-api:latest \
  alembic current
```

### Con Docker Compose (opcional)

Para un flujo local más simple con gestión integrada de variables de entorno:

```bash
# 1. Copiar el ejemplo y completar variables
cp .env.example .env

# 2. Ejecutar con compose (archivo no incluido, crear si necesitas)
# docker-compose up

# 3. Acceder a la API
# curl http://localhost:8000/api/v1/health
```

## Tests Automatizados

### Ejecutar todos los tests

```bash
# Ejecutar todos los tests con reporte detallado
uv run pytest tests/ -v

# Ejecutar todos los tests en modo quiet (resumen)
uv run pytest tests/ -q

# Ejecutar con cobertura
uv run pytest tests/ --cov=src
```

### Ejecutar tests específicos

```bash
# Solo tests unitarios de JWT
uv run pytest tests/test_auth_jwt.py -v

# Solo tests de endpoints
uv run pytest tests/test_auth_endpoints.py -v

# Test específico
uv run pytest tests/test_auth_jwt.py::TestVerifySupabaseToken::test_valid_token -v
```

```

## Estructura del proyecto

```

ivr-tester-api/
├── main.py # Entry point de Uvicorn
├── pyproject.toml # Dependencias y configuración
├── alembic.ini # Configuración de Alembic
├── .env.example # Variables de entorno de ejemplo
├── alembic/
│ ├── env.py # Configuración de conexión y metadata
│ └── versions/ # Archivos de migración versionados
├── src/
│ ├── domain/ # Entidades y contratos (interfaces)
│ ├── application/ # Casos de uso y servicios
│ ├── infrastructure/ # Adaptadores externos (DB, Twilio, Deepgram)
│ │ ├── config.py # Configuración centralizada (pydantic-settings)
│ │ └── database/
│ │ ├── base.py # DeclarativeBase compartida
│ │ └── models/ # Modelos SQLAlchemy (una entidad por archivo)
│ └── presentation/ # API REST (routers FastAPI)
│ └── api/v1/
│ └── health.py # GET /api/v1/health
└── tests/ # Pruebas automatizadas

````

## Comandos útiles

```bash
# Verificar linting
uv run ruff check src/ main.py

# Corregir errores automáticamente
uv run ruff check src/ main.py --fix

# Formatear código
uv run ruff format src/ main.py
````
