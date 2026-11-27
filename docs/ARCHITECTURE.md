# Arquitectura (para Claude)
Flujo: **frontend → API (routers) → servicios → repositorio → MongoDB**. Nada de BD en el frontend. Operaciones y clave de admin: [OPERATIONS.md](OPERATIONS.md). Detalle de datos: [DATA_FORMATS.md](DATA_FORMATS.md); motor live: [LIVE.md](LIVE.md).

## Mapa del documento
Sección -> pregunta que responde (`grep -n '^#'` da el índice completo):
- Paquetes `src/` (tabla) -> ¿qué hace el paquete `src/x`? (una línea y enlace a su detalle)
- Detalle por paquete `src/` -> ¿módulos y reglas de `src/api`, `pbp`, `live_prep`, `local_data`, `market`, `external`…?
- Routers API (`src/api/routers`, prefijo `/api/v1/<x>`) -> ¿qué router/endpoint existe? ¿seguridad, `ADMIN_API_KEY`?
- Servicios (`src/services`) -> ¿qué servicio calcula X? ¿qué páginas tiene cada competición?
- Base de datos (`src/database`) -> ¿conexión, colecciones, pipelines, índices, `DERIVED`?
- Frontend Analytics (`frontend/src`) -> ¿tema, `datasource/`, `forecast/`, `webdata/`, `localdata/`, `api/client.ts`?
- Frontend Talent (`frontend/src/market`) -> ¿buscador, ficha, comparador, «Mi equipo» de BasketLab Talent?
- Despliegue y config -> ¿Vercel, CI, variables de entorno?
- Rutas de import / Deuda conocida de arquitectura -> ¿cómo se importa (`src.…`)? ¿dónde está la deuda?

## Paquetes `src/` (tabla)
| Paquete | Propósito | Detalle |
|---|---|---|
| `src/api` | FastAPI: `app.py`, `deps.py` (`get_db`), `routers/`; 503 con pista accionable sin Mongo | [detalle](#srcapi-fastapi-apppy-depspy-get_db-routers) |
| `src/services` | lógica de negocio | [detalle](#servicios-srcservices) |
| `src/database` | conexión, repositorios, pipelines, índices, `shared_handler`, `db_health` | [detalle](#base-de-datos-srcdatabase) |
| `src/scraper` | clientes FEB/FBCYL (JWT, API, calendarios) | [detalle](#srcscraper-clientes-febfbcyl-fbcyl_calendar-schedule_client) |
| `src/pbp` | parsers de play-by-play y posesiones sin BD (los reutiliza el motor live) | [detalle](#srcpbp-play-by-play-y-posesiones-sin-bd-game_possessions-game_derived) |
| `src/report_engine` | informes por reglas, sin LLM, funciones puras | [detalle](#srcreport_engine-informes-por-reglas-catalog-rules-engine) |
| `src/live_core` | motor de partido en vivo, biblioteca estándar (Pyodide en la tablet) | [detalle](#srclive_core-motor-en-vivo) |
| `src/live_prep` | paquetes de preparación cifrados, canary, grabador, publicador, scouting | [detalle](#srclive_prep-paquetes-de-preparación-publisher-scouting_-recorder) |
| `src/shotcharts` | cancha FIBA, zonas, visualizadores, valoración de zona | [detalle](#srcshotcharts-cancha-zonas-feb_zones-zone_rating-owned_shots) |
| `src/stats` | calculadoras de estadísticas (equipo, avanzadas, jugador) | [detalle](#srcstats-calculadoras-match_derived) |
| `src/utils` | `collection_utils` (`is_fbcyl`), `numeric_utils`, `team_utils` | [detalle](#srcutils-srcvisualization-srcjson_samples-y-appslive-android) |
| `src/visualization` | radar chart | [detalle](#srcutils-srcvisualization-srcjson_samples-y-appslive-android) |
| `src/local_data` | local-first: filas, archivo privado, publicación `web-data` | [detalle](#srclocal_data-exportación-archivo-privado-y-publicación-web-data-web_data-archive-contract) |
| `src/market` | BasketLab Talent: equivalencias, identidad, filas por temporada, perfiles | [detalle](#srcmarket-talent-equivalence-identity-season_rows-profile-canonical) |
| `src/external` | fuentes externas ACB, Euroliga, FIBA, NCAA convertidas a formato FEB | [detalle](#srcexternal-fuentes-externas-acb_-fiba_-euroleague_-ncaa_-registry-refresh) |

## Detalle por paquete `src/`

### `src/api`: FastAPI, `app.py`, `deps.py`, `get_db`, `routers/`
- FastAPI: `app.py` (todos los routers, CORS), `deps.py` (`get_db`; el handler único es `src/database/shared_handler.py` con `lru_cache`, **que también usan los jobs de publicación, #334**: nada de lo que publica datos importa `src.api`, lo vigila `test_publication_without_api.py`; 503 con pista accionable si no hay Mongo o se rechazan las credenciales: el clasificador está en `src/database/db_health.py` y `src/api/db_health.py` lo reexporta), `routers/`

### `src/scraper`: clientes FEB/FBCYL, `fbcyl_calendar`, `schedule_client`
- clientes FEB/FBCYL: token JWT, API, calendario HTML
- `fbcyl_calendar` (el calendario ESB de un grupo de FBCYL leído en un solo sitio y convertido a `CalendarMatch`, #446)
- `calendar_parser` (conserva los partidos aún no jugados), `schedule_client` (calendario/estado en directo de FEB; solo depende de requests/bs4/cachetools/tenacity)

### `src/pbp`: play-by-play y posesiones sin BD, `game_possessions`, `game_derived`
- parsers de play-by-play y posesiones **sin BD** (los reutiliza el motor live)
- `game_possessions` (posesiones, rebotes y pérdidas por equipo y partido validados contra el boxscore), `points_by_origin` (puntos por origen, banquillo y pintura por equipo y partido), `period_stats` (cifras por equipo y periodo), `situation_stats` (ATO, primera posesión y ventanas de 2:00) y `timeout_effects` (ventanas antes y después de cada tiempo muerto) y `game_derived` (el subdocumento `DERIVED` que se guarda en cada partido FEB, #372)

### `src/report_engine`: informes por reglas, `catalog`, `rules`, `engine`
- informes por reglas (sin LLM, funciones puras): `catalog` (estadísticas; el grupo «Origen de los puntos» —puntos tras pérdida, de 2.ª oportunidad y en la pintura, propios y concedidos, y % del banquillo— sale del pbp y `TeamReportService` lo añade a la fila y a los cuartiles desde `PBPExtendedStatsService`, #358), `rules` (cuartiles, diferencial vs mediana, CV), `zones` (zonas calientes/frías), `templates` (frases por tema), `engine.build_team_report`, `html_renderer` (para PDF), `config.ReportConfig` (umbrales por confirmar)

### `src/live_core`: motor en vivo
- motor de partido en vivo, biblioteca estándar (corre en la tablet con Pyodide)

### `src/live_prep`: paquetes de preparación, `publisher`, `scouting_*`, `recorder`
- generación y cifrado de paquetes de preparación (usa Mongo; por contraseña o por alcance, #410:
  - `package_scopes`, `package_sealing`, `invite`)
  - `canary` (comprobación diaria del formato de datos de FEB) y `recorder`/`recording_report` (grabación y análisis del feed en directo)
  - `publisher` (paquetes de los próximos partidos del club → rama `live-packages`, `run_package_publish.py`, workflow `live-packages.yml`)
  - `round_packages` (la jornada completa de cada competición en un sobre comprimido, #286/#172) el evaluador de reglas (`python -m src.live_prep.rule_evaluation`, workflow `rule-evaluation.yml` a mano)
  - `roster_fetcher` (plantilla de FEB con la marca de formación; una petición por equipo al construir cada paquete), el scouting del rival (`scouting_collect`, `scouting_report`, `scouting_compare`; servicio `scouting_rival_service` y PDF `scouting_pdf`) y `wp_*`/`download_games` (calibración de la probabilidad y descarga de partidos a carpeta), ver [LIVE.md](LIVE.md)

### `src/shotcharts`: cancha, zonas, `feb_zones`, `zone_rating`, `owned_shots`
- cancha FIBA, zonas (shapely), visualizadores
- `feb_zones` (conteo por zona y la API que usan el router, los servicios y los exportadores; **la geometría ya no es suya: clasifica con `live_core.zones`**, un solo sistema de 10 zonas para web, app e informes, #452)
  - `fbcyl_zones` (mismos conteos desde las coordenadas por jugador de FBCYL)
  - `zone_rating` (valoración de zona por cuartiles ponderados de la competición, #760)
  - `owned_shots` (cada tiro con su equipo y jugador, compartido por el exportador de la web y el servidor)
  - `zone_distribution` (conteos por zona de cada equipo o jugador: la referencia de la valoración)
  - `league_zones` (#765: `league_zone_distribution`, los conteos por zona de cada equipo o jugador en las zonas del `ZoneAnalyzer`, con los que los PNG del informe semanal y del scouting individual colorean con la misma regla que la web)

### `src/stats`: calculadoras, `match_derived`
- `formulas` (#1153): el registro de las tasas de equipo, que lee `config/formulas.json` (evaluar, y construir la expresión de Mongo de los pipelines); su gemelo del navegador es `frontend/src/lib/formulas.ts` (alias `@config` en Vite/tsconfig) y el vector compartido `tests/formulas/vector.json`.
- calculadoras (StatsCalculator, avanzadas, jugador)
- `match_derived.with_derived` aplica las cifras exactas de `DERIVED` (posesiones, rebotes y pérdidas validados) a los totales de un partido, y el informe semanal la usa en «Último partido» (#379)

### `src/utils`, `src/visualization`, `src/JSON_samples` y `apps/live-android`
- `src/utils`: `collection_utils` (`is_fbcyl`), `numeric_utils`, `team_utils`, `text` (`strip_accents`, `plain_words`: el único normalizador de nombres, con apóstrofos y Ł/Ø/ß/ı; #1128)
- `src/visualization`: radar chart
- `src/JSON_samples/` = documentos reales de ejemplo (FEB y FBCYL) para tests. `apps/live-android/` = app móvil/tablet del motor live (fuera de `src/`; ver [LIVE.md](LIVE.md)).

### `src/local_data`: exportación, archivo privado y publicación `web-data` (`web_data`, `archive`, `contract`)
#### Exportación de filas (`export`, `run_local_export.py`)
- **local-first (#327)**: `export` escribe un fichero por competición con las filas del contrato (equipo y jugador por partido) y un `index.json`, sin marcas de tiempo (un refresco sin partidos nuevos no cambia ningún byte)
- `python run_local_export.py [--out DIR] [--collection N]` (por defecto `frontend/public/local-data`, ignorado por git)

#### Informes de equipo sellados (`team_reports`, `run_local_reports.py`, #638)
- `team_reports` (**clase B, #638**): el informe de equipo propio y el scouting del rival de cada equipo (FEB y, desde #635, los grupos de FBCYL donde juega un equipo de interés), calculados con `TeamReportService` (la temporada se lee una vez por competición), sellados una vez con clave aleatoria y envueltos por alcance (`package_scopes`: el análisis propio para `club:<equipo>`, el scouting para los clubes de la competición, todo para `competicion:<col>` y `abierto` mientras dure la beta
  - la política vive en `report_scopes`), un fichero por equipo y modo más `index.json`, y un informe que no cambió no se reescribe
- `python run_local_reports.py [--out DIR] [--collection N] [--closed]` con `PACKAGE_MASTER_KEY`

#### Filas de jugador de FBCYL (`fbcyl_player_rows`, #644)
- filas de jugador de FBCYL (**#644**, `fbcyl_player_rows` sobre `build_fbcyl_season_player_rows_pipeline`): el *pipeline* de temporada resuelve la identidad en Mongo (nombre normalizado, UUID completado con `$max`, fantasmas, `$reduce` del +/-), aquí lo hace el exportador en Python sobre **toda la temporada** —un jugador con el UUID ausente en algunos partidos es una sola persona sea cual sea el filtro
- la API lo completa solo con los partidos filtrados, divergencia documentada y probada— y el cliente solo suma

#### Archivo privado (`archive`, `COLLECTION_META`, `archive_purge`, `archive_repo`, `ssh_key`)
- `archive` (**#646**): archivo privado de los partidos en bruto, un `.jsonl.gz` por competición (JSON extendido, partidos por `_id`, gzip sin marca de tiempo: sin cambios = mismos bytes) y `archive.json` con sha256 que `load_archive` comprueba antes de tocar la base
- **`COLLECTION_META`** (#724: lo que el scrape de FEB guarda por colección —URL del calendario, etiquetas, grupo—, que `live-packages` lee para etiquetas y fases) viaja en un fichero propio, `COLLECTION_META.jsonl.gz`, anotado en `archive.json` como `meta`: sin `saved_at` (cambia en cada pasada y haría commit en cada refresco), restaurado **por `_id` sin vaciar la colección** (un scrape puede haber escrito ya algunos), con `--collection` solo los de esas colecciones, y protegido por la misma guarda `--no-shrink`
- **`ensure_team_indexes`** (`run_archive.py index`, #724 paso 4) crea el índice `HEADER.TEAM.id` de las colecciones FEB tras una restauración, porque un índice no viaja en el archivo y los paquetes lo necesitan
- la acción compartida `.github/actions/restore-archive` (descarga con la clave reconstruida, restaura —solo una colección si se pide— e indexa, **solo lectura**) la usan `live-packages` y `rule-evaluation` (no se sustituye por uno con menos metadatos)
- un archivo anterior sin `meta` se carga igual y el primer refresco lo siembra
- las temporadas anteriores a la previa se guardan ligeras (sin `PLAYBYPLAY`/`moves`)
- `python run_archive.py dump --out DIR [--no-shrink]` / `load --src DIR --replace` (restaura en el Mongo efímero del job; reemplaza las colecciones; `--no-shrink` se niega, sin escribir nada, a sustituir el archivo por uno con menos partidos)
- `archive_purge` (**#724**: la única orden que borra datos del archivo —una competición y temporada con todas sus fases por el nombre de la colección—, en ensayo sin confirmación, con la competición y la temporada escritas de nuevo para borrar, rechazando una competición activa del catálogo; quita ficheros, entradas de `archive.json` y metadatos y trabaja solo sobre el directorio del archivo
  - `run_archive.py purge` y `archive-purge.yml`, que comparte concurrencia con el refresco) y `archive_repo` (**el repositorio privado**: `pull`/`push` por git; un único commit forzado con `--force-with-lease` sobre el commit descargado —no pisa un remoto que cambió— y las últimas 10 versiones como etiquetas `archive-<fecha>-<sha>`; `python run_archive.py pull|push --repo URL --dir DIR`)
- `ssh_key` (`normalise_key`: la clave de despliegue guardada a mano en un secreto, reconstruida desde su cuerpo base64 para que OpenSSH la acepte).

#### Workflows `archive-refresh.yml` y `web-data.yml`
- `archive-refresh.yml` (**#724**) es el único que escribe el archivo: descarga → Mongo efímero → scrapea lo nuevo de FEB y FBCYL (el catálogo) → `DERIVED` → guarda (`--no-shrink`), con cron propio y en rojo si el scrape informa de un problema
- `web-data.yml` usa lo mismo solo para leer: descarga → Mongo efímero → construye → publica, tras cada *Archive refresh*, y cae a Atlas sin `ARCHIVE_DEPLOY_KEY`.

#### Scouting del rival (`scouting_export`, #638)
- `scouting_export` (**#638**: el scouting completo del rival por alcance (`liga`, `copa`, `todo`) sellado como un informe de rival —todos los clubes de la competición y la competición pueden abrirlo— en `scouting/`, indexado con `mode: scouting` y `scope`; se calcula para las competiciones de la última temporada donde juega un **club de interés** (el del publicador y los `clubs` de su catálogo: hoy LF Challenge, 2ª FEB A y B y 3ª FEB A-B, 58 equipos); `--scouting COL`/`--no-scouting`; **sin comparativa con nuestro equipo**: depende de un par de equipos y la calcula el servidor)

#### Contrato del manifiesto (`contract`, `run_web_contract.py`, #328)
- `contract` (**#328**: el **contrato del manifiesto** declarado una sola vez —`WebDataManifest`, `RowsEntry`, `ReportIndex`…—, con `validate_manifest`/`validate_report_index` y `render_typescript`; `python run_web_contract.py` genera `frontend/src/webdata/contract.generated.ts` y un test falla si va por detrás; las filas y el contenido de los informes los fijan la publicación versionada y los vectores de paridad, no este módulo)

#### Publicación `web-data` (`web_data`, `run_web_data.py`)
- `web_data` (**#328, #640**): lo que lee la web en la rama `web-data` —`index.json` (manifiesto: `schema`, `v`, `open_key`, las filas de cada competición y el índice de informes de cada una), `rows/` (filas del contrato selladas para `competicion:<col>`) y `reports/` (un índice por competición, en claro, y los informes sellados)—
- todo menos el manifiesto lleva el hash del contenido en el nombre (un fichero **nunca cambia en su sitio**: un cliente con un manifiesto viejo ve el fichero antiguo o un 404, jamás una mezcla) y parte de la publicación anterior para que lo que no cambió conserve sus bytes (el sellado es aleatorio)
- `python run_web_data.py --out DIR [--collection N] [--closed]` con `PACKAGE_MASTER_KEY`, workflow `web-data.yml` tras cada *Archive refresh* (un solo commit forzado y solo si algo cambió; guarda de Vercel como `live-packages`).
- Medido con la BD local (62 competiciones): 47 s, 11 MB en disco (filas 2,2 MB, 1.000 informes; manifiesto 197 KB, 17 KB comprimido) y una segunda ejecución deja el árbol idéntico.
- Las filas y los informes salen **iguales con cualquier orden de inserción** (filas ordenadas; floats de los informes a 9 decimales), porque el archivo restaura por `_id` y no por orden de llegada

#### Calendario y género (`calendar_export`, `competition_gender`, #842, #843)
- `calendar_export` (#842): el calendario de cada competición de la temporada más reciente (sin eliminatorias; en FBCYL, solo los grupos del catálogo), **sección `calendar/` sellada para la competición y fuera de la caché** (un calendario cambia sin partido nuevo: se lee de la FEB —página del grupo— o del ESB de FBCYL en **cada** publicación; `CalendarSource` es la frontera de red, falseada en los tests): cada partido con `code`
  - `match_id` (el `_id` del partido: código FEB, `universallyid` en FBCYL), jornada
  - `kind` (`result`, `scheduled` o `live`: un resultado FEB que no está en el archivo se consulta a la API en vivo, máx. 8 por competición), inicio, equipos y marcador
- `ties_allowed` en FBCYL. Un fallo da `None` con aviso y **la publicación sigue**: se conserva el calendario anterior (o ninguno), `--no-calendar` lo omite
- `competition_gender` (#843): `F`/`M` de cada competición en la entrada de `rows` del manifiesto (`gender`, ausente si no se sabe): FEB por la etiqueta de su competición en `COLLECTION_META` o, sin metadatos, por la competición del nombre de la colección, contra el catálogo (`competition_info.competition_infos`)
- FBCYL por el `_gender` de sus partidos o por la entrada de su grupo
- con él la web elige la probabilidad de victoria calibrada de su familia (`WP_BY_GENDER`)

#### Secciones, imágenes y caché (`sections`, `images_export`, `parallel_sections`, `build_cache`)
- `sections` (`section_payload`: qué tiene cada competición para cada sección, o nada que publicar)
- `images_export` (#717, 17a): el escudo y las fotos de cada equipo, con la fecha de nacimiento y la altura de cada jugador (lo que el servidor bajaba de la FEB al escribir el DOCX del scouting individual
  - la FEB no manda CORS, así que el navegador no puede), **por equipo** —entradas `mode: images` del índice de informes de la competición, selladas para la competición y todos sus clubes como un scouting de rival—, solo de las **competiciones de la temporada más reciente de cada liga** (la de FEB, `2026_2027`, y la de FBCYL, `2026`
  - #721: FBCYL no tiene fecha de nacimiento ni altura, y el escudo y la foto de cada jugador, por su `uuid` estable, se piden a la ESB de la federación —`Clubs/getImageByTeamId` y `Federateds/getPhotobyUuidFederat`—, que dice qué foto tiene ahora, así que se pregunta cada vez y la imagen solo se baja si cambió su tamaño) (el DOCX es del rival de la semana,
    - de esa temporada), reducidas (foto a 200 px en JPEG sobre blanco, escudo a 128 px en PNG: unos 10 KB cada una) y **incrementales**: el publicador baja lo que no estaba y conserva lo que ya tenía si el tamaño que anuncia un HEAD no cambió (la FEB no admite peticiones condicionales: sin ETag, `Last-Modified` siempre «ahora»)
- la identidad se raspa una vez por jugador y, desde #1082, el `alta` y la `baja` de su línea de la «Trayectoria» (`feb_trajectory`) se leen la primera vez que se ve al jugador y después **una vez por semana por equipo** (#1085: `reread_today`, un día de siete distinto para cada equipo, sin estado)
- ocho peticiones a la vez
- `publish_web_data(image_source=…)` y `run_web_data.py --no-images`
- `parallel_sections` (#945: las secciones cuyo código cambió —`changed_code`— se calculan antes de publicar las competiciones con un `Runner`; `in_processes(n)` las reparte en `n` procesos `spawn`, cada uno con su `shared_handler`, y `publish_web_data(sections_runner=…)` las sella según llegan; sin runner, todo en serie
  - `run_web_data.py --workers N`), `build_cache` (#700, #783): `build-cache.json` en la publicación, con la huella de las filas y cifras derivadas de cada competición y **la versión del código de cada sección** (hash de los módulos que importa su exportador, `module_files`, más `src/database` por el `handler`; `payload_format` aparte de `export` para que decir el formato no arrastre la capa de datos)
- sin cambios, `web_data` reutiliza los ficheros sellados de cada sección y solo calcula las que cambiaron.

#### Temporadas publicadas (#991)
- **Temporadas publicadas (#991)**: `run_web_data.py` publica solo las dos temporadas más recientes de cada liga (`images_export.recent_season_collections`; el resto, en el archivo y en `talent-data`).

### `src/market`: Talent (`equivalence`, `identity`, `season_rows`, `profile`, `canonical`)
#### Talent (épica #872): visión general
- **Talent (épica #872, [evaluación](evaluaciones/2026-11-12_mercado-scoutingfeb.md))**:

#### Equivalencias entre competiciones y estimadores (`equivalence*`, `age_curve`, `formation*`)
- `equivalence` (**E1a, #891**: la tabla del grafo de equivalencias entre competiciones, sin modelo: una observación por persona, competición y temporada con los percentiles de los 8 ejes como z, los **movimientos** entre dos competiciones del mismo sexo en temporadas consecutivas, los que se quedan en una y el recuento de personas por arista y sentido según el nivel; la copa y la formación no son nodos; ver [el diseño](evaluaciones/2026-11-20_grafo-equivalencias-891.md))
  - `equivalence_model` (**E1b**: `z_B = ρ·z_A + (θ_B − θ_A)` por eje con **un nivel por competición ajustado con todos los movimientos a la vez** por mínimos cuadrados, errores agrupados por persona, aristas con ≥ 40 personas, hombres y mujeres aparte; `translate` da siempre un **rango del 80 %** y `None` si las competiciones no están conectadas)
  - `equivalence_publish` (**E1c**: el documento `equivalences` de `talent-data`, sellado como el resto y con su entrada `usable` en el manifiesto: por sexo los niveles θ, su covarianza, el ruido y la fiabilidad de un origen de **una y de dos temporadas** (la media por minutos de la temporada y la anterior en la misma competición
    - los niveles son siempre los de una temporada), las aristas con ≥ 40 personas y la validación de una temporada fuera; `estimate` da **un solo estimador final por jugador** —la web no distingue medias— y `estimate_from_document` es la referencia de lo que hará el navegador, E4)
  - `age_curve` (**E2, #892**: `z_siguiente = ρ·z + efecto(edad)` con los que se quedan en su competición, efecto fijo por edad suavizado y encogido, una temporada fuera cada vez; **medido: la edad mejora menos de un 1 %, no se enseña**, [resultado](evaluaciones/2026-11-20_curva-de-edad-892.md))
  - `formation` (**E3, #893**: `z_sénior = a + b·z_formación + g·[U18]` en la escala común del grafo, **condicional a llegar al juego sénior**, una promoción fuera cada vez con los niveles del grafo hechos sin esa temporada; medido: error −11 % frente a la media de los que llegan, cobertura 79,5 %, [resultado](evaluaciones/2026-11-20_indice-de-formacion-893.md))
  - `formation_publish` (**E3b**: el documento `formation` de `talent-data`, sellado como `equivalences` y con su entrada `usable`: por sexo los coeficientes y el ruido, los grupos de los que habla —con al menos 100 jugadores que llegaron— y la validación de una promoción fuera; `estimate_from_documents` es la referencia de lo que hará el navegador y toma los niveles de las competiciones sénior de `equivalences`)
  - `equivalence_study` (una temporada fuera cada vez y *walk-forward*, con el veredicto de si el rango se puede enseñar; [resultado](evaluaciones/2026-11-20_estudio-estimador-891.md))
- funciones puras sobre documentos de partido, sin E/S.

#### Identidad de personas (`identity`, `name_conflicts`, #873)
- `identity` (**#873**): registro de personas, un `person_id` (`feb:<idPlayer>`) por jugador, nunca fusionado por nombre (medido en el seed: el id es estable entre competiciones y temporadas; 13 de 2.158 ids con más de una grafía)
- `name_conflicts` lista los ids cuyas grafías no comparten ningún apellido (a revisión).
- Determinista e independiente del orden de los partidos.

#### Barrido de plantillas (`roster_sweep`, #874)
- `roster_sweep` (**#874**): barrido de las plantillas de todos los equipos FEB de cada temporada (`season_team_ids` desde los partidos; reutiliza `live_prep.roster_fetcher`: nombre completo, nacimiento, altura, posición, nacionalidad y formación), una petición por equipo y temporada con pausa de 1 s entre peticiones, lista de equipos no leídos (`missing`) y filas ordenadas sin marcas de tiempo
- el peso queda sin leer (el parser compartido no lo recoge).

#### Publicación `talent-data` (B2 #878: `competitions`, `season_rows`, `bio`, `advanced`, `profile`, `contract`, `roster_store`, `roster_run`, `publish`)
- **B2 (#878), la publicación `talent-data`**:
  - `competitions` (qué competición y temporada es cada colección: `COLLECTION_META`, el nombre y, para FBCYL, el catálogo —categoría + territorio + temporada—; las fases y los grupos de una competición van juntos y las competiciones **nunca se mezclan**; lo que no dice nada va a `unknown`)
  - `season_rows` (**una fila por jugador, temporada, competición y equipo**: un traspaso son dos filas; suma las filas de `export_collection`; los minutos son **segundos en FEB y FBCYL**, que va en minutos enteros, medido en el archivo: `×60`; `attach_bio` une la plantilla **campo a campo** (#910): el equipo y la temporada de la fila, luego otro equipo de la temporada y luego la temporada más cercana —empate, la más reciente—; `bio_from` dice de dónde salió lo que la plantilla de la fila no decía; formación y dorsal solo salen de esa temporada)
  - `bio` (**#910**: `normalize_height` → cm enteros desde cm, metros, pies-pulgadas `6-7`/`6'7"` y pulgadas, `None` fuera de 120–240 cm; `canonical_position` —Base, Escolta, Alero, Ala-Pívot, Pívot— y `position_group` G/F/C, lo único que dice la NCAA; `merge_bio` para las fuentes externas: campo a campo, prioridad FEB > FIBA > ACB > NCAA, `bio_src` con la fuente de cada campo y `bio_conflict` si las alturas difieren más de 3 cm, las fechas difieren o los grupos de posición difieren)
  - `advanced` (usage, ORtg, DRtg, net, AST%, TOV%, STL%, BLK%, REB% y PIE en el contexto de **su** equipo, con paridad con los vectores de la página de jugadores)
  - `profile` (tasas por 40, rol z-score de `live_core.profiles` y percentiles dentro de **su** competición y temporada, `eligible` = **minutos suficientes** (#1010, `played_enough`): 10 minutos por partido jugado, al menos un tercio de los partidos de SU equipo —los del jugador más usado de ese equipo en la competición; un traspaso son dos filas, cada una contra su equipo— y al menos 3 partidos. Es también la población de los percentiles, y el filtro y la insignia «Pocos minutos» dicen la regla (`enoughMinutes.ts`); los paquetes live conservan sus 5 minutos; en `tov` menos es mejor)
  - `contract` (manifiesto propio `TalentManifest` y tipos TS generados con `run_web_contract.py`)
  - `roster_store` (`rosters/<temporada>.json` de `basketlab-archive-ext`: `{format, season, teams, rows}`; `teams` son los equipos **barridos** —uno sin jugadores también lo está—; `merge_season` sustituye las filas de los equipos barridos, así que quien se fue de una plantilla desaparece)
  - `roster_run` (**A5, #905**: `plan_sweep` —la temporada en curso, la última de los partidos, **entera cada día**
    - las cerradas **una sola vez**, de la más nueva a la más antigua y como mucho `budget` equipos por run: **el presupuesto cuenta solo el atraso de las cerradas**, nunca la actual—, `sweep_into` —un equipo que no responde no se marca como barrido y se vuelve a pedir— y `teams_by_season` —los ids de equipo de los partidos, solo FEB, con la misma clave de temporada que las filas de Talent—
    - `python run_roster_sweep.py --out DIR [--seasons 2025,2024] [--budget N]`; workflow `talent-rosters.yml`)
  - `publish` (un fichero sellado por competición y temporada para el alcance `talent` —y `abierto` en la beta— con el hash en el nombre, más `index.json`; `python run_talent_data.py --out DIR [--rosters DIR] [--closed]`). Workflow propio `talent-data.yml` (rama `talent-data`, grupo de concurrencia propio: dos escritores en la rama de `web-data` competirían).

#### Formato canónico de fuentes externas (`canonical`, #884)
- **`canonical` (#884, D0)**: el formato canónico de las fuentes externas —ACB, FIBA y NCAA se convierten al documento FEB en la ingesta—: `_league` es la fuente, todo id lleva su prefijo (`ncaa:401`; los de FEB son dígitos y nunca llevan), la duración del partido depende de la fuente (NCAA masculina, 2 mitades de 20 min; el resto, 4 cuartos de 10; cada prórroga, 5) y `validate_game` lista lo que está mal sin tocar el documento (ids sin prefijo en la cabecera, la caja o la jugada a jugada, equipos de la caja que no son los de la cabecera, hora de inicio, periodos de menos).

#### Cuadre con la caja oficial (`box_reconciliation`, `minutes_reconciliation`, #884, #963)
- **`box_reconciliation` (#884, D0)**: el cuadre de la jugada a jugada con la caja oficial, **criterio común de aceptación de toda fuente nueva**: por equipo-partido y estadística cuenta lo que dice la jugada a jugada (los mismos eventos y la misma regla de rebotes que el resto de pipelines, **sin las líneas que la mesa borró**) y lo compara con la caja.
- **Nueve estadísticas centrales exactas** (puntos, tiros de campo, triples y libres, intentados y anotados, rebotes ofensivos y defensivos): una diferencia y el partido es **no fiable** (fuera de tasas, percentiles y `eligible`, nunca corregido a ojo)
- asistencias, robos, tapones, pérdidas y faltas se miden e informan por fuente sin descartar el partido
- los minutos no se pueden contar aún y el informe lo dice (`UNCHECKED`). **Minutos** (`minutes_reconciliation`, #963): el quinteto inicial de la caja (`sta`) y las sustituciones dan los segundos en pista de cada jugador, comparados con los de la caja con tolerancia de 2 s
- son informativos (no descartan el partido) y, si el partido no trae quinteto, quedan sin comprobar (`unchecked: ["MIN"]`).

#### Enlace de identidades externas con FEB (`identity_link`, #885, #886)
- **`identity_link` (#885, D1)**: enlaza los jugadores de una fuente externa con la persona de FEB por **fecha de nacimiento y al menos dos palabras del nombre en común** (sin partículas) y candidato único (`linked`)
- **Reglas contra falsas fusiones (E2, #1125-#1129)**:
  - el enlace por nacimiento exige además el **nombre de pila o su inicial** (alguno de los nombres del jugador con alguno de la persona); si no, `review` con `reason: given_name` (#1126);
  - una sola palabra del club solo es prueba si los dos clubes son de la misma clase (`CB`/`BALONCESTO` frente a `C.D.`; #1127);
  - en FBCYL el filtro de edad exige que encajen **todos** los pares (categoría, temporada) reales del jugador (`periods`; #1125);
  - dos ids FBCYL enlazados al mismo id FEB en una competición y temporada no se funden: `linked_to` None y `link_conflict` con los otros (`season_rows.attach_bio`; #1129);
  - `external_players` toma el valor más repetido (fecha corregida en un partido posterior), a igualdad el menor.
- **ACB (#886) usa el mismo enlace**: su caja trae `name` (como se conoce al jugador: «Facu Campazzo») y `full_name` (el de su ficha: «Facundo Campazzo», como lo escribe FEB), y el enlace junta las palabras de los dos
- la biografía que presta ahora incluye la **posición** (`external_bio.FIELDS`) y `read_external_bios` junta la de FIBA y la de ACB
- una palabra o varios candidatos van a `review`
- la fecha sola nunca enlaza ([medición](evaluaciones/2026-11-18_enlace-fiba-feb.md): el 80 % de los extranjeros comparte fecha con alguien de FEB por casualidad).

#### Enlace de FBCYL sin nacimiento (#978)
- **FBCYL (#978)**, sin nacimiento: la persona es su `uuid` (el `actorId` cambia en cada partido)
- candidatos por clave de nombre (inicial + apellidos en su orden, sin partículas ni marcas como «(REF)»), nombre completo de las plantillas o los dos últimos apellidos (nombre de pila compuesto)
- fuera los de otro sexo (catálogo) o demasiado mayores para la categoría (U16/U18 del catálogo, nacimiento de las plantillas)
- `linked` con un único candidato y club corroborado (`name+club`) o nombre completo con nacimiento que encaja y sin homónimos en FEB (`name+birth`)
- el resto, `review`.
- Funciones puras
- `run_identity_links.py` escribe `links/<fuente>.json` en el archivo externo.

#### Biografía externa (`external_bio`, `attach_bio`, #979, #996)
- **`external_bio` (#979)**: de los jugadores de FIBA `linked` (nunca los `review`) saca nacimiento, altura y nacionalidad (el valor más repetido, empate al menor: no depende del orden de los partidos) y `attach_bio(..., external=)` los usa.
- **Biografía por la temporada más cercana (#996)**: altura, posición y nacionalidad cambian con los años, así que cada fila toma cada campo de la temporada más cercana a la suya entre TODAS las fuentes (rosters de FEB y un candidato por temporada de FIBA, sin tope de distancia; empate: mismo equipo, fuente de más prioridad `SOURCE_PRIORITY`, temporada posterior)
- `bio_from` dice `temporada:equipo` (FEB) o `fuente:temporada` (externa).
- El nacimiento no cambia: una fecha distinta queda en `bio_conflict` (`['birth']`), nunca se promedia.
- `nationalities` lista todas las nacionalidades distintas (`countries.py`: nombres de FEB y códigos de FIBA normalizados a un país; dos pasaportes no son conflicto), la más cercana primero, y `nationality` es la primera.

#### Enlaces de FBCYL en la fila y `identities` (#996)
- **Enlaces de FBCYL (#996)**: `attach_bio(..., linked=)` (`{person_id: feb:<id>}` de `links/fbcyl.json`, solo los `linked`) pone `linked_to` en la fila de FBCYL (su `person_id` no se reescribe) y le da la biografía de la persona de FEB (sin formación ni dorsal del club de FEB)
- la publicación escribe además `identities` (fichero sellado con `links` y `by_feb`, la lista de competiciones de FBCYL con filas de cada persona de FEB) que la ficha lee para unir la trayectoria sin abrir todo FBCYL, y para redirigir `fbcyl:U` a `feb:X`
- `read_external_bio` y `read_person_links` leen `links/*.json` del archivo externo (`run_talent_data.py --ext`).

### `src/external`: fuentes externas (`acb_*`, `fiba_*`, `euroleague_*`, `ncaa_*`, `registry`, `refresh`)
#### Fuentes externas: visión general
- **Fuentes externas (ACB, Euroliga, FIBA, NCAA; #884, épica #872)**, aparte de todo lo de FEB.

#### Euroliga (`euroleague_*`, #1038, D6a)
- **Euroliga (#1038, D6a)**:
  - `euroleague_page` (lee de la API pública el calendario, la caja con la biografía de los jugadores, la jugada a jugada y los tiros con coordenadas en centímetros; un partido son tres respuestas y deben ser del mismo partido)
  - `euroleague_client` (pausa de 0,5 s, un 429 se espera 60 s, presupuesto)
  - `euroleague_catalogue` (EuroLeague y EuroCup desde 2017/18, torneo U18 desde 2019/20, pausadas; `run_euroleague_catalogue.py`)
  - `euroleague_canonical` (el partido como documento FEB con el escritor de líneas de `fiba_canonical`, y el mapa de tiros solo completo)
  - `euroleague_source` (los partidos jugados que el archivo no tiene; los torneos U18 de una temporada en una entrada)
- ver OPERATIONS.

#### NCAA D1 (`ncaa_*`, #888, D4)
- **NCAA D1 (#888, D4; hecha el 23/11/2026)**:
  - `ncaa_page` (lee de ESPN las conferencias y la clasificación de una temporada, el marcador de un día y el partido: caja oficial, equipos con la conferencia de ese día y jugada a jugada)
  - `ncaa_client` (educado, con presupuesto; envía un `Mozilla/5.0` normal porque ESPN rechaza el que nombra un bot)
  - `ncaa_catalogue` (las entradas pausadas por conferencia, temporada y sexo; `run_ncaa_catalogue.py`)
  - `ncaa_canonical` (el partido como documento FEB: asistencias del segundo participante de la canasta, pérdidas de equipo en el total y el mapa de tiros completo, #1062)
  - `ncaa_source` (qué partidos son de una conferencia —los del equipo local—, los días que lee y el presupuesto por lotes)
- ver OPERATIONS.

#### ACB (`acb_*`, #886, D2)
- **ACB (#886, D2; en curso)**: `acb_page` (los datos de las páginas públicas de partido y de jugador, que viajan en los trozos de Next; `check_page` pide de nuevo la que llega sin datos; `parse_game` lee un partido terminado de sus dos páginas, caja y jugada a jugada, con el local que dice la jugada a jugada y la comprobación de que ambas son del mismo partido
  - `parse_player` lee la biografía de un jugador —nacimiento `AAAA-MM-DD` desde el `DD-MM-AAAA` de la página, altura en cm desde los metros con coma, posición y nacionalidad—, `parse_shots` sus tiros con coordenadas en milímetros desde el aro, y `shots_of_game` los une a las jugadas de un partido por orden —el n-ésimo tiro del jugador es su n-ésima jugada de tiro— solo si ambas listas dicen lo mismo: si no, el partido se queda sin coordenadas antes que con las de otro tiro) y `acb_client` (pausa de 1 s, presupuesto de peticiones por ejecución, reintentos con espera doble, 404 y 403 sin repetir
  - la clave de la API, que solo necesita el calendario, se lee del JavaScript público del sitio en cada ejecución y nunca se guarda ni se escribe; riesgo legal abierto, [informe](evaluaciones/2026-11-20_acb-spike-886.md))
- `acb_catalogue` y `run_acb_catalogue.py` (D2c: las ediciones de la Liga Endesa desde 2019/20 como entradas **pausadas** del catálogo, `league: acb` con `acb: {competition_id, edition_id}`, el id de la edición lo da la API y no una fórmula; no activa nada)
- `acb_canonical` (D2e: `to_canonical(partido, línea del calendario, entrada del catálogo)` lo escribe como el documento FEB —`_league: acb`, ids con prefijo `acb:`, inicio en hora de Madrid, TOTAL de los jugadores y lo del equipo aparte— y reutiliza el escritor de líneas de `fiba_canonical` (`Lines`, ahora con el prefijo como parámetro)
  - **los códigos de jugada de ACB no tienen tabla**: `KNOWN_CODES` son los que prueban los partidos reales y `UNKNOWN_CODES` los vistos y no entendidos, que quedan como líneas `other`
  - con `bios` y `shots` opcionales —la biografía de las páginas de los jugadores y sus tiros—: **`SHOTCHART` solo se escribe si cada tiro de campo del partido tiene su tiro con coordenadas** (el de FEB son exactamente los tiros de campo de la jugada a jugada
  - uno incompleto cambiaría todas las zonas) y `feb_coordinates` pasa los milímetros desde el aro a los porcentajes de la pista de FEB, con el equipo 0 en el aro izquierdo y el 1 en el derecho —el motor los pliega a la misma media pista y la zona sale la misma que da ACB—)
- `acb_source` (D2i: **la fuente registrada del refresco diario**: pide a la API los clubes y el calendario de cada club de la edición, se queda con los partidos terminados que el archivo no tiene y, de cada uno, lee la caja y la jugada a jugada y las páginas de los jugadores que jugaron —biografía— y de los que tiraron a canasta —tiros de su temporada, con `?editionId=`—
  - **presupuesto de peticiones por ejecución** (el del cliente, reintentos incluidos, 900 por defecto) y una página de jugador una vez por ejecución; una página que falta se anota y el partido sale sin esa biografía y sin mapa de tiros; si **ningún** partido pedido se puede leer, la ejecución falla).

#### Registro y refresco (`registry`, `refresh`, `run_external_refresh.py`)
- `registry` (una fuente es un objeto con `name` y `fetch(entrada, desde)` que da los partidos de una competición del catálogo en el formato canónico de `market.canonical`
  - hasta los bloques D2 a D4 no hay ninguna registrada) y `refresh` (`refresh_source`: restaura su archivo, pide los partidos desde la ventana de reescrapeo, **valida** cada uno —uno que no es canónico se rechaza con su motivo—, lo **marca** con su cuadre (`_reliable: false` y `_mismatches` si no cuadra: se guarda, nunca se descarta), lo fusiona por `_id` y escribe el archivo con el formato del archivo privado en `<out>/<fuente>/` junto a `status.json`: cuándo corrió, cuándo funcionó por última vez, cuántos partidos, cuáles no cuadran).
- Un fallo se queda en su estado y no toca el archivo ni a otra fuente
- una fuente sin scraper o sin competición activa está `pending` (no es un fallo).
- Punto de entrada `run_external_refresh.py`.

#### Publicación `web-data-ext` (`publish_external`, `run_web_data_ext.py`)
- **`publish` (`publish_external`)**: la publicación `web-data-ext` —restaura el archivo de cada fuente en la base de la ejecución, **deja fuera los partidos no fiables** (siguen en el archivo marcados; nunca entran en filas, tasas ni percentiles) y publica con `publish_web_data` solo las competiciones externas del catálogo, con la `league` de cada una y la **frescura de cada fuente** en el campo `sources` del manifiesto (`SourceFreshness`: estado de la última ejecución, `last_ok`, partidos, no fiables y publicados)—
- punto de entrada `run_web_data_ext.py`.
- Workflows propios `archive-ext-refresh.yml` y `web-data-ext.yml` (rama `web-data-ext`), sin relación con los de FEB.

#### FIBA: `fiba_page` (#887, D3a)
- **`fiba_page` (#887, D3a)**: la ficha pública de un partido de FIBA como datos (`/events/<evento>/games/<id>`). La página es de Next y sus datos viajan en los trozos `self.__next_f.push`: `extract_flight` los une y `parse_game` lee de ahí el partido, **la caja oficial por jugador y los totales de cada equipo (minutos, quinteto inicial y rebotes y pérdidas de equipo incluidos)**, las plantillas y la jugada a jugada completa agrupada por periodo (`Q1`…`Q4`, `OT1` en las prórrogas).
- Sin clave ni API. Una página sin datos de partido (la versión genérica que a veces devuelve la ficha) es `GenericPage` y una cortada o de otra forma, `FibaPageError`: el cliente de D3b reintenta.

#### FIBA: `fiba_canonical` (#887, D3a)
- **`fiba_canonical` (#887, D3a)**: `to_canonical` convierte lo que lee `fiba_page` en el documento FEB (`_league: fiba`, ids `fiba:<id>`): cabecera con la competición, el inicio local, los puntos de cada periodo (una prórroga es un quinto) y los equipos
- **la caja oficial** con los minutos en segundos y el quinteto inicial (`sta`)
- y la jugada a jugada como las líneas que lee el motor de FEB (`TIRO DE 2 ANOTADO`, `MATE`, `Faltas: n.`, `ENTRA/SALE DE PISTA`…, como hace `fbcyl_adapter`).
- Dos detalles de la fuente: **los totales de equipo de FIBA ya suman lo que hizo el propio equipo** (sus rebotes), así que el `TOTAL` se queda en la suma de jugadores y lo del equipo va en `TEAMACTIONS` (juntos son la cifra de FIBA)
- y **una sustitución puede ser un solo evento que dice quién entra y quién sale** (el partido absoluto) o dos (los de formación): siempre son dos líneas, la del que sale primero.
- Una «falta recibida» va en `logParam4` de su falta y un código desconocido se guarda como línea `other`.
- Sin el mapa de tiro por ahora (FIBA da coordenadas de pista; llevarlas a las zonas del motor es un bloque aparte).
- `gender_of` toma `M`/`F` de la competición y rechaza lo que no diga.

#### FIBA: `fiba_client` y `parse_event_games` (#887, D3b)
- **`fiba_client` y `parse_event_games` (#887, D3b)**: `parse_event_games` lee de la página de un evento sus partidos (quién juega, cuándo, el marcador y la `slug` de su ficha) y distingue **terminado** (`statusCode` `VALID` y último periodo `E`) de **programado** (`INIT`)
- la ficha de un partido también menciona otros, así que se distingue por su bloque `game` (dirección equivocada, no se reintenta).
- `FibaClient` pide las páginas **con cortesía** (como mucho una petición cada 2 s, agente genérico que **no nombra el proyecto**, sin clave), **con paciencia** (una página genérica, cortada —`CutPage`—, un error 5xx o un fallo de red se pide otra vez tras una espera que se duplica, hasta 4 veces) y **diciendo la verdad** (404 es `FibaNotFound`, un 403 `FibaFetchError`, y un formato que el lector no conoce se levanta tal cual: reintentar no lo cambiaría).
- La red se inyecta para probarlo con las páginas reales.

#### FIBA: `fiba_source`, `sources`, `fiba_catalogue` (#887, D3b)
- **`fiba_source`, `sources` y `fiba_catalogue` (#887, D3b)**: `FibaSource` (registrada para `fiba` por `sources.register_defaults`, que `run_external_refresh.py` llama antes de correr) pide a cada evento del catálogo (`fiba.event`) sus partidos, se queda con los **terminados que el archivo aún no tiene** (un partido jugado no cambia: recibe los `known` y no los pide otra vez) y lee la ficha de cada uno con el cliente
- **presupuesto por ejecución** (300 partidos por defecto, compartido por todas las entradas; `fiba.max_games` por entrada; `--budget` o la entrada manual `budget` del workflow), de modo que la primera carga se reparte en varios días y cada ejecución sigue donde acabó la anterior
- un partido que no se puede leer se salta y se dice (`notes` del estado: 404, formato, otro sexo) y **si ninguna de las páginas que llegaron se puede leer, la ejecución falla** (el sitio cambió; se abre el issue en vez de un archivo vacío en silencio)
- el sexo de la entrada debe ser el de la página.
- `fiba_catalogue` + `run_fiba_catalogue.py --year 2025` añaden al catálogo, **pausadas**, las entradas de los eventos que existen y listan partidos reales (U16, U18 y U20 EuroBasket, U19 Copa del Mundo y EuroBasket absoluto, masculino y femenino; U16 y U18 son formación).
- Un evento cuya página existe pero lista solo huecos sin equipos (la «cáscara» del Mundial U19 de años pares) no tiene partidos aún.

## Routers API (`src/api/routers`, prefijo `/api/v1/<x>`)

### Lista de routers y endpoints (`health`, `collections`, `teams`, `players`, `lineups`, `shots`, `possessions`, `scouting_rival`, `team_report`, `reports`, `matches`, `multi_phase`, `rotaciones`)
- `health` (`GET /api/v1/health`: vivo + commit desplegado, sin BD; `GET /api/v1/health/db`, público: conexión a Mongo, latencia y causa clasificada sin secretos)
- `collections`
- `teams`
- `players` (incluye IN/OUT)
- `lineups` (REST + SSE `/stream`)
- `assist_connections` (`GET /api/v1/assist-connections/{collection}/{team_id}[?player_id=]`: pasadores, receptores y zonas de anotación asistidas y sin asistir de un equipo, #773)
- `shots` (zonas; `?compare=league` añade `rating`/`league_pct`/`delta_pp`/`low_sample`)
- `possessions` (incluye `GET /{collection}/points-by-origin`: puntos por origen, banquillo y pintura de temporada por equipo y del rival, #352, `GET /{collection}/situations` (ATO propio y del rival, primera posesión de cada periodo y primeros/últimos 2:00 frente al resto, #354), `GET /{collection}/timeouts` (rating neto 5 posesiones antes y después de cada tiempo muerto, propio y del rival, y % que mejora al solicitante, #355) y `GET /{collection}/by-period`: puntos, posesiones, ORtg/DRtg, ritmo, eFG%, TOV%, ORB%, FTr y faltas por equipo y cuarto —Q1-Q4 y OT— con las del rival, #353)
- `scouting_rival` (informe de scouting de **cualquier equipo** de una colección FEB, en PDF —**hecho ya en el navegador a partir del informe (#715: `lib/scoutingPdf.ts` pide las mismas llamadas que `scouting_pdf.lay_out`, comprobadas una a una contra `scouting_pdf.json`, y las dibuja con `jspdf`; funciona también con el informe publicado, sin trabajo
  - `/pdf/{job}` queda sin uso y se retirará con #334)**— y como JSON para la vista previa: `POST /api/v1/scouting-rival` {collection, team_id, own_team_id?} lanza el trabajo en segundo plano, `/progress/{job}`, `/report/{job}`, `/pdf/{job}`; público (solo cómputo), **un solo trabajo a la vez**, caducidad de 30 min y hecho para ejecutarse en local, ver [LIVE.md](LIVE.md))
- `team_report` (informe automático por reglas JSON/PDF, modos `own`/`rival`; **el PDF ya se hace en el navegador** (#714: `lib/teamReportPdf.ts` escribe el mismo HTML que `render_report_html`, comparado cadena a cadena con `report_html.json`, y lo dibuja con `jspdf` al pulsar el botón, sea cual sea el origen del informe), así que `/pdf` queda sin uso y se retirará con #334; en `/reports/team-report/{collection}`)
- `reports` (informe semanal ZIP, `individual-scouting/docx`; los endpoints sin ningún cliente se retiraron en #202 —los paquetes live los publica Actions y la app los baja de `live-packages`; [historia](evaluaciones/2026-11-27_historia-architecture.md)—)
- (**retirados con el predictivo antiguo, #853**: `historical`, `analysis` y `analysis_predictive`; el ajuste por rival lo calcula `rival_adjusted_service` y lo publica `web-data`, `rival_adjusted/`)
- `matches`
- `multi_phase` (`/multi`)
- `rotaciones` (REST + SSE; **jugadoras significativas (#757)**: las que han jugado al menos el 15 % de los partidos **del equipo** y promedian al menos 5 minutos —umbrales relativos, `min_games_pct` y `min_avg_min`—; el resto es «marginal» y no entra en el Gini, el CV ni el quinteto).

### Seguridad de la API (`require_admin`, `ADMIN_API_KEY`, `X-Admin-Key`)
- **Seguridad**: no hay usuarios ni roles
- **el servidor no recibe escrituras de la web desde #724** (se retiraron `DELETE collections`, `scrape/*`, `historical/ingest*` y el servicio scraper: los datos los carga el refresco programado del archivo y se retiran con la purga) y **ninguna ruta exige ya la cabecera `X-Admin-Key` = `ADMIN_API_KEY`**: el entrenamiento del predictivo (`elasticity/train*`) se retiró con él (#853).
- La guarda (`src/api/security.require_admin`; guía en [OPERATIONS.md](OPERATIONS.md)) queda como patrón para la próxima escritura y se prueba sobre una aplicación pequeña
- `tests/test_admin_auth.py` obliga a clasificar todo endpoint de escritura nuevo (protegido o en la lista pública explícita) y `tests/test_server_writes_retired.py` exige que no quede ninguna que la pida.
- El resto de la API es de lectura/cómputo y público.

## Servicios (`src/services`)

### Estadísticas y análisis (`team_stats_service`, `team_comparison_service`, `pbp_extended_stats_service`)
- `team_stats_service`
  - `team_comparison_service` (comparativas bajo demanda, #607: `GET /teams/{collection}/compare?by=venue|result|period[&from_date&to_date]` llama dos veces a `load_season_data` con los dos lados y devuelve por equipo ambos grupos y la **diferencia real** a−b, para el equipo y para lo que le hicieron los rivales; un tramo `period` es el rango y «el resto» su `$not`, que el pipeline FBCYL normaliza a inicio de día
    - público, solo lectura), `player_stats_service`, `evolution_service`, `match_analysis_service`, `multi_phase_service`, `lineup_service`, `rotation_service`, `rival_adjusted_service`, `collection_service`, `_consistency_calculator`
  - `_possession_stats_builder` (entradas de posesión por equipo de `team_stats_service`, puras)
  - `pbp_situation_stats_service` (situaciones y tiempos muertos de temporada con `aggregation/pipeline_situation_stats`; versión mínima 4)
  - `pbp_extended_stats_service` (suma `DERIVED` por equipo con `aggregation/pipeline_points_origin` y `pipeline_period_stats`; descarta partidos `unreliable` y los cuenta; caché de 1 h; todas exigen `DERIVED` v5, que trae `reliable`; los partidos no fiables se dejan fuera y se cuentan en `games_unreliable`; `games_doubtful` cuenta los usados con roturas de alternancia —guardado en las respuestas, la web no lo muestra, #392—) y, en `src/database`
  - `possession_stats_helpers` (funciones puras del mixin de posesiones).

### Conexiones de asistencia (`assist_links`, `assist_connection_service`, #773)
- `assist_links` (por partido, FEB y FBCYL: enlaza cada asistencia con la canasta de campo que la precede, mismo reloj y equipo, y la canasta con su zona —FEB: tiro del `SHOTCHART` con igual cuarto, tiempo, equipo, jugador y acierto; FBCYL: tiro con el mismo `eventUuid`—
  - las asistencias que no se pueden enlazar se cuentan aparte) y `assist_connection_service` (suma por equipo: receptores —canastas y **puntos de campo** asistidos, % del equipo, zonas asistidas/sin asistir—, pasadores —con a quién encuentran, **desde dónde anotan los que reciben sus pases** (zonas de las canastas que crearon, total y por receptor) y las asistencias sin zona conocida—
  - **sin umbral mínimo**, el usuario ordena; un solo recorrido de la competición con `get_all_teams`).
- Se publica en `web-data` como sección `assist_connections` (`local_data/assist_connections_export`), dataset `assist-connections` del interruptor y página `ConexionesPage` (`/:colección/conexiones`, `AssistZoneCourt`: una pista, burbuja por zona con anillo partido entre asistidas y no).

### Capacidades por competición (`requires` en `lib/nav.ts`, matriz FEB/FBCYL/NCAA/FIBA, #1099)
- **Capacidades por competición (#1099, #1100, épica #1102)**: **toda página de una competición declara en `lib/nav.ts` la sección que necesita** (`requires`, 16 de 16 menos el resumen; un test lo exige y otro que toda ruta de `App.tsx` pasa por `guarded(...)`), así que **una página se ofrece solo donde la competición tiene esa sección publicada y se oculta donde el origen de los datos no la trae**
- la dirección directa de una página no disponible dice «No disponible para esta competición: el origen de los datos no lo trae o todavía no está publicado» con un enlace al resumen (ya no vuelve en silencio).
- Matriz medida el 26/11/2026 sobre los manifiestos publicados (`lib/capabilities.test.ts` la fija):

| Página (sección) | FEB | FBCYL | NCAA | FIBA |
|---|---|---|---|---|
| Equipo, Comparativas, Multifase, Evolución, Individual, Rankings, Informe semanal (`rows`) | sí | sí | sí | sí |
| Posesiones, Combinaciones, IN/OUT, Rotaciones, Análisis de partido, Scouting del rival, Informe de equipo (`possessions`, `lineups`, `inout`, `rotations`, `matches`, `reports`) | sí | sí | sí | sí |
| Gráficos de tiro (`shots`) | sí | sí | sí | **no** (FIBA no trae coordenadas) |
| Análisis pbp (`derived`) | sí | sí | **no** | **no** |
| Conexiones de asistencia (`assist_connections`) | sí | sí | **no** | **no** |
| Previa y Simulación (`calendar`) | solo la temporada más reciente | sí | **no** | **no** |

- Lo que «no» se puede cerrar o no se decide en #1101 (asistencias, `derived`, calendario)
- los tiros de FIBA y la baja y racha sin jugar (FEB) son por origen.

### Páginas que dependen de una sección de `web-data` (`RequirePublished`, `useVisibleNavGroups`, #780)
- `NavItem.requires` (sección y dataset) en `lib/nav.ts`
- `useVisibleNavGroups` (menú y tarjetas del resumen) y `RequirePublished` (la ruta dice que no está disponible) leen del manifiesto qué secciones tiene la competición (`webdata/client.publishedSectionsOf`) y **ocultan** la página hasta que existe (nada mientras se lee ni si el manifiesto falla)
- con `?data=api` siempre se ofrece.
- `web-data.yml` se lanza además con un `push` a `main` que toque lo que da forma a los ficheros (#781).
- Protocolo completo: [OPERATIONS.md](OPERATIONS.md#protocolo-de-despliegue-épica-784).

### Predictivo antiguo retirado (#853)
- Predictivo antiguo retirado del servidor (#853; servicios retirados: [historia](evaluaciones/2026-11-27_historia-architecture.md)): la previa y la simulación se calculan en el navegador (`frontend/src/forecast/`, ver más abajo) sobre `web-data`
- lo que necesita scikit-learn (los estudios de `scripts/`) está en `requirements-research.txt`, no en `requirements.txt`.

### Live, refresco y catálogo (`match_schedule_service`, `competition_refresh`, `competition_catalogue`, `inout_service`)
- `match_schedule_service` (próximos/en directo de un equipo desde el calendario de FEB)
  - `feb_match_ingest` (scrape incremental de un grupo FEB, compartido por el router `scrape` y por el refresco del archivo)
  - `competition_refresh` (CLI `run_refresh.py`: scrape de `config/competitions.json` + comprobación de frescura; lo ejecuta `archive-refresh.yml`, #724)
  - `fbcyl_match_ingest` (**#724**: el scrape incremental de un grupo de FBCYL, compartido por el router `scrape` y por el refresco)
  - `catalogue_batches` (**#876**: activa por tandas las temporadas pausadas del histórico y de la formación; `run_catalogue_activate.py`)
  - `refresh_state` (**#924**: colecciones cerradas y partidos que fallan, guardados en días en `COLLECTION_META`; el refresco omite lo cerrado y deja de pedir lo que no llega)
  - `fbcyl_catalogue` (**#920**: qué competiciones autonómicas de FBCYL entran en el catálogo —cadete y júnior, sénior; no infantil, provincial ni escolar— y cómo se llaman; `run_fbcyl_catalogue.py` las añade)
  - `competition_category` (**#914**: `category` sénior/formación, `age_group` U12/U14/U16/U18 normalizado (minibásket, infantil, cadete, júnior) (U15 es cadete y U17 júnior; **U19–U22 son sénior**, sin grupo, #918) y nombre legible de cada competición, validados al cargar el catálogo y publicados en los dos manifiestos)
  - `competition_catalogue` (**#724**: el catálogo único de competiciones, `config/competitions.json`: una entrada por competición y temporada —FEB, o un grupo de FBCYL con `"league": "fbcyl"`— con el scrape, lo que saben de ella los paquetes —nivel, género, clubes, reglas, `packages_groups`— y los calendarios del grabador; `active: false` pausa sin borrar datos; da las vistas del refresco —`load_config` de `competition_refresh` también lo lee—, de los paquetes —`publisher.load_config` y `_collections`— y del grabador —`recorder.load_watchlist`—)
  - `data_freshness_service` (colección vs calendario de FEB: `missing_codes`, `up_to_date`)
  - `collection_meta` (metadatos por colección guardados al hacer scrape: `COLLECTION_META`)
  - `inout_service` (**#334**: el análisis IN/OUT de una jugadora tal como lo ve la web, con las claves `on`/`off` y las métricas avanzadas; lo responde el endpoint y lo publica `local_data/inout_export` sin importar el servidor).

### Relleno de `DERIVED` y datos históricos (`derived_backfill`)
- sin ingesta a `HISTORICAL` desde #853 ([historia](evaluaciones/2026-11-27_historia-architecture.md)).
- Relleno de `DERIVED`: `derived_backfill`.

### DOCX del scouting individual e informe semanal en el navegador (`lib/scoutingDocx.ts`, `lib/weeklyReport.ts`)
- **DOCX del scouting individual en el navegador (#717, 17b)**: `lib/scoutingDocx.ts` (biblioteca `docx`, carga perezosa) hace una página por jugador del equipo —cabecera, identidad con la edad calculada hoy desde la fecha de nacimiento, tablas de promedios, totales y avanzadas con el sombreado por cuartil de toda la liga y las notas— con las imágenes publicadas (`images/`, 17a; sin ellas, sin foto ni fecha)
- **desde #1082 no hace página a quien tiene una baja ya alcanzada en su línea del equipo** (`lib/playerAvailability.ts` `hasLeftTeam`; sus cifras siguen en la liga contra la que se colorea) **y desde #1083 la primera línea de las notas es «‹nombre› llega desde dd-mm-aaaa sin jugar (X partidos)»** (`staffNotes`: la racha actual de partidos de su equipo sin fila con minutos, contada desde su alta; solo FEB; el gemelo del servidor filtra la baja pero no escribe esta nota)
- el hook `lib/useLeftPlayers.ts` aplica la misma baja cuando se elige un equipo: **Jugadores → Individual** mantiene la fila **atenuada y con la etiqueta «Baja»** (sus cifras siguen en los totales del equipo; `DataTable` admite `rowClassName`), y el selector de `PlayerSelect` (IN/OUT) y la lista de **Tiros** lo ocultan (sin equipo, o sin clave/publicación/FBCYL, no se marca ni se oculta a nadie)
- `api/individualScouting.ts` elige navegador o servidor con el dataset `scouting`.
- Los gráficos (17c) son SVG con los colores del papel (`design/paper.ts`) que el navegador pasa a PNG con un canvas (`lib/svgImage.ts`): el radar (`lib/radarChart.ts`, mismos valores que `RadarChart`), y el mapa de calor y las zonas de tiro, que dibuja el mismo `FibaCourtSVG` de la web con un tema de papel (`lib/scoutingCharts.tsx`)
- sin tiros (FBCYL, sin datos) no hay perfil de lanzamiento, y un gráfico que el navegador no puede dibujar se omite.

#### Informe semanal en el navegador (`lib/weeklyReport.ts`, `lib/weeklyRows.ts`, #716, D4)
- **Informe semanal en el navegador (#716, D4)**: `lib/weeklyRows.ts` es el port de los `build_*_rows` de `_weekly_report_helpers` (mismas celdas y mismo cuartil, con vectores de paridad `weekly_rows.json`
  - el color es un `Tone` y no un hexadecimal), `lib/weeklyTables.ts` dibuja cada tabla como SVG con la paleta del papel (no el fondo oscuro de matplotlib: la web es clara por defecto), `localdata/lastMatch.ts` saca el último partido de un equipo de las filas del contrato (la fila ya trae las cifras del rival y las posesiones del partido) y `lib/weeklyReport.ts` arma los ficheros con las mismas carpetas y nombres que el ZIP del servidor (`General/01…06`, `{equipo}/1_Estadisticas_Individuales`, `2_Graficos_Lanzamiento`) y los comprime con `fflate` (carga perezosa, PNG sin recomprimir)
- `api/weeklyReport.ts` elige navegador o trabajo del servidor con el conjunto `weekly-report`, y la página muestra el progreso de los cinco pasos y el motivo si falla.
- Diferencias con el servidor: el «último mes» se parte por **día** (no por instante), los gráficos de jugadora se nombran solo con su nombre (el dorsal no está en el navegador) y falta lo que no se publica (sin filas, sin «último partido»)
- como en el servidor, lo que no se puede dibujar se omite y solo una clave que falta es un error.

### Informes y exportación (`report_service`, `weekly_report_service`, `team_report_service`)
- `report_service`, `weekly_report_service` (+`_weekly_report_helpers`), `individual_scouting_service` (+`_scouting_docx_helpers`, `_scouting_formatters`, `scouting_docx_tables`: las tablas de la página de cada jugador como datos —columnas, texto y color por cuartil—, que usan el servicio y el navegador), `pdf_generator`, `possession_export_service`, `pbp_quality_service`, `player_data_fetcher`, `team_report_service` (datos → `report_engine`).

## Base de datos (`src/database`)

### Paquete `src/database`: manejador, repositorio y salud
- Conexión, repositorios, pipelines de agregación, índices, `shared_handler` (el manejador único del proceso, del servidor y de la publicación) y `db_health` (clasificación segura de los fallos de la base).

### Conexión y colecciones (`db_config`, `get_collection_name`, `is_fbcyl`)
- `db_config.get_mongodb_connection_string()`: env `MONGODB_CONNECTION_STRING` → `src/database/db_credentials.txt` (no versionado) → valor por defecto.
- BD `BASKETBALL`, un `MongoDBHandler` (fachada) sobre `BasketballRepository` (+mixins `repository_games/_inout/_lineup/_possession`).
- Colecciones de partidos: `{competición}_{temporada}_{grupo}` saneado (`get_collection_name`)
- prefijo `FBCYL_` = formato FBCYL (`is_fbcyl`).
- (`HISTORICAL` y `ELASTICITIES`, de un predictivo que ya no existe, #853, no se leen ni se escriben; `CollectionService` las ignora si una base antigua aún las tiene.)

### `aggregation/` e índices (`pipeline_builder`, `possession_expr`, `IndexManager`)
- `aggregation/` (pipelines FEB y FBCYL; los de FEB se componen en `pipeline_builder` con los mixins `pipeline_team_stats` (base y temporada), `pipeline_team_per_game` (una fila por equipo y partido) y `pipeline_opponent_stats`; `feb_date_expr` = la fecha de inicio de FEB (`HEADER.starttime`) leída una sola vez para pipelines, repositorio y evolución; `possession_expr` = expresiones de posesiones, rebotes y pérdidas que leen `DERIVED` con respaldo al boxscore), `indexes.py` (`IndexManager`, siempre `background=True`).

### `DERIVED` por partido (`insert_boxscore`, `derived_backfill`, #372)
- **`DERIVED` por partido** (#372): `insert_boxscore` lo calcula al ingerir (un fallo no impide guardar, pero **deja un aviso en el log con el código del partido**, #630)
- `GET /possessions/{collection}/derived-coverage` (`DerivedCoverageService`: partidos sin el `DERIVED` que piden las tablas pbp, con los equipos de los primeros 50) y la pestaña «Análisis pbp» lo dice («N de M partidos sin procesar»)
- `src/services/derived_backfill` + `run_backfill_derived.py` lo rellenan en lo ya guardado (idempotente; recalcula si sube `DERIVED_VERSION`).

### Calculadoras PBP de BD (`inout_calculator`, `lineup_extractor`, `possession_analyzer`)
- Calculadoras PBP de BD: `inout_calculator`, `lineup_extractor`, `lineup_stats_calculator`, `possession_analyzer`
- las dos primeras que cuentan acciones comparten el cubo de contadores y sus ayudas en `pbp_stat_counters` (#200, #452), y cada una conserva sus reglas (qué palabras son un fallo, qué fuentes cuentan un robo), que fija el fichero de caracterización de TESTING
- lo que `repository_inout` necesita saber de UN partido (quién es la jugadora en él, si jugó y si su equipo estaba) son funciones puras de `_inout_game_lookup`.

## Frontend Analytics (`frontend/src`)

### Stack, tema, navegación y caché de consultas (`lib/theme.ts`, `lib/nav.ts`, `queryKeys.test.ts`)
- Vite + React + TS + TanStack Query + Tailwind + Recharts/D3
- **tema claro por defecto, oscuro o del sistema** (#188: tokens de `design/` con el preset de Tailwind, `lib/theme.ts` sobre `design/theme.ts`, selector `components/ThemeControl` en la cabecera, script anti-parpadeo en `index.html`, colores de gráficos con `lib/chartTheme.ts`
  - navegación de una competición en `lib/nav.ts` (barra lateral agrupada, menú modal en el móvil, selector de competición en la cabecera y tarjetas del resumen, #191); marca de `design/brand` en `components/BrandLogo` y en `public/` con `npm run brand`, #189; ver design/README.md) (**regla de la caché de las consultas, #605**: una clave de `queryKey` guarda UNA forma de respuesta
  - dos sitios con la misma clave y distinta función se leen los datos el uno al otro según el orden de las visitas y el fallo desaparece al refrescar el navegador; lo vigila `frontend/src/api/queryKeys.test.ts`)

### Análisis pbp y Comparativas (`api/pbpExtended.ts`, `pages/ComparativasPage.tsx`, `DiffBadge`)
- `api/pbpExtended.ts` (tipos y hooks de `points-by-origin`, `by-period`, `situations` y `timeouts` de `/possessions`; página «Análisis pbp», ruta `pbp`, #359)
  - `pages/ComparativasPage.tsx` (ruta `comparativas`, #607: local/visitante, ganados/perdidos o un tramo con atajos de 30 y 15 días; cada celda = valor + diferencia con `DiffBadge`, verde bueno y rojo malo, invertido en la vista de rivales) con las columnas compartidas en `lib/teamColumns.ts`
  - `components/ui/DiffBadge.tsx` (la diferencia real que sustituye a las flechas de tendencia, #608; el informe semanal PNG dice lo mismo: `73.0 (+2.1)`) (sin página Administración —`/admin` redirige al inicio— ni predictivo antiguo —`/predictive` redirige a «Previa del partido»—; `getRivalAdjusted` y `getLiveTeamNames` viven en `api/teams.ts` y `api/collections.ts`; retiros #724 y #852: [historia](evaluaciones/2026-11-27_historia-architecture.md))

### `datasource/`: conmutador local/API y conjuntos de datos (`switch.ts`, `fromSource`)
- `datasource/` (**#329**; el conjunto `scouting` (#638) lo leen `getScoutingScopes` y `getPublishedScouting`, y la página «Scouting del rival» muestra **Liga; Copa; Agrupado** cuando el rival tiene scouting de copa; la migración sin «big bang». `switch.ts`: qué **conjuntos de datos** leen los ficheros publicados y cuáles la API
  - **desde #334 el valor por defecto es local para todos** (sin nada guardado ni en la URL, o con almacenamiento bloqueado
  - **desde la parte 2 de #334 no hay respaldo a la API**: si los ficheros no pueden responder, `fromSource` lanza `DataNotAvailable` —«estos datos no están disponibles todavía para esta competición o no se pueden calcular sin servidor»— o el error de los ficheros, que ya dice por qué, y devuelve un valor neutro solo donde el llamador lo dice (`whenUnavailable`: «nada publicado» es una lista vacía en el scouting del rival)
  - TanStack Query no reintenta ese error); `?data=api` fuerza la API para todos (se recuerda), `?data=local` vuelve al valor por defecto, `?data=local:team-report,team-stats` activa solo esos y el resto lee la API, y se recuerda en el navegador (`localStorage`; un valor guardado dañado es el valor por defecto); la cabecera muestra «Datos de la API» (con los conjuntos que la leen) si alguno la lee
  - **el manifiesto lleva además `possessions/`, `possession_csv/`, `matches/`, `shots/`, `rotations/`, `lineups/`, `inout/`, `consistency/` y `rival_adjusted/` (#678, #686, #685, #684, #709, #710: ficheros por competición, sellados igual) y `derived/` (#676, bloque B): el `DERIVED` de cada partido —una fila por partido con sus dos entradas `DERIVED.TEAM` y los nombres de los equipos—, sellado por competición en un fichero aparte para que las tablas de temporada no lo paguen
  - es el insumo de las pestañas de Análisis PBP**; **las filas de las que se calculan salen de `rows/` de la publicación (`webdata/client.loadWebRows`: sellado por competición, clave abierta en la beta o invitación; #673) y `local-data/`, la exportación manual de `run_local_export.py`, es solo el respaldo de desarrollo**
  - los conjuntos son `team-stats` y `player-stats` —los que leen `getTeamStats`/`getPlayerStats`: Resumen, Estadísticas de equipo, Individual, Rankings, Gráficos de tiro, IN/OUT, Combinaciones, Rotaciones—, `team-comparison` —Comparativas (#670): `localdata/comparison.ts` calcula en el navegador local/visitante, ganados/perdidos y tramo contra el resto con los mismos filtros que las tablas,
    - el complemento de un tramo es `outsideDates`—, `multi-phase` —Multifase (#671): `localdata/multiPhase.ts` es el port de `MultiPhaseService` (suma lo que se cuenta y recalcula medias, porcentajes y ratings, con sus rarezas) y de los hermanos de una colección, que salen de los nombres que publica el manifiesto
  - si una de las fases no está publicada contesta la API, nunca una mezcla a medias—, `possessions` —Posesiones (#679): la tabla de la página (el endpoint no tiene filtros), la consistencia de los equipos y el CSV de calidad se calculan al publicar y se leen de `possessions/`; el CSV por posesión, aparte en `possession_csv/` y solo al pulsar el botón; las dos descargas se hacen en el navegador con un solo BOM
  - informe en `evaluaciones/2026-10-30_posesiones-publicadas.md`—, `matches` —Partidos (#677): la lista y el análisis de cada partido (`MatchAnalysisService`) se calculan al publicar y la página los lee de un solo fichero por competición (271 partidos: 1,6 s y 0,11 MB comprimidos)—, `shots` —Tiros (#685): `localdata/shots.ts` cuenta las zonas, su valoración frente a la distribución de la competición (`rate_zone`, #760) y los tiros crudos del `shots/` publicado,
    - que lleva equipo y jugador de cada tiro en el orden de la competición— `rotations` —Rotaciones (#684): el análisis de cada equipo (`RotationService` con sus umbrales por defecto) se calcula al publicar y la página lo lee sin esperar al stream—, `player-consistency` —la consistencia por jugador de `PlayerStatsPage` (#709): la respuesta de `GET /players/{col}/consistency` (media, desviación, CV y partidos de 26 estadísticas en FEB y 18 en FBCYL) se calcula al publicar con la función del propio endpoint (`src/local_data/consistency_export.py`
  - sus cifras por partido salen de los pipelines por jugador de cada liga, no de las filas del contrato: 64 KB comprimidos y 0,5 s para 279 jugadores) y la página la lee tal cual—, `rival-adjusted` —el rating ajustado al rival de `TeamStatsPage` (#710): la respuesta de `GET /teams/{col}/rival-adjusted` se calcula al publicar con la función del propio endpoint (`src/local_data/rival_adjusted_export.py`) —empareja las dos filas de un partido por su marcador cruzado, no por `match_id`, una rareza que un port tendría que reproducir
  - unos 2 KB comprimidos por competición— y la página la lee tal cual—, `inout` —IN/OUT (#678): el análisis de cada jugador de FEB (`GET /players/{col}/inout/{id}`, la misma función del endpoint, con sus cifras avanzadas) se calcula al publicar (`src/local_data/inout_export.py`: unos 5 min y 119 KB comprimidos para 279 jugadores) y la página lo lee sin ir a la API
  - no hay nada que fusionar porque el endpoint no tiene filtros. **FBCYL también (#711)**: su tabla lista al jugador por el `actorId` de un partido (cambia de un partido a otro) y el análisis busca el `uuid`, así que las páginas identifican al jugador con `playerKey` (`player_uuid` si lo hay, si no `player_id`; `PlayerSelect`, IN/OUT y la consistencia) y el IN/OUT de FBCYL se publica por `player_uuid`
  - el análisis «dos jugadoras juntas» (`/together`, `getPlayersTogether`) se retiró con #200: ninguna página lo usaba—, `lineups` —Combinaciones (#686): `lineups/` publica, por equipo, los contadores de cada combinación de 2 a 5 jugadores **en cada partido** (`src/local_data/lineups_export.py`, el mismo bucle que el servicio: `iter_game_lineups` de `repository_lineup`) y `localdata/lineups.ts` los fusiona como `_merge_lineup_stats` (tamaño, estadística, período, mínimos, último partido, desglose por partido e IFQ, con sus redondeos
  - el ORB% es sobre los totales, con `opp_drb` publicado por partido, #691); el período se cuenta desde el instante del partido (`game_at`) y un partido con fecha ilegible queda fuera de cualquier período y del último partido. 118–141 KB comprimidos por equipo de FEB con la temporada completa (≈ 2 MB y ≈ 8 min al publicar una competición de 17 equipos
  - informe en `evaluaciones/2026-10-30_tamano-combinaciones-rotaciones-tiros.md`)—, `pbp` —Análisis PBP (#676): `localdata/pbp.ts` suma en el navegador, del `derived/` publicado, las cinco tablas (puntos por origen, por periodo, situaciones, tiempos muertos y cobertura) como los pipelines y servicios de Python; un partido cuenta si su entrada dice `reliable: true`
  - el publicado lleva también el total y los partidos sin `DERIVED` para la cobertura—, `evolution` —Evolución (#672; la serie de un equipo, #708: `teamEvolution` con fecha, rival, `won` y medias móvil y acumulada, exacta
  - deshacer el reescalado a 40 min de las posesiones redondea a 1e-9 para no sacar un ruido que cambie un redondeo en .xx5): `localdata/evolution.ts` reproduce `EvolutionService` (medias móviles y acumuladas de toda la competición por número de partido
  - una ventana fuera de 2–15 la dejamos a la API, que la rechaza, y una estadística desconocida se lee como puntos, como hace el router). Las posesiones siguen la regla de cada liga: en FEB las de la fila deshacen su reescalado a 40 minutos con `game_minutes`; en FBCYL siempre se estiman—, `team-report` y `report-teams` —el Informe de equipo
  - `getLiveTeamNames` (`{id, name}`) lee también la lista de equipos de su índice, ordenada como `$sort` (por unidad de código, no `localeCompare`) (#706)—, `collections` —la lista de competiciones (#705): `localdata/collections.ts` la saca del manifiesto (nombre, liga, partidos) y de los componentes del nombre (`parseComponents`, que usa también multifase), en el orden de `CollectionService.list_available`
  - no publica nada nuevo y no recorta a 100 como la API—; `player-stats` también da los cuartiles de los jugadores de `ShotChartPage` (#707: `localdata/playerQuartiles.ts`, `np.percentile` lineal con la interpolación desde el extremo más cercano de numpy, sin redondear; ≥ 3 partidos y ≥ 4 valores por campo); `getTeamsInCollection` (los nombres de equipo, `distinct`) sale de las filas de `team-stats` (#706)—

#### `datasource/resolve.ts`: política `fromSource`
- `resolve.ts`: **la única política** `fromSource(conjunto, local, api)`: activo → lee lo publicado
- si no puede (`null`, `DataUnavailable`) → la API como siempre
- `ScopedAccessError` **no** se contesta con la API
- cualquier otro error no se esconde
- para migrar una página: añadir su conjunto a `DATASETS`, escribir el lector local y envolver su llamada de `api/` con `fromSource`
- en lugar de una interfaz con dos clases se usan pares de funciones, porque los nombres públicos de `api/client.ts` no cambian y no se toca ninguna página
- la cabecera «Datos locales» dice cuáles)

### `forecast/`: previa del partido y simulación de la liga (`api/forecast.ts`, `useForecast`, `useSeasonSim`)
- `api/forecast.ts` (**#849**:
  - `getForecastInputs`, conjunto `forecast` del conmutador: las filas, el calendario —si lo hay— y el género de la competición desde `web-data`; **con `?data=api` o sin ficheros dice que solo funciona con los datos publicados**: la API no tiene predictivo), `forecast/inputs.ts`
  - `forecast/useForecast.ts` (la consulta y el modelo, una vez)
  - `forecast/fixtures.ts` (los partidos pendientes de un equipo, con el rival y el campo desde su lado, y el próximo)
  - `forecast/storage.ts` (equipo propio y líneas de corte por competición en `localStorage`, con `try/catch` y valores por defecto si está bloqueado o dañado)
  - `forecast/useSeasonSim.ts` (la simulación, tras pintar la página)
  - `forecast/study/` (**#851**: la evaluación walk-forward —`metrics`, `walkForward`, `report` y el runner `backtest.study.ts`, que no corre en el CI—), `pages/PreviaPage.tsx` + `pages/previa/` y `pages/SimulacionPage.tsx` + `pages/simulacion/` (**#850**: la tabla proyectada, el mapa de calor de puestos, las líneas de corte del usuario y los partidos decisivos; ver [UI.md](UI.md))
  - `forecast/` (**#846, épica #841**: el motor de la previa del partido y de la simulación de la liga, funciones puras en el navegador sobre lo publicado en `web-data`; de momento los modelos portados de Python con vectores de paridad: `normal.ts` —`erf` de fdlibm, `phi`, `bisect`—, `teamRatings.ts` —el rating Kalman de `live_prep.team_rating`—, `winProb.ts` —`headline`: la probabilidad de victoria al inicio del partido, con `WP_BY_GENDER`— y `factors.ts` —los cuatro factores, `pointsPerUnit` y el nivel de un equipo encogido a la liga a partir de las filas del contrato—; ver [LIVE.md](LIVE.md)

#### `forecast/` motor de la previa (#847: `gameLog`, `pool`, `scenarios`, `levers`, `preview`)
- **#847, el motor de la previa**: `gameLog.ts` —las dos filas de cada partido emparejadas en un partido (local, visitante, margen, ritmo) en el orden en que se jugaron, más los resultados del calendario que el archivo aún no tiene—, `pool.ts` —`buildModel`: ratings, nivel de cada equipo y la **bolsa de escenarios**: uno por partido y lado de la temporada, con lo que hizo cada lado frente a lo esperado,
  - el ritmo y el margen frente al rating, y desde #936 los puntos por 100 posesiones de cada lado frente a lo esperado (sobre las posesiones del partido: ritmo × minutos, así que una prórroga cuenta sus minutos) y el nivel de cada equipo en ellos, encogido a la liga como los factores—, `scenarios.ts` —`evaluate`: la bolsa jugada por un equipo propio contra un rival, **anclada para dar exactamente la probabilidad del pronóstico**
- cuatro tramos de margen con su perfil y `density`—, `levers.ts` —los objetivos de ataque y defensa: umbral = donde empieza el 25 % de escenarios de ese emparejamiento que mejor van en esa dirección, y P(ganar | se cumple), la parte de los partidos y el balance real de la temporada son **la respuesta de la proyección a esa condición** (`leverCondition` + `project`, #941: la tarjeta «¿Y si…?» da la misma cifra)
- condicional, nunca causal
- **lo que la evaluación no respalda es solo información** (`BandInfo`: lo esperado y el balance en el cuarto bajo y en el alto, sin probabilidad): el ritmo (#857) y los factores sin respaldo en `projection/variables.ts` (hoy nuestras pérdidas, 16/11/2026)
- `paceCandidates`/`bestPaceLever` quedan para que el estudio siga midiendo el ritmo—, `matchup.ts` —el emparejamiento factor a factor—, `preview.ts` —`buildPreview`: la composición, con la confianza baja si un equipo tiene menos de 5 partidos o hay menos de 30 escenarios (entonces solo el pronóstico)— y `copy.ts` —los textos en español, con la guarda de que nada promete ni dice «+N %»—

#### `forecast/projection/` proyección multifactorial (#936, #937, #938, #940, #941)
- **#936 (épica #935), la proyección multifactorial**:
  - `projection/` —`build.ts` (`buildProjection`: cada escenario jugado por estos dos equipos como un partido entero —posesiones, cuatro factores y puntos de cada lado = posesiones × minutos × puntos por 100 posesiones—, con un núcleo normal en los puntos de cada lado y un desplazamiento que **ancla la bolsa al pronóstico**)
  - `variables.ts` (el catálogo: posesiones del partido y, por lado, puntos, puntos por 100 posesiones y cuatro factores; `supported` dice si la evaluación respalda una cifra, regla de #857)
  - `conditions.ts` (una condición de posesiones o factores mete o saca el escenario; una de puntos es un intervalo de los puntos de ese lado; integración por escenario con Gauss-Legendre, **sin Monte Carlo**, decisión de #841)
  - `project.ts` (`project`: en los partidos como este donde se cumplen todas las condiciones, la masa, P(ganar), el perfil de todas las variables frente a lo esperado, el reparto de los puntos de más entre ritmo y acierto y el balance real de la temporada; sin cifra por debajo del 5 % de los partidos o sin respaldo)
- y `paceResponse.ts` (**#937**, la capa de cada equipo, opcional: la pendiente de lo que hace y deja hacer cada equipo —cuatro factores y puntos por 100 posesiones— frente al ritmo del partido, encogida hacia la de la liga por partidos / (partidos + k); `buildProjection(…, { paceResponse })` mueve cada escenario lo que esas pendientes dicen más allá de la liga a su ritmo, y sin ella la relación es la de la liga)
- **evaluada el 16/11/2026 (#938, [informe](evaluaciones/2026-11-16_proyeccion-multifactorial.md))**: la capa de equipo no llega a la página (la pendiente de cada equipo es ruido) y `variables.ts` deja sin cifra posesiones, pérdidas propias y puntos por 100 posesiones del rival
- el estudio es `forecast/study/projection.ts` + `projectionReport.ts` (`npm run study:projection`, a mano; también `rivalResponse`, si la respuesta de cada rival a lo que le hacemos es suya: no, es ruido) sobre `study/competitions.ts`, y `scripts/web_data_dump.py` (las filas publicadas como exportación local) y `scripts/pace_style_study.py` (duración × origen de las posesiones y estilo de cada equipo)
- condicional, nunca causal
- la usan los objetivos de la previa (`preview.ts` la construye y la deja en `PreviewDetail.projection`, #941) y la tarjeta «¿Y si…?» (#940): `project` da además el balance de la temporada del rival **en la misma situación** (`rivalRecord`: sus partidos con las condiciones vistas desde su lado, `variables.mirrored`), los marcadores de los dos balances y la dispersión de cada variable entre escenarios (`movers`: las dos que más se mueven, sin contar lo preguntado)
- `query.ts` escribe y lee las condiciones de la dirección (`?si=own.points.gt.70_rival.efg.lt.40`, porcentajes y tiros libres por 100, hasta 3) y sugiere el valor de partida (lo esperado del emparejamiento)—

#### `forecast/` simulación de la liga (#848: `seasonSim`, `standings`, `decisive`)
- **#848, la simulación de la liga**: `prng.ts` —mulberry32, Box–Muller y `hashSeed` (FNV-1a)—, `standings.ts` —la tabla y el **desempate genérico** (victorias, con el empate medio punto; los partidos entre los empatados: victorias y diferencia; la diferencia de toda la liga
  - un sorteo): no recursivo y sin puntos anotados, porque la simulación solo sortea márgenes y las bases de cada competición cambian con la temporada—, `seasonSim.ts` —`simulateSeason`: 10.000 temporadas con semilla = el nombre de la competición, sobre los partidos pendientes del **calendario real** (también los `live`), la fuerza de cada equipo sorteada **una vez por temporada** de N(rating, varianza del Kalman) y cada partido jugado con `σ_g = √max(σ² − v_local − v_visitante, 144)` más la ventaja de campo de la familia
- los resultados del calendario que el archivo aún no tiene cuentan para ratings y tabla
- el empate solo si el grupo lo permite, si no una moneda
- devuelve la distribución de puestos, victorias esperadas, P(1º) y un resultado por partido y temporada—, `pTop`/`pBottom` (las líneas de corte las dibuja quien lea la página, sin configuración en el repositorio) y `decisive.ts` —los partidos que más mueven el puesto esperado de un equipo, con lo que cada resultado hace a la probabilidad de una línea de corte—
- 10.000 temporadas del calendario real del LF Challenge (193 partidos pendientes) tardan ≈ 0,26 s en Node

### `webdata/`: lectura de `web-data` (`client.ts`, `loadWebSection`, `invite.ts`, `AccessPanel`)
- `webdata/` (**#328, #639**: lo que publica `web-data` leído desde el navegador: `client.ts` —manifiesto, índice de informes por competición y descifrado de cada informe con la clave abierta del manifiesto y las invitaciones del lector—, `loadWebSection<T>(sección, competición, mensaje)` (**#845**: el lector genérico de cualquier fichero sellado de una competición, sobre el que están los de cada sección), `calendar.ts` (`loadWebCalendar`: el calendario publicado, #842, con sus tipos
  - `loadWebCollectionInfos` lleva además el `gender` del manifiesto, #843), `WebDataUnavailable` para volver a la API y `ScopedAccessError` que **no** se contesta con la API; `invite.ts` —`#invite=bl1.…` guarda la clave y la quita de la dirección—; el descifrado, los derechos y las invitaciones son los de la app live, vía el alias `@live-package`, una sola implementación hasta la interfaz compartida #330
  - `VITE_DATA_BASE` cambia el anfitrión) con `components/AccessPanel` (pide la invitación; «Informe de equipo» la muestra si falta la clave) y `api/teamReport` (con `?data=local`, `getTeamReport` y `getReportTeams` leen `web-data`)

### `localdata/`: tablas calculadas en el dispositivo (`aggregateTeams`, `aggregatePlayers`, `source.ts`)
- `localdata/` (**spike local-first, #327**: las tablas de equipo, rival y jugador calculadas en el dispositivo a partir de las filas del contrato —una por equipo o jugador y partido—, sin servidor: `aggregateTeams` (FEB y FBCYL), `aggregatePlayers` + `advancedStats` (port de `live_core/advanced_stats`), `aggregatePlayersFbcyl` (**#644**: la tabla de jugadores de FBCYL, con su fórmula propia —suma por `(player_uuid, team_id)` de filas ya limpias— y su rival real
  - `source.ts` elige la agregación por liga) y `pyMath`; las filas las exportan `build_season_rows_pipeline`, `build_season_player_rows_pipeline` y `build_fbcyl_season_rows_pipeline` de `src/database/aggregation`; todavía no lo usa ninguna página)
- con `?data=local` (se recuerda en `localStorage`; `?data=api` lo apaga) `getTeamStats` y `getPlayerStats` de `api/client.ts` leen los ficheros de `local-data/` por `localdata/source.ts` —Resumen, Estadísticas de equipo, Individual, Rankings, Gráficos de tiro, IN/OUT, Combinaciones, Rotaciones
- **no** Comparativas, que usa `GET /teams/{col}/compare` y queda por portar— y la cabecera muestra «Datos locales»
- si la competición no está exportada, no tiene filas de jugador (una exportación anterior a #644) o falla la carga, vuelven a la API)

### `api/client.ts`, `components/ui`, `lib/` y rutas
- `api/client.ts` (**barrel de reexportaciones** desde #201: las llamadas y tipos viven en un módulo por dominio —`http`, `collections`, `teams`, `players`, `lineups`, `rotations`, `shots`, `possessions`, `matches`, `multiPhase`— y las páginas siguen importando de `@/api/client`; ningún módulo pasa de 500 líneas, lo vigila `api/moduleSize.test.ts`; `http.ts` guarda `BASE`, `get`, `post` y `downloadBlob`; `BASE` = `VITE_API_BASE`+`/api/v1`, scraper = `VITE_SCRAPER_BASE`), SSE con `EventSource` en lineups y rotaciones
  - `context/` (`CollectionContext`, `AuthContext` stub)
  - `components/ui` (componentes base de #190 —`Button`/`IconButton`, `Field`/`Input`/`Select`, `SegmentedControl`, `Tabs`, `Card`, `PageHeader`, `EmptyState`, `Spinner`/`Skeleton`, tonos de `Badge`/`StatCard` en `tone.ts`— y StatCard, FilterBar, DataTable, ExportButton…; guía en docs/UI.md)
  - `lib/` (utils, statLabels, exportDom, pdfLayout, zoneRating, quartiles, teamColumns, `useTeamOptions` —la lista `{id, name}` de equipos de las páginas que eligen uno—; `api/sseStream.ts` lee el análisis por SSE de lineups y rotations, #452).
- Rutas `/:collection/{teams,players,evolution,shots,rankings,report,team-report,scouting-rival,possessions,pbp,inout,lineups,rotaciones,…}` y `/admin`.
- Proxy dev `/api` → `localhost:8000`.

### Scouting del rival con «Nuestro equipo» sin servidor (`lib/scoutingCompare.ts`, #751)
- **Scouting del rival con «Nuestro equipo» sin servidor (#751)**: la comparativa propio-rival es una función pura de las filas de temporada de los dos equipos más las cifras de jugada a jugada, así que se calcula en el navegador: `lib/scoutingCompare.ts` (`compareTeams`, igual que `live_prep/scouting_compare.compare_teams`) con su catálogo `lib/statCatalog.ts` (el de `report_engine/catalog.py`
  - `scoutingCompare.test.ts` falla si se separan, con los vectores de `tests/local_vectors/scouting_compare.json` que genera Python) y `api/scoutingRival.getOwnComparison` (filas de `getTeamStats` + `getPointsByOrigin`)
- la página añade esa comparativa al informe publicado del rival, sin trabajo en el servidor.
- Con los ficheros como origen y nada publicado, la página lo dice en vez de lanzar un trabajo
- el trabajo del servidor (`startScouting`…) solo queda con `?data=api`.

## Frontend Talent (`frontend/src/market`)

### Talent: visión general (`frontend/market.html`, `src/market/`, `npm run build:market`, épica #872, B1 #877)
- **BasketLab Talent (épica #872, B1 #877)**: la tercera pieza de la familia (junto a Analytics y Live), **segunda entrada del mismo proyecto web**: `frontend/market.html` + `src/market/` (`main.tsx` con los mismos proveedores y tema, `MarketApp.tsx`), construida con `npm run build:market` (`vite build --mode market`; el plugin `talent-index` de `vite.config.ts` deja `market.html` como `dist/index.html` al escribir el bundle, para que el documento por defecto y el rewrite de `vercel.json` funcionen igual).
- Comparte `components/ui`, `design/`, `webdata/` y `localdata/`
- el build de Analytics no cambia.
- Proyecto de Vercel `basketlab-talent` (`basketlab-talent.vercel.app`, raíz `frontend`, sin variables de entorno).
- El nombre interno del código sigue siendo `market`.

### Talent: datos (`market/data.ts`, `createSealedClient`, B2 #878)
- **Datos (B2 #878)**: `market/data.ts` lee la rama `talent-data` (`loadTalentCompetitions`, `loadCompetitionRows`) con el mismo cliente genérico que Analytics, `webdata/sealedClient.ts` (`createSealedClient`: base, manifiesto, ficheros que nunca cambian en su sitio y desbloqueo con la clave abierta o las invitaciones)
- `webdata/client.ts` lo usa con su manifiesto y su rama.
- La base de Talent va fijada en `data.ts`, sin variable de entorno.

### Talent: buscador (`SearchPage`, `market/search.ts`, B3 #879)
- **Buscador (B3 #879)**: la ruta `/` es `SearchPage` (filtros en `SearchFiltersPanel`, reglas en `market/search.ts`, funciones puras sin React).
- Empieza en la **última temporada publicada** con sus competiciones (hasta 12; con más no elige ninguna) y la temporada, las competiciones y los filtros viven en la dirección (`s`, `c`, `amin`, `amax`, `hmin`, `hmax`, `pos`, `m`, `p`, `e`, `u`, `q`), así que una búsqueda se comparte con un enlace y un parámetro ilegible se ignora.
- **La edad es la del 31/12 del año en que empieza la temporada**.
- **Un dato que nadie dice es «sin dato», nunca 0**: la fila a la que le falta el dato que pide un filtro se oculta salvo «Incluir los que no tienen el dato», y la página dice cuántas ocultó y por qué campo.
- **Se pueden mezclar competiciones de distinta federación, nivel o sexo con un aviso** (el percentil es el del jugador en su competición, no comparable entre ellas).
- Posición por grupo G/F/C (`position_group`, #910).
- El CSV es el del resultado en pantalla (`ExportButton` de `DataTable`).

### Talent: ficha de jugador (`PlayerPage`, `market/player.ts`, B4 #880)
- **Ficha de jugador (B4 #880)**: la ruta `/jugador/:personId` es `PlayerPage` (reglas puras en `market/player.ts`, radar SVG en `PlayerRadar`; el nombre del jugador del buscador enlaza a ella).

### Talent: zonas de tiro (`src/market/zones.py`, `PlayerZones`, #994)
- **Zonas de tiro (#994)**: `src/market/zones.py` cuenta por jugador **y equipo** (la granularidad de la fila, clave `<person_id>|<team_id>`) los tiros anotados e intentados de las 10 zonas del motor (`live_core.zones`, mismo orden fijo), más los de toda la competición, con los tiros de `shotcharts.owned_shots` (los mismos que ve el mapa de tiro; un dorsal que no casa con nadie cuenta para la liga y para ningún jugador)
- cada recuento son 20 enteros `[anotados, intentados]` por zona.
- Se publica en **un fichero sellado propio por competición y temporada** (`zones` en su entrada del manifiesto, `TalentZonesEntry`), no dentro de las filas: el buscador no lo descarga, solo `PlayerZones` en la ficha (tabla «Tiros por zona» de la fila elegida con % y % liga; sin tiros o sin fichero se dice, nunca ceros).
- Los grupos de una competición se suman y un partido corregido que no toca los tiros no cambia sus bytes.

### Talent: comparador exportable y selección (`CompareBar`, `compareMemory`, #1009)
- **Comparador exportable y con selección (#1009)**: el comparador exporta la tabla (`ExportButton`: CSV con `Dato`, una columna por jugador y `Diferencia`; PNG y PDF de la tabla), y con **exactamente dos** jugadores añade la columna «Diferencia» (el segundo menos el primero, con los decimales de cada línea, `0` si es igual, nada si a un jugador le falta el dato: nunca contra un cero; el texto no tiene diferencia).
- En el buscador se **marca con casillas** a quién comparar (hasta tres; con tres, las demás se desactivan y se dice por qué) y `CompareBar`, pegada abajo, lleva al comparador con ellos elegidos
- la selección se recuerda en la pestaña (`compareMemory`) y la trae de vuelta la navegación.
- Sustituye al enlace por fila de #1008.

### Talent: encaje con tu equipo (`TeamFit`, `market/fit.ts`, C2 #883)
- **Encaje (C2, #883)**: tarjeta «Encaje con tu equipo» en la ficha (`TeamFit`, reglas puras en `market/fit.ts` sobre las de `myTeam.ts` y `similar.ts`; en el navegador, sin datos nuevos; el equipo es el recordado de «Mi equipo»).

### Talent: Mi equipo y huecos de perfil (`MyTeamPage`, `market/myTeam.ts`, C1 #882)
- **Mi equipo (C1, #882)**: página `/mi-equipo?c=<competición>&e=<equipo>` (`MyTeamPage`, reglas puras en `market/myTeam.ts`; sin datos nuevos, en el navegador).
- El staff **elige** el equipo de cualquier competición y temporada publicada, senior o formación
- queda en la dirección y se recuerda **solo en este navegador** (`myTeamMemory.ts`, `localStorage` con `try/catch`) hasta que haya cuentas (#896), y con la dirección vacía abre el último elegido.
- **Rotación** = quien tiene minutos suficientes (`eligible`) por minutos
- el resto, fondo de plantilla.
- **El hueco es de perfil de juego, no de posición** (decisión del 20/11/2026: tres pívots y ninguno que rebotee es un hueco en rebotes): un eje del radar que **nadie** de la rotación cubre, es decir, el **mejor** jugador de la rotación no llega al percentil 75 en él (el mejor, no la media: un reboteador cubre los rebotes aunque los demás no lo sean; percentil de cada jugador en su competición)
- solo se dice con al menos 5 jugadores de rotación y 3 con la cifra del eje (`axisCoverage`: los ejes del radar, cada uno con su mejor jugador, con **los dos de rebotes unidos en uno**: el percentil de un jugador en «Rebotes» es la media de su percentil ofensivo y el defensivo, y necesita los dos; la búsqueda que lo cubre pide el medio donde la rotación es más floja —rebotes ofensivos o defensivos— y lo dice).
- La **posición** (reparto por grupo con la parte de los minutos) y la **edad** (parte de los minutos de menores de 22 y de 30 o más) son información, nunca un hueco.
- Cada hueco enlaza al **buscador con los filtros ya puestos** (`suggestions`: percentil 75 o más en ese eje, con minutos suficientes; el mayor hueco —cuyo mejor jugador está más lejos del 75— primero): no hay ranking propio.
- Entrada «Mi equipo» en la navegación principal.

### Talent: PDF de la ficha (#1010)
- **PDF de la ficha (#1010)**: `Exportar` junto a «Comparar con otros jugadores» (`ExportButton` con PDF y PNG, sin CSV: la ficha no es una tabla de filas) captura la ficha entera —foto, datos, trayectoria, radar, parecidos y mapa de zonas
- no la navegación ni los botones— y la llama `ficha-<nombre>.pdf`
- la foto se cambia por las iniciales en la captura (`lib/exportDom`).

### Talent: anclas de la ficha (`SectionNav`, #1010)
- **Anclas de la ficha (#1010)**: `SectionNav`, una navegación pegada arriba («En esta ficha») con un enlace a cada sección —Datos personales, Trayectoria, Perfil, Parecidos, Zonas de tiro— que son `Card` con `id` (`Card` acepta `id` y deja `scroll-mt` para que la barra no tape el título)
- anclas del navegador (`#zonas`, sin enrutado propio)
- en el móvil los enlaces se parten en dos líneas en vez de un desplazamiento lateral.

### Talent: mapa de zonas de la ficha (`zoneChart`, `FibaCourtSVG`, #1010)
- **Mapa de zonas de la ficha (#1010)**: encima de la tabla «Tiros por zona», la **cancha de Analytics** (`FibaCourtSVG`) con una burbuja por zona con tiros (`zoneChart` en `market/zones.ts` convierte las líneas al formato de esa cancha): el color dice cómo está frente a la liga —por encima desde +8 puntos, por debajo desde −8, entre medias «en el promedio» (los 8 puntos de los informes de scouting, `zone_excess_pp`)— y una zona sin cifra de liga queda sin valorar, nunca inventada
- con menos de 10 intentos la burbuja va punteada (muestra pequeña: un jugador tiene muchos menos tiros por zona que un equipo, así que los 30 de los informes de equipo dejarían todas punteadas).
- El mapa va oculto a lectores de pantalla (`aria-hidden`): la tabla dice lo mismo en texto, como el radar y su lista.

### Talent: jugadores parecidos (`similar.ts`, `SimilarPlayers.tsx`, #1010)
- **Jugadores parecidos (#1010)**: la ficha lista los cinco jugadores cuyos percentiles están más cerca de los de la fila elegida (`similar.ts`, `SimilarPlayers.tsx`; sin datos nuevos, en el navegador con el fichero de la competición que la ficha ya abre).
- Solo cuentan las filas de **su** competición y temporada (nunca se mezclan competiciones) con minutos suficientes, y el jugador también debe tenerlos (si no, la tarjeta lo dice con la regla)
- la distancia es la raíz de la diferencia cuadrática media entre los percentiles de los ejes que **ambos** tienen (un eje sin dato se deja fuera, nunca un cero; hacen falta al menos 6 de 8), y el parecido es 100 menos esa diferencia (0-100, en puntos de percentil).
- No mira la posición, la altura ni la edad (decisión del 20/11/2026: la edad se ve junto a cada uno)
- un jugador cuenta una vez (su mejor fila) y nunca él mismo ni su fila enlazada
- empates por minutos, nombre, equipo e id (no depende del orden de las filas).
- Cada resultado enlaza al comparador con ambos.

### Talent: foto de la ficha (`lib/playerPhoto.ts`, `PlayerPhoto`, #1010)
- **Foto de la ficha (#1010)**: la ficha muestra la foto que FEB publica para el `idPlayer` (`imagenes.feb.es/foto.aspx?c=<id>`, `lib/playerPhoto.ts`, sin publicar ningún dato: la dirección sale de `feb:<id>`) en un círculo (`components/ui/PlayerPhoto`)
- si no carga, o el jugador es de FBCYL sin enlace (FBCYL no tiene dirección pública de la foto: la pide con token), salen sus iniciales, nunca una imagen rota.
- La foto es de otro origen y html2canvas no la pinta: en la exportación se oculta y la sustituyen las iniciales (`lib/exportDom`, como en las alineaciones).
- Es una petición del navegador a `imagenes.feb.es` (como los escudos).

### Talent: ejes del radar elegibles (`?ejes=`, `parseAxes`, #1014)
- **Ejes del radar elegibles (#1014)**: tarjeta «Ejes del radar» para ocultar, mostrar y subir o bajar cada eje (mínimo tres, un polígono no se dibuja con menos; los últimos tres no se pueden ocultar), con la elección en la dirección (`?ejes=tov,pts,ast`, nada si es la de por defecto, junto a `j`: son independientes) que siguen el radar, la tabla de percentiles y la exportación
- un eje desconocido o menos de tres vuelven a los ocho (`parseAxes`, `toggleAxis`, `moveAxis` en `compare.ts`) y «Restablecer los ejes» lo deshace.

### Talent: buscador en móvil y fichas de filtros (`FilterChips`, `activeFilters.ts`, #1008)
- **Buscador (#1008)**: en el móvil los filtros se pliegan tras un botón «Filtros (n)» (quedan a la vista la temporada y el nombre; desde `sm` está todo), los filtros activos son fichas que se quitan con un clic y «Limpiar filtros» (`FilterChips`, reglas puras en `activeFilters.ts`: palabras del panel, orden fijo, el 0 cuenta como límite, el percentil se va con su métrica), la lista sale por minutos jugados (empate por nombre y equipo, no depende del orden de entrada) y «Comparar» es una acción de la fila junto al nombre, no una columna de datos.

### Talent: navegación (`MainNav`, `compareMemory.ts`, #1007)
- **Navegación (#1007)**: la cabecera tiene `MainNav` (Buscar · Comparar, `NavLink` con `aria-current`; en el móvil va bajo la marca porque a 320 px no cabe a su lado) y el comparador recuerda su lista mientras la pestaña está abierta (`compareMemory.ts`, `sessionStorage` con `try/catch`: el enlace «Comparar» la trae de vuelta; la dirección sigue siendo la verdad).

### Talent: comparador y trayectoria (`ComparePage`, `market/compare.ts`, B5 #881)
- **Comparador (B5, #881)**: `ComparePage` en `/comparar?j=a,b,c` (reglas puras en `market/compare.ts`): de dos a tres jugadores de **cualquier liga**, cada uno leído en SU competición y su última temporada (un id de FBCYL enlazado es la persona de FEB y nunca sale dos veces)
- radar superpuesto (`PlayerRadar` con `others`, colores `--chart-N`), tabla con datos personales, cifras por 40 y el percentil de cada eje con el mejor marcado (todos los empatados, solo si al menos dos lo tienen; un dato que falta es un guion, nunca un cero) y el aviso de que un percentil no se compara entre competiciones.
- Solo abre las competiciones que contienen a los elegidos (`identities.by_feb` para la formación enlazada) y todas solo mientras se escribe un nombre para añadir
- la lista va en la dirección.
- Se llega desde un enlace «Comparar» en cada fila del buscador y desde la ficha.
- Reúne las filas de **una persona** de los ficheros de las competiciones **de su liga** (un id `fbcyl:` no abre ficheros FEB; mismas claves de caché que el buscador): trayectoria de la temporada más antigua a la más reciente con una fila principal por temporada (la de más minutos
  - empate por competición y equipo, así que el orden de entrada no cambia la respuesta) y qué cambió (competición, o solo equipo), datos personales campo a campo desde su fila más reciente que lo diga (con «de otra ficha» cuando la plantilla de esa fila no lo decía, `bio_from`
  - la posición fina gana al grupo G/F/C) y el radar de ocho percentiles de **una** fila en su competición y temporada, siempre con los números en una lista y nunca comparando competiciones.
- Lo que nadie dice es «sin dato», no un cero.
- Las zonas de tiro quedan en #994 (las filas publicadas no las llevan).

## Despliegue y config

### Despliegue: Vercel, CI y API sin alojamiento (#334)
- **Sin alojamiento de la API en el repositorio (#334, 05/11/2026)** y **conservada para desarrollo y pruebas** (decisión del 05/11/2026: no se elimina, y el rework del predictivo se resolvió sin ella en #841; los ficheros de test que importan `src.api` y el e2e dependen de ella): no hay `render.yaml` ni despliegue de la API
- `python run_api.py` sirve para desarrollo local, pruebas y el e2e (el servicio `basketlab-scraper` y `DISABLE_SCRAPING` se retiraron en #724: la API ya no scrapea ni ingiere nada).
- Frontend en Vercel (`vercel.json`: rewrite SPA). CI (`.github/workflows/ci.yml`): solo tests (backend repartido, web, e2e), sin despliegue.

### Variables de entorno (backend y frontend)
- Env backend: `MONGODB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `ADMIN_API_KEY` (ninguna ruta la usa hoy), `WEB_CONCURRENCY` (workers, 1 por defecto), `MALLOC_ARENA_MAX`, `LOG_MEMORY` (ver [OPERATIONS.md](OPERATIONS.md#memoria-servidor-pequeño-512-mb)), `ENVIRONMENT`, `DISABLE_SCRAPING`, `BASKETLAB_DEV`, `PORT`. Frontend: `VITE_API_BASE`, `VITE_SCRAPER_BASE`. Ejemplo en `.env.example`.

## Rutas de import
Usa siempre `src.…`. Los parsers PBP viven en `src/pbp` (sin BD); los antiguos shims se eliminaron (`tests/test_pbp_isolation.py` lo vigila). `tests/conftest.py` limpia cachés bajo ambos alias por compatibilidad con tests antiguos.

## Deuda conocida de arquitectura
Ver [ROADMAP.md](ROADMAP.md).
