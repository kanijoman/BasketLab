# BasketLab

Analizador de estadísticas de baloncesto (ligas FEB y FBCYL): frontend React/Vite sobre ficheros publicados + MongoDB, con motor de partido en vivo (`src/live_core`).

Documentación técnica (para desarrollo asistido): [CLAUDE.md](CLAUDE.md) y [docs/](docs/ARCHITECTURE.md).

## Arrancar
```bash
pip install -r requirements.txt
cd frontend && npm ci && npm run dev   # frontend en :5173
```
Conexión a MongoDB: variable `MONGODB_CONNECTION_STRING` o `src/database/db_credentials.txt` (no versionado).

## Tests
```bash
pytest -q
cd frontend && npm run type-check && npm run test:run
```

## Despliegue
Vercel (frontend); los datos y los paquetes los publica GitHub Actions en las ramas `web-data` y `live-packages`. No hay servidor de API: se eliminó (#1199). Variables en `.env.example`.
