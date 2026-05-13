# FastAPI Spring Style

Proyecto base en Python con arquitectura por capas tipo Spring:

- API (controllers)
- Services
- Repositories
- Components (clientes externos)
- Inyeccion de dependencias
- Integracion con AWS S3
- Persistencia en MongoDB y cache en Redis
- Docker y docker-compose

## Estructura

```text
app/
  api/
  components/
  core/
  repositories/
  schemas/
  services/
resources/
```

## Ejecutar con Docker

1. Copia `.env.example` a `.env`.
2. Ejecuta:

```bash
docker compose up --build
```

## Endpoints principales

- `GET /api/v1/health`
- `POST /api/v1/files` (sube archivo a S3 y guarda metadata)
- `GET /api/v1/files/{file_id}`
