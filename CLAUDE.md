# BasketLab — contexto para Claude
Doc solo para Claude: terso, sin duplicar el código. Humanos: [README.md](README.md).

## Identidad
Analizador de estadísticas de baloncesto (ligas españolas FEB / FBCYL) + motor de partido en vivo (FEB, alertas y propuestas para el staff).
**Stack:** Python 3.11 · FastAPI · MongoDB (pymongo, síncrono) · matplotlib · fpdf2 · python-docx · scikit-learn (modelos predictivos) | React 18 + Vite + TypeScript + TanStack Query | Render (API + scraper) y Vercel (frontend). Fase PoC (LF2).
Sin LLMs externos (eliminados): los informes automáticos serán por reglas, ver [docs/ROADMAP.md](docs/ROADMAP.md).

## Mapa de documentación (leer cuando…)
| Doc | Léelo cuando |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | toques capas, routers, servicios, despliegue, config/env |
| [docs/DATA_FORMATS.md](docs/DATA_FORMATS.md) | parseas FEB/FBCYL, play-by-play, SHOTCHART, campos |
| [docs/LIVE.md](docs/LIVE.md) | `src/live_core`, `live_prep`, `pbp`, scraper en vivo, vectores Pyodide |
| [docs/TESTING.md](docs/TESTING.md) | escribes/ejecutas tests, CI, cobertura, checklist manual |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Render/Vercel, variables de entorno, `ADMIN_API_KEY` (guía para activarla), errores 401/503 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | fases, pendientes, deuda técnica, límites conocidos |

## ❌ TDD ES OBLIGATORIO — NUNCA SALTAR ESTE PASO
> **Si modificas código sin haber escrito antes el test que falla → PARA. Escribe el test primero.**

Ciclo rojo→verde (sin excepciones, incluye bugfixes):
1. `tests/test_<feature>.py` — test que describe el comportamiento deseado
2. `pytest -v tests/test_<feature>.py` — confirmar que **falla** (rojo)
3. Implementar el mínimo código que lo corrija
4. `pytest -v tests/test_<feature>.py` — confirmar que **pasa** (verde)
5. Ningún PR / commit sin este ciclo

Evitar: arreglar un bug sin test de regresión previo · añadir feature y tests después · "es un fix pequeño" (**no existe fix pequeño sin test**).
**Bug fix → test de regresión** (`test_<síntoma>_regression` o bug documentado en el docstring) que reproduce el fallo exacto, pasa solo con el fix y va en el mismo commit.

## Reglas de implementación
- **Infer > ask**: "añade export" = CSV/PNG/PDF. **Follow patterns**: busca código similar antes de crear. **Adapt > duplicate** (si hay 80 % de coincidencia, extiende). **DRY**. Usa librerías (numpy/scipy/pandas, requests) en vez de reinventar.
- **Dual format**: siempre FEB + FBCYL (`is_fbcyl`, ver DATA_FORMATS).
- **Código y comentarios en inglés; textos de UI en español.**
- **Preguntar solo por**: umbrales de lógica de negocio, alcance ambiguo, preferencias de layout.
- **Testing tras features**: plan (camino feliz + bordes + errores) → ejecutar → suite completa. Checklist: sin excepciones · bordes (vacío/None/cero) · FEB+FBCYL · sin regresiones.

## Calidad (antes de escribir y cada ~100 líneas)
| Comprobación | Umbral | Acción |
|---|---|---|
| Líneas del archivo | >300 aviso · >500 **parar** | extraer módulo/helper **ahora** |
| Longitud de función | >40 | dividir antes de seguir |
| Duplicación | similar existente | reutilizar/extraer helper |
| Anidación / condicionales | >3 niveles o >5 | refactorizar |
**Refactor ANTES, no después.** Si el archivo ya supera límites, no añadas código sin avisar: *"Antes de implementar X, [archivo] tiene [problema]. ¿Procedo con 1) refactor + feature (recomendado) 2) solo feature (deuda) 3) solo refactor?"*

## Backlog = GitHub Issues
El usuario añade ahí necesidades y bugs de pruebas manuales. **Antes de proponer o elegir la siguiente tarea**: `gh issue list --state open --json number,title,labels,createdAt` (y `gh issue view N` de los candidatos); prioridad: `bug` > bloqueantes del trabajo en curso > resto; avisa si hay issues nuevos. Referencia el issue en rama/commit/PR (`Closes #N`) y ciérralo al integrar. **Épicas** (`gh issue list --label epic`; sub-issues de GitHub + etiquetas `area:*`): una funcionalidad no está resuelta hasta cerrar todos sus sub-issues; no saltes a otra épica sin cerrar la activa (se puede aplazar a una épica `deferred` si se acuerda). Nuevo hallazgo propio → crear issue en vez de apuntarlo en docs.

## Flujo git
`git fetch && git checkout main && git merge --ff-only origin/main` **antes de crear cualquier rama**; una rama por PR, independiente. `main` protegido: solo PRs. **Un bloque de funcionalidad = un único PR.** Si hay que dividir, no abras el siguiente mientras haya PRs pendientes que toquen los mismos ficheros (sobre todo `docs/*` y `CLAUDE.md`): encadena o espera a la integración para evitar conflictos. Commit/push solo cuando se pide. Pie de commit: `Co-Authored-By: Claude …`. Ver también [docs/TESTING.md](docs/TESTING.md) para CI.

## Definición de hecho (sincronizar docs — obligatorio)
Antes de dar una entrega por terminada y del commit/PR, revisa y **actualiza** (y borra lo que ya no sea cierto) los docs afectados. `tests/test_docs_consistency.py` lo hace cumplir en parte (paquetes, routers y módulos live sin documentar fallan).
| Si cambias… | actualiza |
|---|---|
| router/endpoint, servicio, paquete `src/*`, despliegue, env | docs/ARCHITECTURE.md |
| esquema FEB/FBCYL, campo verificado, convención de cálculo | docs/DATA_FORMATS.md |
| `src/live_core`, `live_prep`, `pbp`, scraper en vivo, vectores | docs/LIVE.md |
| tests, CI, cobertura, fixtures | docs/TESTING.md |
| una fase hecha/nueva, deuda, límite conocido | docs/ROADMAP.md |
| regla de trabajo, comando, decisión | este archivo (mantenerlo ≤ ~170 líneas; el detalle va a docs/) |

## Arquitectura (resumen; detalle en ARCHITECTURE)
- **UI → API → Servicio → Repositorio → MongoDB.** El frontend nunca toca la BD. Consultas complejas = aggregation pipelines (no filtrar en Python).
- Backend `src/api` (FastAPI :8000, `run_api.py`) + servicio scraper aparte (`src/api/scraper_app.py`, `run_scraper.py`). Frontend `frontend/` (Vite :5173).
- Visualización: matplotlib → PNG bytes por la API. Sync `pymongo` (decisión tomada).

## Patrones obligatorios
```python
@router.get("/example/{collection}")
def get_example(collection: str, db: MongoDBHandler = Depends(get_db)):
    return MyService(db).get_data(collection)
```
- **Endpoints de escritura** (borrar, ingerir, entrenar, persistir): `dependencies=[Depends(require_admin)]` (`src/api/security.py`); si es solo cómputo, añádelo conscientemente a `PUBLIC_WRITE_ROUTES` en `tests/test_admin_auth.py`.
- Operaciones largas: `BackgroundTasks`, nunca bloquear el event loop. Imports perezosos (`from src.services.x import X` dentro de la función) para dependencias pesadas opcionales.
- **MongoDB**: NUNCA `list(col.find({}))` y filtrar en Python → filtra en BD / `AggregationPipelineBuilder`. Índices siempre `background=True` y registrados en `IndexManager`.
- **Posesiones**: `FGA - ORB + TOV + 0.44*FTA`; normalizar `(stat/posesiones)*40`.
- **Cuartiles**: Q1 verde … Q4 rojo, `reverse=True` para pérdidas/faltas.

## Pitfalls
| ❌ No | ✅ Sí |
|---|---|
| asumir FEB (`PLAYER[0]["points"]`) | comprobar `is_fbcyl` (FEB `points`, FBCYL `PTS`) |
| `create_index("f")` | `create_index("f", background=True)` |
| ruta de credenciales fija | `get_mongodb_connection_string()` (`src/database/db_config.py`: env → `db_credentials.txt`) |
| `import src.x` y `import x` mezclados | usa siempre `src.…` |
| texto de UI en inglés | UI en español |

## Decisiones tomadas (no re-debatir)
MongoDB (no SQL) · aggregation pipelines (no ORM) · fpdf2 + python-docx · matplotlib (precisión FIBA) · pymongo síncrono · FastAPI + React/Vite · motor live en biblioteca estándar ejecutado en la tablet con Pyodide (ver LIVE) · sin LLMs.

## Lógica de negocio
- **Cuartiles (Mongo 7+)**: `{"$percentile": {"input": "$m", "p": [0.25], "method": "approximate"}}`.
- **Tendencias**: ⇈ >10 % (#006400) · ↑ 5-10 % (#28a745) · ≈ <5 % (#6c757d) · ↓ 5-10 % (#fd7e14) · ⇊ >10 % (#dc3545).
- **Four Factors**: eFG%=`(FGM+0.5·3PM)/FGA` · TOV%=`TOV/(FGA+0.44·FTA+TOV)` · ORB%=`ORB/(ORB+DRB_rival)` · FTr=`FTA/FGA`. Pesos de Oliver 40/25/20/15 (live).
- **Zonas de tiro (10)**: aro, zona (pintura), 3 de media distancia, esquinas, alas, centro del arco.

## Comandos
```bash
python run_api.py                    # API :8000 (BASKETLAB_DEV=1 → reload)
python run_scraper.py                # servicio scraper
cd frontend && npm run dev           # Vite :5173
pytest -q                            # backend (CI: requirements.txt)
cd frontend && npm run lint && npm run type-check && npm run test:run && npm run build
python tests/live_vectors/generate.py  # regenerar vectores tras cambiar live_core
python -m src.live_core.fake_feb --speed 30   # FEB simulado
cd apps/live-android && npm ci && npm run test:run   # app live: tests con Pyodide real (e2e: npm run e2e)
# creds: MONGODB_CONNECTION_STRING o src/database/db_credentials.txt · ejemplo en .env.example
```
