# BasketLab — contexto para Claude
Doc solo para Claude: terso, sin duplicar el código. Humanos: [README.md](README.md).

## Identidad
Analizador de estadísticas de baloncesto (ligas españolas FEB / FBCYL) + motor de partido en vivo (FEB, alertas y propuestas para el staff).
**Stack:** Python 3.11 · FastAPI · MongoDB (pymongo, síncrono) · matplotlib · fpdf2 · python-docx | React 18 + Vite + TypeScript + TanStack Query | Vercel (frontend) y GitHub Actions (datos y paquetes publicados en ramas); **sin Render ni alojamiento de la API en el repositorio**. Fase PoC (LF2).
Sin LLMs externos (eliminados): los informes automáticos serán por reglas, ver [docs/ROADMAP.md](docs/ROADMAP.md).

## Mapa de documentación (leer cuando…)
| Doc | Léelo cuando |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | toques capas, routers, servicios, despliegue, config/env |
| [docs/DATA_FORMATS.md](docs/DATA_FORMATS.md) | parseas FEB/FBCYL, play-by-play, SHOTCHART, campos |
| [docs/LIVE.md](docs/LIVE.md) | `src/live_core`, `live_prep`, `pbp`, scraper en vivo, vectores Pyodide |
| [docs/TESTING.md](docs/TESTING.md) | escribes/ejecutas tests, CI, cobertura, checklist manual |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Vercel, variables de entorno, `ADMIN_API_KEY` (ninguna ruta la usa hoy: patrón para la próxima escritura), errores 401/503 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | fases, pendientes, deuda técnica, límites conocidos |
| [docs/DECISIONS.md](docs/DECISIONS.md) | dudas si algo ya está decidido (no re-debatir): razón, fecha y excepciones |
| [docs/UI.md](docs/UI.md) | toques la UI de la web: componentes base, vocabulario de color, tema |

Los docs no se leen enteros (LIVE ≈ 54k tokens): `grep -n '^#' docs/X.md` da el índice, cada uno empieza con un `## Mapa del documento`, y se lee solo la sección (`Read` con offset/límite). La historia (incidentes, «antes X, ahora Y») vive en `docs/evaluaciones/2026-11-27_historia-*.md`: al documentar, el doc dice lo que **es**.

## ❌ TDD ES OBLIGATORIO — NUNCA SALTAR ESTE PASO
> **Si modificas código sin haber escrito antes el test que falla → PARA. Escribe el test primero.**

Ciclo rojo→verde (sin excepciones, incluye bugfixes):
1. `tests/test_<feature>.py` — test que describe el comportamiento deseado
2. `pytest -v tests/test_<feature>.py` — confirmar que **falla** (rojo)
3. Implementar el mínimo código que lo corrija
4. `pytest -v tests/test_<feature>.py` — confirmar que **pasa** (verde)
5. Ningún PR / commit sin este ciclo
6. El test reproduce el fallo **con el estado más real posible**: la situación se construye jugando eventos con `tests/builders.py` (`Match`), con un partido real o con un fixture de partido raro, no con un dict inventado (puede describir un estado inalcanzable).
7. **Prueba de rojo**: tus tests nuevos (pytest y vitest de la web y de la app) deben fallar con el código de la base. Compruébalo antes del PR: `python scripts/red_proof.py` (compara **commits**: commitea antes; el CI lo repite en cada PR, informativo, job `red-proof`; `scripts/pre_pr.py` lo incluye).

Evitar: arreglar un bug sin test de regresión previo · añadir feature y tests después · "es un fix pequeño" (**no existe fix pequeño sin test**).
**Bug fix → test de regresión** (`test_<síntoma>_regression` o bug documentado en el docstring) que reproduce el fallo exacto, pasa solo con el fix y va en el mismo commit.

## Reglas de implementación
- **Infer > ask**: "añade export" = CSV/PNG/PDF. **Follow patterns**: busca código similar antes de crear. **Adapt > duplicate** (si hay 80 % de coincidencia, extiende). **DRY**. Usa librerías (numpy/scipy/pandas, requests) en vez de reinventar.
- **Dual format**: siempre FEB + FBCYL (`is_fbcyl`, ver DATA_FORMATS).
- **Código y comentarios en inglés; textos de UI en español.**
- **Preguntar solo por**: umbrales de lógica de negocio, alcance ambiguo, preferencias de layout.
- **Esperas largas (CI, workflows, cargas, builds)**: `Monitor` o `run_in_background` con un **latido cada 5 min** (`while …; do sleep 300; echo latido; done` junto al filtro de eventos) y, con cada latido o evento, un mensaje al usuario: estado, qué falta, fallos. Sin evento no hay mensaje: el latido es lo que permite cumplirlo. Nunca `sleep` en primer plano.
- **Testing tras features**: plan guiado por el **checklist de esquinas de docs/TESTING.md** (fronteras de periodo, determinismo y orden, vacío/None/cero, FEB y FBCYL, idempotencia, datos tardíos o corregidos), no «camino feliz + bordes + errores»; sin tests de constantes o defaults sueltos (una tabla `parametrize`), texto exacto solo en las frases críticas, mocks solo en fronteras (red, Mongo). **No lances la suite completa en local** (≈ 6 min): la corre el CI y un fallo ahí se arregla en el mismo PR. Ejecuta solo lo que cubre lo tocado (los tests nuevos y los antiguos del mismo código):

| Tocas… | Ejecuta |
|---|---|
| `src/live_core`, `live_prep`, `pbp` | `pytest --no-cov -n auto tests/test_live_core*.py tests/test_live_prep*.py tests/test_rule_eval*.py tests/test_docs_consistency.py tests/test_live_vectors*.py` (≈ 2 min: la selección por área dejó pasar dos fallos que esta tanda cazó) y, si cambian vectores o paquetes, `cd apps/live-android && npm run test:run`. Tras regenerar vectores, **revisa el diff de `vectors.json`**: solo debe cambiar lo esperado |
| `tests/builders.py` o un helper de tests | los tests que lo usan (`grep -rl`) |
| `frontend/` | `vitest run <ruta>` |
| docs o `CLAUDE.md` | `pytest --no-cov tests/test_docs_consistency.py` |

Checklist: sin excepciones · bordes (vacío/None/cero) · FEB+FBCYL · sin regresiones en lo afectado.

## Calidad (antes de escribir y cada ~100 líneas)
| Comprobación | Umbral | Acción |
|---|---|---|
| Líneas del archivo | >300 aviso · >500 **parar** (excepción, #203: los literales de pipelines de Mongo —`database/aggregation/fbcyl_pipeline.py`, `pipeline_team_stats.py`—, `detailed_zones._create_10_zone_system` y los vectores generados son datos declarativos de baja complejidad: no se parten por líneas; la excepción se revisa si se elimina la API, #641) | extraer módulo/helper **ahora** |
| Longitud de función | >40 | dividir antes de seguir |
| Duplicación | similar existente | reutilizar/extraer helper |
| Anidación / condicionales | >3 niveles o >5 | refactorizar |
**Refactor ANTES, no después.** Si el archivo ya supera límites, no añadas código sin avisar: *"Antes de implementar X, [archivo] tiene [problema]. ¿Procedo con 1) refactor + feature (recomendado) 2) solo feature (deuda) 3) solo refactor?"*

## Backlog = GitHub Issues
El usuario añade ahí necesidades y bugs de pruebas manuales. **Antes de proponer o elegir la siguiente tarea**: `gh issue list --state open --label bug --json number,title,createdAt`, luego `--label epic` y `--search "created:>=AAAA-MM-DD"` desde la última vez (el listado entero son >100 issues ≈ 11k tokens: no lo pidas entero) y `gh issue view N` de los candidatos; prioridad: `bug` > bloqueantes del trabajo en curso > resto; avisa si hay issues nuevos. Referencia el issue en rama/commit/PR (`Closes #N`) y ciérralo al integrar. **Épicas** (`gh issue list --label epic`; sub-issues de GitHub + etiquetas `area:*`): una funcionalidad no está resuelta hasta cerrar todos sus sub-issues; no saltes a otra épica sin cerrar la activa (se puede aplazar a una épica `deferred` si se acuerda). Nuevo hallazgo propio → crear issue en vez de apuntarlo en docs.

## Flujo git
1. Antes de crear rama: `git fetch && git checkout main && git merge --ff-only origin/main`. Una rama por PR, independiente. `main` protegido: solo PRs.
2. **Un bloque de funcionalidad = un único PR**, agrupado por naturaleza (misma épica o área, mismos ficheros: p. ej. varias reglas del motor live): **un commit por issue** (`Closes #N` en cada uno) con su ciclo TDD y la sincronización de docs; propón el bloque antes de empezar y ábrelo al terminarlo entero. Cada PR pasa el CI completo (≈ 10-18 min) y la revisión automática de código (límite de PRs por hora): **pocos PRs, lo más grandes posible**. Antes de abrir uno, recorre los issues abiertos (`gh issue list`) y mete **todos los de su misma naturaleza** (misma épica/área/ficheros, sin mezclar bug con refactor, datos con UI o CI) que no añadan riesgo: sin cambio de contrato o de datos publicados fuera del bloque, sin dependencias de decisiones pendientes y revisables de una vez (~8-12 issues; más, divídelo por área). Lo que no entra se nombra en el PR.
3. No mezcles naturalezas: un bug urgente que bloquea o un cambio de CI van aparte; un cambio de reglas de trabajo o de docs viaja **dentro** del PR del bloque, como un commit más.
4. Si hay que dividir, no abras el siguiente mientras haya PRs pendientes que toquen los mismos ficheros (sobre todo `docs/*` y `CLAUDE.md`): encadena o espera a la integración.
5. **Checklist previa al PR**: `python scripts/pre_pr.py`. Bloquea: rama = main, sin rebase sobre `origin/main`, `ruff check` con errores (el CI rechaza imports sin usar), `test_docs_consistency` en rojo. Avisa: cambios sin commit y prueba de rojo sin rojo. Si el rebase trajo cambios, repite los tests afectados. Que se ejecute solo ante `gh pr create` requiere el hook de docs/TESTING.md («Antes del PR»), que activa el usuario.
6. **Commit, push y PR sin preguntar si no hay ningún PR abierto** (`gh pr list`); con uno abierto, esperar a que se integre o a que se pida. Pie de commit: `Co-Authored-By: Claude …`. PR con código (fuera de `docs/` y `*.md`): tras la primera subida, un solo `@coderabbitai review`; aplicar sus comentarios pertinentes en el mismo PR, sin más rondas; si hay duda, preguntar (OPERATIONS); nunca en PRs solo de docs.
7. Fallo del CI ajeno al código (Chromium, Maven 429, red del runner): `gh run rerun --failed` y una línea al usuario; ni issue ni PR de endurecimiento. Un fallo real se arregla en el mismo PR. Ver [docs/TESTING.md](docs/TESTING.md) para CI.

## Tras integrar un PR: limpieza obligatoria (antes de seguir con nada más)
1. **Git**: `git fetch --prune`, ff de `main`, borrar ramas locales fusionadas (`git branch --merged main`); comprobar que no quedan ramas remotas ni PRs sin integrar (`git branch -r`, `gh pr list`).
2. **Issues**: cerrar los resueltos, comentar los parciales (`Refs #N`), actualizar épicas/sub-issues y ROADMAP/docs si cambió el estado, crear **issues** para hallazgos nuevos o trabajo diferido (no solo en el chat), revisar duplicados/obsoletos y issues nuevos del usuario.
3. **CI en `main`**: `gh run list --branch main` (deploy, vectores, APK); un fallo = arreglo o issue. Si el PR tocó datos de la web, comprobar también el run de `Web data` (se lanza solo, #781; protocolo en OPERATIONS).
4. Resumir al usuario (ramas, issues, CI) y proponer la siguiente tarea.

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
- Backend `src/api` (FastAPI :8000, `run_api.py`; **sin escrituras desde la web desde #724**: los datos los carga el refresco programado del archivo y se retiran con la purga). Frontend `frontend/` (Vite :5173).
- Visualización: matplotlib → PNG bytes por la API. Sync `pymongo` (decisión tomada).

## Patrones obligatorios
```python
@router.get("/example/{collection}")
def get_example(collection: str, db: MongoDBHandler = Depends(get_db)):
    return MyService(db).get_data(collection)
```
- **Endpoints de escritura** (borrar, ingerir, entrenar, persistir; hoy no queda ninguno): `dependencies=[Depends(require_admin)]` (`src/api/security.py`); si es solo cómputo, añádelo conscientemente a `PUBLIC_WRITE_ROUTES` en `tests/test_admin_auth.py`.
- Operaciones largas: `BackgroundTasks`, nunca bloquear el event loop. Imports perezosos (`from src.services.x import X` dentro de la función) para dependencias pesadas opcionales.
- **Memoria (servidor pequeño, 512 MB)**: un documento de partido ≈ 1 MB en RAM. Proyección siempre en colecciones de partidos; iterar cursores/generadores, no listas de documentos o tiros; 1 worker (ver docs/OPERATIONS.md).
- **MongoDB**: NUNCA `list(col.find({}))` y filtrar en Python → filtra en BD / `AggregationPipelineBuilder`. Índices siempre `background=True` y registrados en `IndexManager`.
- **Posesiones**: exactas del tracker único (`src/live_core/possessions.py`, FEB y FBCYL; un partido no fiable por su impacto —más del 10 % de los puntos de origen desconocido o recuento > 10 % de la estimación (`reliable` de `DERIVED`)— usa la estimación `FGA - ORB + TOV + 0.44*FTA`; las roturas de alternancia son solo informativas); ratings por 100 posesiones **reales**, ritmo por 40 min (lo único escalado), Talent por 40 min. Cada partido FEB guarda `DERIVED` (posesiones y rebotes/pérdidas validados) y los pipelines de temporada lo leen con respaldo al boxscore; rellenar lo antiguo con `run_backfill_derived.py` (OPERATIONS). Rebote ofensivo = rebota el equipo que falló, siempre (ver DATA_FORMATS).
- **Cuartiles**: Q1 verde … Q4 rojo, `reverse=True` para pérdidas/faltas.

## Pitfalls
| ❌ No | ✅ Sí |
|---|---|
| asumir FEB (`PLAYER[0]["points"]`) | comprobar `is_fbcyl` (FEB `points`, FBCYL `PTS`) |
| `create_index("f")` | `create_index("f", background=True)` |
| ruta de credenciales fija | `get_mongodb_connection_string()` (`src/database/db_config.py`: env → `db_credentials.txt`) |
| `import src.x` y `import x` mezclados | usa siempre `src.…` |
| texto de UI en inglés | UI en español |
| color suelto en la web (`#hex`, `gray-500`, `text-white` sobre superficie, `dark:`) | vocabulario del preset de `design/` (`canvas`, `surface`, `ink`, `accent`, `ok`/`bad`/`warn`…; gráficos con `useChartTheme`): tema claro por defecto, lo vigila `designTokens.test.ts` (#188) |
| `<button>`/`<select>`/`<input>`/`<h1>` a mano en una página | componentes de `components/ui` (docs/UI.md); `rawControls.test.ts` no deja sumar más (#190) |
| página nueva de Talent (`frontend/src/market`) sin su recorrido ni su maquetación | añadirla a `PAGES` de `frontend/e2e-talent/support.ts` (maquetación a 320/412/1280 y axe, #1006) |
| pantalla/lista nueva de la app sin comprobar su maquetación | añadirla a `apps/live-android/e2e/layout.spec.ts` (412 y 320 px, nombres largos): nada sale de la pantalla ni se superpone (#508) |
| estado de test inventado (dict o `snap()` a mano con 1-4 jugadoras en pista: puede ser inalcanzable) | `Match` de `tests/builders.py`, que solo produce estados alcanzables |
| `bash -c` con heredoc largo en Windows (falla) | escribir el script a un fichero y ejecutarlo |
| leer `min`/`sec` de FBCYL como tiempo transcurrido | es tiempo **restante** (#370) |

## Decisiones tomadas (no re-debatir; razón, fecha y excepciones en [docs/DECISIONS.md](docs/DECISIONS.md))
Stack: MongoDB + aggregation pipelines (sin SQL ni ORM) · pymongo síncrono · FastAPI + React/Vite · fpdf2 + python-docx · matplotlib (precisión FIBA) · motor live en biblioteca estándar con Pyodide en la tablet · sin LLMs.
- **App live**: release automática cada viernes por la mañana, el staff actualiza con el botón; acceso a paquetes por alcances (#410), `access.mode` `legacy` hasta la release que lee el índice v2; caminos no felices ya implementados (#219, #220), pendientes de tablet real.
- **API** (#334): `src/api` y `run_api.py` se quedan para desarrollo, pruebas y e2e; **sin Render ni alojamiento** en el repositorio.
- **Competiciones** (#435, #724): un solo catálogo, `config/competitions.json`.
- **Predictivo en el navegador** (épicas #841, #935): TS sobre `web-data`, siempre probabilidad condicional, nunca promesa; sin ascensos, descensos ni playoffs.
- **BasketLab Talent** (épica #872): app aparte en la misma plataforma; identidad anclada al `idPlayer` de FEB; escritura del staff decidida en #895.
- **Local-first** (#326): la web lee la rama `web-data` con `?data=local`; la API queda de respaldo.
- **Producto** (26/10/2026): web multiusuario con niveles de acceso y app Android como cliente; el modelo se decide en #591 antes de cuentas (#153).

## Lógica de negocio
- **Cuartiles (Mongo 7+)**: `{"$percentile": {"input": "$m", "p": [0.25], "method": "approximate"}}`.
- **Tendencias**: ⇈ >10 % (#006400) · ↑ 5-10 % (#28a745) · ≈ <5 % (#6c757d) · ↓ 5-10 % (#fd7e14) · ⇊ >10 % (#dc3545).
- **Four Factors**: eFG%=`(FGM+0.5·3PM)/FGA` · TOV%=`TOV/(FGA+0.44·FTA+TOV)` · ORB%=`ORB/(ORB+DRB_rival)` · FTr=`FTA/FGA`. Pesos de Oliver 40/25/20/15 (live).
- **Zonas de tiro (10)**: aro, zona (pintura), 3 de media distancia, esquinas, alas, centro del arco.

## Comandos
```bash
python scripts/pre_pr.py              # checklist previa al PR (ruff, rebase, docs; avisa de rojo y árbol sucio)
python run_api.py                    # API :8000 (BASKETLAB_DEV=1 → reload)
cd frontend && npm run dev           # Vite :5173
pytest -q --no-cov tests/test_x.py   # backend: solo lo afectado (tabla de Reglas de implementación); en paralelo: python -m pytest -n auto
cd frontend && npm run lint && npm run type-check && npm run test:run && npm run build
python tests/live_vectors/generate.py  # regenerar vectores tras cambiar live_core (y, si cambia el paquete, los fixtures sellados: make_demo_bpkg.py y make_demo_scoped.py; correr la suite COMPLETA de la app después)
cd apps/live-android && npm ci && npm run test:run   # app live: tests con Pyodide real (e2e: npm run e2e)
# creds: MONGODB_CONNECTION_STRING o src/database/db_credentials.txt · ejemplo en .env.example
```
Estudios de predicción (`study:forecast`, `web_data_dump`), e2e de Talent, vectores de Talent: docs/TESTING.md · publicación de Talent y barrido de plantillas (`run_talent_data.py`, `run_roster_sweep.py`): docs/OPERATIONS.md y docs/ARCHITECTURE.md · FEB simulado y demos (`fake_feb`, `demo_builder`): docs/LIVE.md. Busca por el nombre del script.
