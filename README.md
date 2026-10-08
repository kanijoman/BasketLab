# BasketLab

Analizador de estadísticas de baloncesto (ligas FEB y FBCYL): API FastAPI + frontend React/Vite + MongoDB, con motor de partido en vivo (`src/live_core`).

Documentación técnica (para desarrollo asistido): [CLAUDE.md](CLAUDE.md) y [docs/](docs/ARCHITECTURE.md).

## Arrancar
```bash
pip install -r requirements.txt
python run_api.py              # API en :8000 (Swagger en /docs)
cd frontend && npm ci && npm run dev   # frontend en :5173
```
Conexión a MongoDB: variable `MONGODB_CONNECTION_STRING` o `src/database/db_credentials.txt` (no versionado).

## Tests
```bash
pytest -q
cd frontend && npm run type-check && npm run test:run
```

## Despliegue
Render (`render.yaml`: API y scraper) y Vercel (frontend). Variables en `.env.example`.
