# Evaluación: ScoutingFEB y el módulo «Mercado» (scouting de fichajes)

Evaluación de lectura del 12/11/2026 del repositorio `kanijoman/ScoutingFEB` (detección temprana de talento) y de si integrarlo en BasketLab. **No se ha tocado código ni el repositorio de ScoutingFEB.** Lo legal queda fuera por decisión del usuario (se da por bueno; #637 sigue aparcado).

**Veredicto: no se integra su código; se integra la idea, ampliada, como una app aparte («Mercado») sobre la misma plataforma.** Épica paraguas en GitHub (ver *Backlog*).

## 1. Estado de ScoutingFEB (leído del código, sin ejecutarlo)

Prototipo de 5 semanas (13/01–16/02/2026, 21 commits, 6 PR), parado desde entonces. El README dice «PRODUCTION-READY»; no lo es.

- Sin CI; dependencias sin versión; UI de PyQt6 probablemente rota (importa `evaluate_team` desde `examples/`, llama a clases que no existen); 8 ficheros de más de 500 líneas (`etl_processor.py`: 1.567); tests con mongomock y claves inventadas (`MIN`, `PTS`).
- ETL a SQLite (contrario a «MongoDB + pipelines»). Solo ligas femeninas sénior (LF Endesa, Challenge, LF2) desde 2001/02: unos 10.660 partidos. **Sin categorías de formación.**
- **Scraping duplicado**: mismas fuentes (`competiciones.feb.es`, `baloncestoenvivo.feb.es`, `intrafeb…/LiveStats.API`) y mismo token JWT, con menos robustez. Lo único que BasketLab no tiene es `legacy_parser.py` (boxscore desde el HTML anterior a 2019/20).
- **Analítica con fallos de fondo**:
  - tira el `idPlayer` de FEB (`feb_id` nunca se rellena) y consolida identidades por nombre exacto (`consolidate_identities.py`): funde homónimas;
  - escala de niveles invertida en `career_potential_calculator._get_level_multiplier` (3 = máxima) frente a `normalization.py` (1 = máxima);
  - R² de 0,88 con fuga de datos: `train_test_split` aleatorio por filas (`xgboost_model.py:341`) y medias de temporada que incluyen partidos futuros;
  - el objetivo (puntos de la temporada siguiente) es rendimiento, no talento;
  - el «potencial» es una puntuación por reglas con pesos a mano; el XGBoost es aparte.

Se aprovechan sus errores como criterios «a evitar» de las sub-issues.

## 2. Comprobado con datos reales (11 y 12/11/2026)

| Pregunta | Resultado |
|---|---|
| Formación FEB | Mismo API que la sénior: CE clubes júnior/cadete (`g=21/22/35/36`), SSAA cadete (`g=40/41`). Boxscore y PBP desde **2020/21**; 2018/19 da 404 (solo HTML). Ej.: partido `2512382` (júnior fem. 2025/26). |
| `idPlayer` estable | **Sí** entre formación, LF2, Challenge y Endesa y entre temporadas y equipos (8 de 24 jugadoras de un partido júnior 2025/26, aunque cambie el nombre del equipo). |
| Nacimiento, altura, posición | En la plantilla (`/equipo/<id>`, `roster_fetcher.py`) y la ficha (`player_data_fetcher.py`). Hoy solo para live e `images/`. |
| FBCYL ↔ FEB por nombre | Clave exacta inicial + dos apellidos (`actorName` del PBP): 25 únicas, 0 ambiguas, 0 contra masculino; 21 corroboradas (club, provincia o doble licencia), 4 a revisión. Difuso: ningún acierto. Riesgo: hermanas con la misma inicial. |
| ACB | Viable, esfuerzo medio-bajo, **sin clave de API**: `acb.com` (Next.js) incrusta JSON en el HTML. Ficha con `birthDate`, altura, posición; boxscore, PBP y tiros desde 2019/20. ~6.000 jugadores en el sitemap; `robots.txt` lo permite. Enlace por nombre + fecha. Riesgo: formato interno de Next.js. |
| FIBA (selecciones) | Viable, esfuerzo medio: la página del partido de `fiba.basketball` trae boxscore, PBP con x/y y plantilla (`personId`, `dateOfBirth`, altura, club). Boxscore ~2006+, PBP 2019+. Genius LiveStats no sirve a FIBA (403). Enlace por nombre + fecha + club. |
| NCAA D1 | ESPN (`site.api.espn.com`, 200, ambos sexos): boxscore y PBP, `athlete id` estable. Histórico masivo en parquet de sportsdataverse (boxscore desde 2005, PBP ~2010). `stats.ncaa.org` y Sports-Reference: 403. |
| NCAA D2 | **No está en ESPN.** `sdataprod.ncaa.com` (GraphQL con *hashes* fijos, 200): boxscore y PBP de texto sin ids de jugador. Completo solo en 2025/26; femenino con boxscore desde 2022/23; masculino irregular 2023–25. Ids: femenino `wbb_id` (Sports-Roster-Data); masculino sin id (ids propios, traspasos a revisión). Sin fecha de nacimiento (salvo barttorvik, D1 masculino). |
| Volumen NCAA | ~21.000 partidos/temporada (ambos sexos): ≈ 90 MB gz solo boxscore, ≈ 335 MB con PBP. ~31.600 peticiones por temporada; día a día < 1.000. |

## 3. Piezas que ya existen (reutilizar)

`live_core/profiles.py` (tasas por 40 con encogimiento, z-score de rol, `role_distance`), `recommender.BALANCE_DIMS` y `LEVER_METRIC`, `package_builder.shrunk_team_level`, `live_core/advanced_stats.py` y su TS, `live_prep/level_gap.py` y `category_strength.py` (diferencia entre divisiones por equipo, solo masculino, `LEVEL_GAP_NET_RTG = 20`), `team_rating.py` (Kalman), `lib/radarChart.ts`, zonas (#685), regularidad (#709), cuartiles (#707). **Faltan**: buscador, «jugadores como X», comparador, huecos de plantilla, identidad entre fuentes y traducción de estadísticas por jugador.

## 4. Decisiones

1. **App aparte en la misma plataforma**: segunda entrada de `frontend/` (`market.html`, `frontend/src/market/`, `vite build --mode market`, segundo proyecto de Vercel), compartiendo `components/ui`, `design/`, `localdata/` y las versiones TS de `live_core`. No `apps/market-web/` (obligaría a sacar un paquete compartido sin valor propio). Datos y acceso propios (alcance `mercado`).
2. **Identidad**: `person_id` anclado al `idPlayer` de FEB; enlaces con método, puntuación y estado (FBCYL, ACB, FIBA, NCAA); correcciones desde la app, aplicadas por el pipeline al regenerar el registro (determinista).
3. **Formato canónico**: ACB, NCAA y FIBA se convierten al documento FEB en la ingesta (`_league` de origen, ids con prefijo de fuente) para no bifurcar pipelines (lección de `is_fbcyl`). Ojo: la NCAA masculina juega 2 × 20 min.
4. **Datos sin descartar nada, publicados por niveles**: guardar todas las temporadas completas; publicar completo la temporada en curso y la anterior, y para el resto todo lo del jugador más agregados de equipo (~400 MB para NCAA con 17 temporadas, en `basketlab-data-ext`, por debajo de 1 GB). Detalle antiguo por competición (tiros, en pista/fuera, informes) guardado y recalculable. Si hiciera falta publicarlo todo (~2,2 GB solo NCAA) se adelanta la migración a Cloudflare R2/Pages de #640.
5. **Almacén**: archivo privado aparte `basketlab-archive-ext` con *assets* de release de GitHub (documentación oficial: «no limit on the total size of a release, nor bandwidth usage», < 2 GiB por fichero; repo git ideal < 1 GB), caché de Actions, almacén intercambiable con S3 (R2/B2) como plan B y copia en frío mensual en Google Drive. Se descarta Drive como almacén de trabajo (token OAuth de usuario, caducidad en modo pruebas, cuota compartida). Revisa la política «ligera» de #646: las temporadas FEB cerradas pasan a *assets* completos.
6. **Refresco como mínimo diario** de la temporada en curso para toda competición nueva: un job por fuente (aislados), ventana de reescrapeo, comprobación diaria de cada fuente, issue automático si falla, frescura en el manifiesto y un test de cadencia.
7. **También en Analytics**: ACB, NCAA y FIBA como competiciones (`web-data-ext.yml`, rama `web-data-ext`, la web lee los dos manifiestos; selector por fuente → división → sexo → conferencia). Nada externo en los paquetes live.
8. **Método**: índices transparentes validados (walk-forward, una promoción fuera cada vez); ML solo como contraste. Grafo de equivalencias entre competiciones con incertidumbre para puntuar a un jugador en la competición objetivo; encaje con la plantilla (colisiona/complementa/sustituto) calculado en el navegador con vectores de paridad. Sin filtro por edad (hasta 25–26 años evaluables).
9. **Escritura del staff** (comentarios, seguimiento, correcciones): requiere persistencia, así que reactiva #153; funciones de Vercel + almacén documental pequeño + OIDC con espacio por club; se decide en #154. No se realoja `src/api` (#334).
10. **NCAA «a máximos»** (D1+D2 con PBP); repliegue acordado a boxscore + PBP de D1 reciente si el parser del PBP de D2 o el almacenamiento dan problemas.

## 5. Riesgos

Formato Next.js de ACB y FIBA; *hashes* de NCAA.com que cambian con cada despliegue (Akamai) y JSON de ESPN no documentado; D2 masculino sin ids ni biografía; NCAA/extranjero/ACB como censurados en las etiquetas; enlaces de FBCYL limitados por la cobertura (LF2 2026-27 aún no está en el archivo); GitHub sin SLA en el plan gratuito y con política de uso aceptable sobre ancho de banda.

## Backlog

Épica paraguas «Mercado: scouting de fichajes» con bloques A (datos e identidad), B (app de solo lectura), C (encaje), D (fuentes externas y almacenamiento), E (estudios) y F (escritura del staff, con #153). Orden: A → B → C → D → E, con F1 (decisión #154) en paralelo.
