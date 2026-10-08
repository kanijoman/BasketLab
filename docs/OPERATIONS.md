# Operaciones: despliegue y clave de administración
Léelo cuando toques Render/Vercel, variables de entorno o veas un 401/503 en Admin, scrape, ingesta o entrenamiento. Arquitectura general: [ARCHITECTURE.md](ARCHITECTURE.md).

## Estado actual (decisión consciente)
`ADMIN_API_KEY` **no está definida en producción**, a propósito: la aplicación no es pública y se prefiere que esas rutas queden cerradas. Consecuencia en Render (`ENVIRONMENT=production`):

| Funciona | Responde **503** ("ADMIN_API_KEY no está configurada en el servidor") |
|---|---|
| Todas las lecturas (equipos, jugadores, tiros, informes, rankings, rotaciones…) | `DELETE /api/v1/collections/{name}` (borrar colección) |
| Cómputo sin persistir: informe de equipo, export PDF, informe semanal, Monte Carlo, predicción de partido | `POST /api/v1/scrape/start` (descargar competiciones) |
| | `POST /api/v1/historical/ingest` y `/ingest_competition` |
| | `POST /api/v1/analysis/elasticity/train` y `/train/stream` (entrenar modelos) |

El 503 es el comportamiento diseñado, no un fallo (`src/api/security.py`, probado en `tests/test_admin_auth.py`). En **local** (sin `ENVIRONMENT=production`) esas rutas están abiertas y no hace falta clave.

Para cargar o refrescar datos mientras la clave no exista: ejecutar la API/scraper en local (`python run_api.py`) con `MONGODB_CONNECTION_STRING` apuntando a la misma base de Atlas; en local no hay guarda.

## Activar la clave (paso a paso)
Hacerlo cuando se quiera usar Admin, scrape, ingesta o entrenamiento en producción.

1. **Generar una clave larga y aleatoria** (en cualquier terminal; no la pegues en el chat ni la commitees):
   - PowerShell: `[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))`
   - o Python: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   Guárdala en un gestor de contraseñas.
2. **Render → servicio `basketlab-api` → Environment**: añadir `ADMIN_API_KEY` = la clave. Guardar.
3. **Render → servicio `basketlab-scraper` → Environment**: añadir `ADMIN_API_KEY` con **exactamente el mismo valor** (el scraper tiene su propia guarda: el frontend envía la misma clave a ambos).
4. **Redeploy** de los dos servicios (Render los reinicia al guardar variables; si no, *Manual Deploy → Deploy latest commit*). Los servicios gratuitos tardan en despertar.
5. **Introducir la clave en la app**: página **Admin** → campo "Clave de administración" → *Guardar*. Se guarda solo en esa sesión del navegador (`sessionStorage`); al cerrar la pestaña hay que volver a ponerla.
6. **Comprobar** (sustituye URL y clave):
   ```bash
   # sin clave -> 401
   curl -i -X DELETE https://<api>.onrender.com/api/v1/collections/PRUEBA_INEXISTENTE
   # con clave -> pasa la guarda (404/200 según exista la colección, pero ya no 401/503)
   curl -i -X DELETE -H "X-Admin-Key: <clave>" https://<api>.onrender.com/api/v1/collections/PRUEBA_INEXISTENTE
   ```
   Cuidado: usa un nombre de colección que **no exista** al probar.

## Rotar o retirar la clave
- **Rotar**: cambiar el valor en los dos servicios de Render, redeploy y volver a guardarla en Admin. Las claves antiguas dejan de valer al instante (se lee en cada petición).
- **Retirar** (volver al estado actual): borrar la variable en ambos servicios y redeploy → vuelven los 503.

## Diagnóstico
| Síntoma | Causa | Solución |
|---|---|---|
| 503 "ADMIN_API_KEY no está configurada" | variable sin definir en ese servicio (producción) | Estado actual esperado; pasos de arriba para activarla |
| 401 "Clave de administración requerida o incorrecta" | sin clave en Admin, clave distinta o variable distinta entre `api` y `scraper` | Re-guardar la clave en Admin; comprobar que el valor es idéntico en ambos servicios |
| CORS / `OPTIONS` bloqueado | `ALLOWED_ORIGINS` no incluye la URL de Vercel | Ajustar `ALLOWED_ORIGINS` (la cabecera `X-Admin-Key` está permitida) |
| Funciona en local pero no en producción | en local no hay guarda (sin `ENVIRONMENT=production`) | Esperado |

## Variables de entorno (resumen)
Backend (Render): `ENVIRONMENT=production`, `MONGODB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `ADMIN_API_KEY` (opcional hasta que se decida activarla), `DISABLE_SCRAPING=1` (solo api). Frontend (Vercel): `VITE_API_BASE`, `VITE_SCRAPER_BASE`. Plantilla: `.env.example`.

## Futuro
La gestión real de usuarios y roles (sustituir la clave única) está planificada y aplazada en la épica #153.
