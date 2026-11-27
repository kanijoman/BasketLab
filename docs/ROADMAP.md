# Hoja de ruta, deuda y límites (para Claude)
Actualizar al cerrar cada entrega (regla de [CLAUDE.md](../CLAUDE.md)). Estado detallado del motor live: [LIVE.md](LIVE.md).

## Mapa del documento
- `## Pendiente (fases abiertas)` -> qué fases quedan por hacer o cerrar (live, app, reglas, Talent, UI, predictivo, diferidos)
- `## Complejidad` -> qué funciones de `src/` superan el umbral de complejidad y por qué no se tocan
- `## Deuda técnica` -> ficheros >500 líneas, duplicación, límites de la API
- `## Límites conocidos` -> qué no cubre el sistema (datos, FBCYL, baja/racha, Talent)
- `## Backlog` -> dónde está la lista de tareas
- `## Hecho (resumen)` -> una línea por fase terminada y enlace a la historia detallada

## Pendiente (fases abiertas)
### 1. Live con datos reales
- **Live con datos reales** (hecho): el motor se ha validado con grabaciones y partidos reales de LF Challenge, 2.ª y 3.ª FEB, Primera FEB y la Copa de España (el directo se verificó con la Copa del 21/10/2026 y el resto de competiciones senior usan el mismo workflow, #442 y #436 cerrados); los umbrales se calibran con partidos (ver 5).
- Queda el **feedback individual del staff** (#235).

### 3. App Android
- **App Android** (`apps/live-android`): en uso por el staff con **release cada viernes** (0.3.x en octubre; 0.4.0 el 23/10/2026): modo demo y grabados, paquetes automáticos (rama `live-packages`), directo contra FEB, avisos locales de partidos, posesión en el marcador, revisión de partidos finalizados, informes PDF y borrado de grabaciones.
- **Pestaña Boxscore hecha en la 0.4.2 (#593)**: local/visitante, normal y avanzada (las 15 columnas de la web), quinteto en pista, última acción resaltada y degradado verde–blanco–rojo frente a la media del propio jugador;
- el coloreado contra el equipo rival y la tabla en el PDF posterior (#480) se **descartan**: la comparación no es intuitiva (superar la media del rival puede ser mérito propio o defensa floja) y su ajuste contra la realidad es de dudoso valor.
- Pendiente: publicar en Google Play (#454, aplazado), la reevaluación de los avisos de tiempo muerto con partidos reales (#524).

### 4. Informes por reglas
- Informes por reglas v1 completa (épica #145: zonas vs liga en FEB y FBCYL, sin mínimo de partidos, PDF sin cortes de fila). v2 diferida (#146).

### 5. Reglas live (épica #260)
- **Reglas live** (épica #260, **implementada**): el catálogo de [LIVE_RULES_CANDIDATES.md](LIVE_RULES_CANDIDATES.md) está integrado (43 reglas con interruptor por regla;
- 80 alertas en Zamora–León frente a 31 antes, tras enfriar el 22/10 `four_factors_lever`, `rival_foul_pair` y `comeback_plan` y añadir el 23/10 el análisis de cada tiempo muerto, propio o rival, con su seguimiento a los 2 minutos (`timeout_review`, `timeout_followup`: volumen a vigilar, #524)) con el evaluador (#238) para medirlas.
- **Calibración hecha** (#426, #427; [evaluación del 20/10](evaluaciones/2026-10-20_calibracion-de-umbrales.md): 753 partidos de LF Challenge de 3 temporadas): fatiga, pérdidas, rachas de tiro y zonas más estrictas y aviso de tiempos muertos al cierre de la 1.ª parte;
- **pendiente solo el feedback individual del staff (#235)**, que se anota por regla, y dos propuestas aplazadas (sequías 300/270/240 s y `wp_flip_drop` 0,25: sin ganancia de seguimiento medible); las aplazadas (#249 a #253) y la probabilidad de victoria (épica #261).

### 5. Modelos live (#122, #261)
- **Modelos live** (#122, cerrado): la probabilidad de victoria está evaluada y calibrada con replay de histórico (Brier, log loss, MAE, deciles con bootstrap; ver docs/evaluaciones/) y se muestra como experimental; épica #261 cerrada (reevaluada el 20/10 con 24 partidos de 2026/27: mismo desvío en la zona media pero sin muestra ni valor previo suficientes;
- repetir con ≥ 8 jornadas, [informe](evaluaciones/2026-10-20_probabilidad-de-victoria-2026-27.md); el 22/10, con 235 partidos, ya cumple el criterio sin mínimo de previos y queda pendiente repetirlo con equipos de ≥ 3 partidos previos, [informe](evaluaciones/2026-10-22_reevaluacion-2026-27.md); la tarjeta sigue experimental hasta ≈ 250 partidos con valor previo real).

### 6. Talent (épica #872)
- **Talent (épica #872, evaluación del 12/11/2026, [informe](evaluaciones/2026-11-12_mercado-scoutingfeb.md))** (**regla del histórico, 23/11/2026**: horizonte de 10 temporadas con tres niveles —archivo, filas por jugador y temporada, y secciones pesadas solo de la actual y la anterior—, ver OPERATIONS;
- **Euroliga masculina, spike #1038, 23/11/2026**: GO desde 2017/18, [informe](evaluaciones/2026-11-23_euroliga-spike-1038.md); **fuente hecha (D6a, #1038): `src/external/euroleague_*` —EuroLeague, EuroCup y torneo U18—, entradas pausadas con `run_euroleague_catalogue.py`; pendientes: activarla con su presupuesto y el enlace de identidad con FEB**;
- **Euroliga femenina, spike #1039, 23/11/2026**: GO **sin fuente nueva** —está en `fiba.basketball` con el nombre `euroleague-women-25-26` (formato `YY-YY`, no `YYYY-YY`) y se lee con la fuente de FIBA; 3 temporadas, 48 de 48 partidos fiables, la EuroCup femenina igual;
- falta añadir los eventos al catálogo de FIBA, [informe](evaluaciones/2026-11-23_euroliga-femenina-spike-1039.md)) (**NCAA D1, 23/11/2026, #888 y #966**: catálogo por conferencia con su id, cliente de ESPN, convertidor y fuente por lotes hechos y sin activar; [medición](evaluaciones/2026-11-23_ncaa-d1-888.md); pendientes: activar la 2025/26 (#1060), y NCAA D2, #889;
- hechos el filtro de equipos D1 al publicar, #1061, y el mapa de tiros, #1062): scouting de fichajes de cualquier edad (hasta 25–26 años evaluables) con desglose por competición, puntuación en la competición objetivo y encaje con la plantilla; sustituye a la proyección multi-temporada de #138 (cerrada) y al ScoutingFEB (no se integra su código).
- App aparte en la misma plataforma (segunda entrada de `frontend/`), identidad anclada al `idPlayer` de FEB, fuentes externas (ACB, FIBA, NCAA D1+D2, FBCYL) como competiciones también en Analytics, refresco diario, archivo `basketlab-archive-ext` y escritura del staff con #153.
- **Hecho hasta ahora**: bloque A (identidad, barrido de plantillas, catálogo de formación e histórico sénior, #900), B0/B1 (logo y segunda entrada de la web, #903) y B2 (#878: publicación `talent-data` con una fila por jugador, temporada, competición y equipo, lectura desde la app); A5 (#905: barrido diario de plantillas, que da edad, altura y posición a las filas);
- spike de formación en FBCYL y FIBA (#915, [informe](evaluaciones/2026-11-13_formacion-fbcyl-fiba.md): FBCYL autonómica GO, FIBA plantillas y líderes públicos, caja por partido desde la jugada a jugada pública, validada contra su API); FBCYL autonómica de minibásket hacia arriba, sénior y masculino en el catálogo (#920: 2026 activa, 2025 y 2024 pausadas, por tandas;
- **infantil (solo 1ª División) y minibásket entraron el 20/11/2026, #1025**, con los campeonatos de España de infantil y minibásket de FEB, clubes y selecciones, 2020 a 2025, y la Minicopa LF Endesa, 2021 a 2025; siguen fuera alevín, benjamín, premini, provincial y escolar);
- A4 (#876): histórico sénior y formación por tandas con `run_catalogue_activate.py` (tanda 1, 2023 y 2022, preparada); refresco del archivo eficiente (#924: colecciones cerradas, límite de reintentos, 27 → 11 peticiones por colección, refrescos parciales por temporada y liga); A6 (#910: biografía campo a campo entre fichas, temporadas y fuentes, altura en cm, posición canónica;
- la primera muestra del barrido traía altura en el 13 % y posición en el 10 %); B3 (#879: buscador con filtros y CSV; **pendiente al integrarse**: con la carga completa del barrido, medir cuánto mejora la cobertura de altura y posición); siguen B4–B5 (ficha, comparador).
- **ACB (#886, D2;
- 20/11/2026)**: la Liga Endesa desde 2019/20 está hecha de punta a punta y **pausada** —catálogo de ediciones, cliente (1 petición por segundo, presupuesto por ejecución), caja y jugada a jugada, biografía y tiros con coordenadas de las páginas de los jugadores, conversor al documento FEB, enlace con FEB por nombre y fecha de nacimiento (con el nombre de la ficha) y la fuente del refresco diario—;
- **pendiente**: la primera carga acotada (2025/26 con presupuesto bajo, activar `active: true`), la evaluación legal de ACEB (el aviso legal prohíbe la cesión a terceros sin consentimiento; decisión del usuario de seguir y evaluarla con el equipo legal) y, como límite conocido, que un partido guardado sin la página de un jugador no recupera su biografía ni su mapa de tiros;
- los códigos de jugada sin entender (9) se ignoran porque no cambian la caja.
- **Fuentes externas por venir, en este orden**: NCAA D1 y D2 (#888, #889) y **después la Euroliga masculina y femenina (D6, #1037: spike de la API pública de la Euroliga en #1038 y localizar el feed de la femenina en #1039)**.
- **Decidido (13/11/2026)**: NCAA se publicará **por conferencia y temporada**, una competición por conferencia (criterio en #884, #888 y #889), no como una lista plana de cientos de equipos y el resto.
- Orden A→B→C→D→E.
- El optimizador de quintetos sigue descartado (#138).
- **Escritura del staff decidida (19/11/2026, #895, [informe](evaluaciones/2026-11-19_escritura-del-staff-895.md))**: OIDC Google, base gestionada pequeña en la UE, espacio por club con tres roles y correcciones de identidad moderadas; pendiente su implementación (F2 #896, F3 #897, F4 #898, #980).
- **`web-data` solo publica la temporada actual y la anterior (19/11/2026, #991)**: el histórico completo queda en el archivo y en `talent-data`.
- **Ficha de jugador (B4, #880)**: trayectoria, datos personales y radar de percentiles; las zonas de tiro, hechas en #994 (fichero propio por competición, tabla en la ficha; un mapa de la cancha queda como mejora).
- **Comparador (B5, #881)**: 2 o 3 jugadores de cualquier liga, cada uno en su competición.
- **Mi equipo (C1, #882)**: rotación, huecos de perfil de juego (ejes que nadie cubre; la posición es solo información) y búsquedas ya filtradas;
- **Encaje (C2, #883)**: en la ficha, «Encaje con tu equipo» (el equipo recordado en «Mi equipo»): complementa (destaca, percentil 75 o más, en un hueco de la rotación), coincide (solo destaca donde ya destaca alguien, que se nombra) o es neutro;
- a quién sustituiría (el más parecido de la rotación, parecido de 85 % o más, regla de los parecidos) y los huecos del equipo con y sin él, avisando del que se abre.
- **Límite conocido**: los percentiles son los de cada competición, sin traducir; si el jugador es de otra competición el encaje es orientativo hasta el grafo de equivalencias (E1, #891; **E1c hecho: `talent-data` publica `equivalences` con un único estimador final por jugador**, **E4b hecho: la ficha enseña «En otra competición» con el rango del 80 % por eje;
- E3 (#893) medido el 20/11/2026: el índice de formación (lo esperable en el sénior **si llega**) reduce un 11 % el error frente a la media de los que llegan y su rango del 80 % acierta el 79,5 %;
- **E3b hecho: `talent-data` publica `formation`**, **E3c hecho: la ficha de un jugador de formación enseña «Si llega al sénior» con el rango del 80 % y la salvedad de que no es la probabilidad de llegar**;
- E2 (#892) medido el 20/11/2026: la curva de edad existe (+0,1 z a los 16, ≈ 0 entre 22 y 29, −0,07 z a los 33 en hombres) pero mejora menos de un 1 % la proyección, así que no se enseña; lo que valdría mostrar es la proyección sin edad (`ρ·z` con rango, cobertura 79,5 %);
- E4c hecho: el encaje con «Mi equipo» juzga el perfil traducido a la competición del equipo (centro del margen) y dice qué ejes del veredicto aguantan en el extremo bajo**;
- sin formación ni FBCYL, que esperan a E2/E3 —la formación mezcla la edad con el nivel— y a más enlaces de identidad —solo 13 personas pasan de FBCYL sénior a FEB sénior, medido el 20/11/2026—) y la puntuación en la competición objetivo (E4, #894).
- Sin optimizador de quintetos ni minutos simulados.
- **Ficha (#1010)**: hechas la foto, los jugadores parecidos, «minutos suficientes» (10 min/partido y un tercio de los partidos del equipo), el mapa de la cancha, las anclas y el PDF.
- **Identidades consumidas (#996, D1b)**: los jugadores de FBCYL con enlace `linked` son la misma persona que la de FEB (`linked_to`, ficha unificada con redirección, biografía heredada); biografía por la temporada más cercana entre fuentes, nacimiento inmutable con `bio_conflict` y todas las nacionalidades.
- Pendiente: filas de FIBA en Talent (competiciones pausadas) y la cola de revisión de los `review` (#980, necesita cuentas).

### 7. Rework de UI (épica #187)
- **Rework de UI** (épica #187, **en curso**: primer tramo U0–U3 acordado el 27/10/2026, U4 fuera por ahora): sistema de diseño con tokens y tema claro/oscuro, marca nueva, componentes base, `TeamCell`/DataTable (#184), shell móvil y migración de todas las páginas.
- **U0 hecho** (#188): la web usa los tokens de `design/` con **tema claro por defecto**, oscuro o del sistema, acento naranja y todos sus colores en tokens (guarda `designTokens.test.ts`); al pasarlos aparecieron y se corrigieron clases de color que nunca existieron (`bg-surface-card`, `surface-muted`, `ink-disabled`: inputs y tooltips sin fondo) y títulos en blanco.
- **U4 hecho** (#191: navegación agrupada con menú modal en el móvil, selector de competición, resumen con una tarjeta por página y hero; Predictivo y Gráficos de tiro ya caben a 390 px).
- **U1 hecho** (#189, iterado en #613): marca de la web en `design/brand` (el balón de la suite con una tendencia ascendente, sin baldosa en la interfaz y el favicon; el pulso es de la app live), favicon SVG/ICO, iconos y manifest, imagen para los enlaces compartidos y metadatos.
- **U2 hecho** (#190): componentes base en `components/ui` y guía [UI.md](UI.md); ya los usan el selector de tema, las pestañas de Equipo y los selects de Combinaciones, Rotaciones y Predictivo; el resto de páginas se migra en U5 (el trinquete `rawControls.test.ts` impide sumar controles a mano).
- **U3 hecho** (#184): una sola columna de equipo (`teamColumn()`: logo, dos líneas, nombre entero en el tooltip) en Equipo, Comparativas, Multifase, Posesiones, Análisis pbp y, compacta, en Jugadores; `DataTable` con densidad, estados del sistema y tarjetas en el móvil (aprovecharán todo el ancho cuando U4 quite la barra lateral fija).
- **U7 hecho** (#197: auditoría axe de 197 violaciones a 0 —contraste del texto tenue y del naranja, 64 controles sin nombre, tablas sin acceso por teclado—, prueba axe permanente en el CI, enlace «Saltar al contenido», movimiento reducido y capturas como artefacto; la revisión de la app Android va aparte, #633).
- **#630 hecho** (el refresco local rellena `DERIVED`, un fallo al calcularlo deja aviso y «Análisis pbp» dice cuántos partidos faltan por procesar).
- **U6 hecho** (#196: la pista FIBA, sus zonas, el scatter y el mapa de calor se dibujan con los tokens del tema —suelo, líneas, aro y tonos de datos—, token `--on-data` para la tinta sobre las burbujas con contraste AA comprobado, y el guarda ya no tiene excepciones).
- **#627 paso 1**: «Informe de equipo» es solo el análisis propio y enlaza a «Scouting del rival» (en FEB; en FBCYL desde #635: el modo rival por reglas se retiró).

### 8. Comparativas en la web (#607, #608)
- **Comparativas en la web y diferencia real (27/10/2026, #607, #608)**: página «Comparativas» con los informes del informe semanal (local vs visitante, ganados vs perdidos, tramo vs resto por rango de fechas con atajos de 30 y 15 días) y la diferencia absoluta en vez de las flechas de tendencia (web, tarjetas y PNG del informe).
- Límites: el atajo «últimos N partidos» no existe (los filtros son por fecha) y el `$not` de fechas del resto está probado con mocks y el pipeline, no contra Mongo real: comprobarlo en la primera consulta de producción.

### 9. Épica #435: estudio de modelos (#567)
- Estudio de modelos de la probabilidad y las palancas (#567, 26/10/2026, [informe](evaluaciones/2026-10-26_modelos-de-probabilidad-y-palancas.md)): con 1.610 partidos, **ningún modelo con más estadística de equipo mejora al actual** y lo que se ve en el partido no predice los 5 minutos siguientes;
- **el jugador sí aporta** (calidad de los quintetos en pista: +0,52 puntos por desviación típica en los 5 min siguientes, IC 95 % +0,35 a +0,71; mejor con ratings de varias temporadas);
- propuestas pendientes de decisión (quitar las cifras causales «+N %» de los avisos, rating de jugador de varias temporadas en el paquete para palancas individuales de rotación, valor previo ajustado por rival, probar la calidad de tiro por zona).

### 9a. Predictivo (épica #841): pendiente
- **#454 (Google Play) en pausa** hasta cerrarla.

### 9c. Proyección «¿Y si…?» (épica #935): diferidos y límite
- **Diferidos**: #939 duración de las posesiones en las filas (es otra forma de medir el ritmo, sin respaldo; decisión del usuario) y #942 simulador causal del ritmo (base: las rápidas tras robo anotan más y las rápidas tras canasta, menos).
- **Límite conocido (#947, anotado por decisión del usuario)**: entre los partidos 15 y 24 de una competición, las cifras de los objetivos y de la tarjeta están calibradas pero no mejoran al pronóstico, y las condiciones sobre factores pasan más de lo que dice la página (el doble en las raras); desde el 25 todo cumple ([sección g](evaluaciones/2026-11-16_proyeccion-multifactorial.md)).

### 9c. Administración y escrituras del servidor (#724, #334): huecos
- **Casos que antes caían a la API y ahora son error** (huecos de capacidad del lado local, candidatos a cubrir al publicar): IN/OUT de FBCYL y de una jugadora que no está en la publicación, comparación por tramo sin fecha, ventana de evolución fuera de 2-15 partidos, multifase con alguna fase sin publicar, partido sin análisis publicado y competición exportada sin filas de jugadoras.
- **#447 queda sin objeto** (activar `ADMIN_API_KEY` para dar de alta colecciones desde la web) y #157–#159 siguen aparcadas.

### 9d. Retirar la API (épica #1199, decidido el 27/11/2026)
- **Se elimina `src/api`, `run_api.py` y el modo `?data=api`** en un PR de cinco commits (#1200 web, #1201 e2e y fixtures, #1202 borrar la API con auditoría de cobertura, #1203 servicios huérfanos, #1204 docs). Mediciones, riesgos y alcance en [la evaluación](evaluaciones/2026-11-27_eliminar-la-api.md): ≈ −25 % del tiempo de la suite, ≈ 3.300 líneas de producción y 7.700 de tests, `fastapi` y `uvicorn`.
- **Queda fuera**: el oráculo Python de los vectores (≈ 2.137 líneas) y que TS sea canónico con vectores congelados como golden files (#641).

### 10. Dependencias y seguridad (#525)
- **Dependencias y seguridad** (#525, 23/10/2026): vulnerabilidades npm del frontend web corregidas (de 10 a 0; `react-router-dom` 7 en #526), Dependabot semanal agrupado (npm web y app, GitHub Actions; pip solo avisos de seguridad) y `pip-audit` limpio; pendiente probar `action-gh-release` v3 con una publicación de prueba (#535, PR #532 retenido).

## Complejidad (#202, 10/11/2026)
- Con un contador propio de complejidad ciclomática hay **9 funciones de `src/` por encima de 25** (eran 14; 31 por encima de 20).
- Partidas en #202: `publish_web_data`/`_publish_sections`, `scout_team_scopes`, `get_rotation_analysis` y `group_page`.
- Quedan: las de la API de desarrollo (`_recompute_derived`, `calculate_stat_value`, `_extract_shots` del informe semanal, `court_zones.plot_zones`;
- no se tocan mientras la API se conserve, #334/#641), `fbcyl_adapter._lines` (motor live: tras la release del viernes) y dos funciones cortas y planas cuya complejidad la dan las comprensiones de lista (`team_points_by_origin`, 26 líneas; `recording_report.summarize`, 27), que no se trocean para bajar un número.

## Deuda técnica (>500 líneas; dividir al tocarlos)
- La lista al día la da el informe del CI (`scripts/duplicate_code.py`, sección «Tamaño», #452/#112): el 10/11/2026 son 13 ficheros —Python: `database/aggregation/fbcyl_pipeline.py` 1252 (#203, datos declarativos) `scraper/feb_scraper.py` 856 `services/rotation_service.py` 730 `shotcharts/court_zones.py` 663 `_weekly_report_helpers.py` 651 `shotcharts/detailed_zones.py` 630
- `shot_visualizer.py` 596 `weekly_report_service.py` 579 `fiba_court.py` 579 `fbcyl_scraper.py` 542; web: `PlayerStatsPage.tsx` 623 `LineupsPage.tsx` 607 `RotacionesPage.tsx` 586—, de 21 el 27/10 (salieron `inout_calculator`, `lineup_stats_calculator`, `repository_inout`, `pipeline_player_stats`, `client.ts`, `PredictivePage.tsx`, `AdminPage.tsx`, `MultiPhaseStatsPage.tsx`…).
- Frontend: `api/client.ts` se partió por dominio (#201: ahora es un barrel de reexportaciones sobre `api/{http,collections,teams,players,lineups,rotations,shots,possessions,matches,multiPhase}.ts`, ninguno de más de 500 líneas, vigilado por `api/moduleSize.test.ts`) · `PlayerStatsPage.tsx` 625 · `LineupsPage.tsx` 635 · `RotacionesPage.tsx` 616 (`PredictivePage` y `AdminPage` se partieron en U5b/U5d, #193/#195, y luego se retiraron).
- App live: `ui/App.tsx` 484 tras extraer `useStoredMatches`, `useMatchReports` y `useEntryPoints` (#590). (Cifras del 23/10/2026.)
- Código duplicado: medición repetible en el CI (`scripts/duplicate_code.py`, #452; línea base 65 + 22 bloques); gemelos de los normalizadores FEB/FBCYL resueltos (`build_team_docs`, bloque 3); pipelines de FEB con la fecha (`feb_date_expr`) y el `$group` de equipo/rival compartidos (bloque 4;
- los literales de `fbcyl_pipeline` ↔ `pipeline_player_stats` quedan como datos declarativos, #203); TypeScript (bloque 5: columnas y cuartiles de `MultiPhaseStatsPage` de `lib/teamColumns` y `lib/quartiles`, `useTeamOptions`, `AnalysisProgress`, `streamResult` de `api/sseStream`, `NoCollection`, `useHistoricalPicker`; quedan solo bloques de ≤ 10 líneas);
- IN/OUT y quintetos (bloque 6, #200: `pbp_stat_counters`; `inout_calculator` 259 líneas y `lineup_stats_calculator` 451, cobertura 95 % y 87 %; `repository_inout` 595 → 384 líneas con `get_player_in_out_stats` partido en `_inout_game_lookup`, cobertura 9 → 49 %;
- el análisis «dos jugadoras juntas» y el de una jugadora con una compañera, sin ningún consumidor, se borraron con el endpoint `/together`, el mixin de ayudas y el ayudante del repositorio que solo ellos usaban (≈ 1.160 líneas con sus tests), y `repository_inout` quedó en 148;
- #818 arregló el IN/OUT de FBCYL, que dejaba a cero el lado «con la jugadora en pista») y `GAME_SECONDS` escrito una sola vez fuera de `live_core`, vigilado por `test_game_seconds_single_source.py`; los literales de `live_core/boxscore.py` y `lineups.py` esperan a la release del viernes y la lista del test solo puede encogerse). #452 se cierra con el informe de tamaño en el CI.
- Otros: la API solo tiene una clave de administración (sin usuarios/roles ni protección de lecturas; #115)

## Límites conocidos
- Esquinas casi vacías en el sistema de 10 zonas (dato de origen) FBCYL en directo hecho (#446, 9/11/2026: motor, paquetes y app; cerrado el 26/11/2026 por decisión del usuario, que seguirá partidos reales y dará feedback en issues nuevos;
- el grabador cogió entero el partido del 25/11/2026, grupo A-1, 531 consultas y 0 errores) y un equipo que descansa la jornada se puede elegir y marcar de interés porque el índice trae todos los equipos de cada competición (#1105); minutos con precisión de 1 min colecciones pequeñas dan líneas base ruidosas (todo se encoge hacia la media de liga)
- sin emparejamientos jugador-vs-jugador.
- **Rating de jugadora y palanca de rotación descartados (#587, 26/10/2026)**: la señal de los quintetos en pista es real agregada pero solo el 11 % del hueco «quinteto actual vs. mejor disponible» lo es en un momento concreto, daría 2,5-6 alertas por partido y su valor no se puede medir con datos observacionales;
- el coste (publicador en local, esquema, motor, app) no lo justifica ([experimento 5](evaluaciones/2026-10-26_modelos-de-probabilidad-y-palancas.md)).
- Se reabre si hay ratings más fiables (varias temporadas de jugada a jugada).
- El scouting individual (DOCX) sigue sin perfil de tiro en FBCYL (solo FEB).
- **Baja y racha sin jugar (#1082, #1083)**: solo FEB (la «Trayectoria» no existe en FBCYL ni en las fuentes externas, y sin alta no se cuenta la racha); valorado en #1085 (25/11/2026): la nota de racha **no** se hace en FBCYL (sin fecha de alta no se puede excluir lo anterior a un fichaje y la cifra engañaría);
- la ficha se lee la primera vez y luego una vez por semana por equipo (≈ −5 a −9 min por publicación frente a leerla siempre); el DOCX del servidor filtra la baja pero no escribe la nota; **Rotaciones, Conexiones y Combinaciones no se filtran** (analizan partidos, no eligen jugadores);
- falta medir el coste de leer la ficha en cada publicación y comprobar la lista de **Tiros** con un test propio. **Talent (#872)**: los enlaces FBCYL↔FEB dependen de la cobertura del archivo (LF2 2026-27 aún no está); el formato Next.js de ACB y FIBA y los *hashes* de NCAA.com son frágiles; D2 masculino no tiene ids ni biografía;
- quien sale de FEB (ACB, NCAA, extranjero) cuenta como censurado, no como «no llegó».

## Backlog
Fuente única: **GitHub Issues** (`gh issue list`). Aquí no se duplica; solo contexto estratégico. Etiquetas: `bug`, `enhancement`, `tech-debt`, `testing`, `live`.

## Hecho (resumen)
Detalle completo (tabla original e ítems pasados a hecho): [historia-roadmap](evaluaciones/2026-11-27_historia-roadmap.md).
- Limpieza: capa PyQt (FASE 0) y LLMs externos eliminados.
- Predictivo rehecho en el navegador (épica #841, #852/#853; previa, simulación, walk-forward, ajuste por rival; `frontend/src/forecast/`) y proyección «¿Y si…?» (épica #935, #936-#948): [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
- Informes: semanal, scouting DOCX, PDF, informe de equipo por reglas, scouting del rival en PDF (#299): [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
- Live app: cooldown de 3 s entre alertas (#375); live motor: estado incremental, alertas, Four Factors, recomendador, paquete cifrado, vectores Python↔Pyodide.
- Calidad: guarda de ingesta en curso, `src/pbp`, tests de docs; smoke e2e Playwright (#111).
- Datos y operaciones: refresco del archivo (#177, #724), `/health/db`, grabador (#171), `live-packages` (#175).
- Estadísticas desde el pbp (épica #347, #348-#393): posesiones únicas, `DERIVED`, puntos por origen, cuartos, ATO, tiempo muerto; completada salvo lo aplazado: [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
- UI: tabla de posesiones (#183, #181).
- Épica #435 (más competiciones en la app live, #442-#503), selectores vacíos (#605) y Análisis pbp por origen (#601-#603): [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
- Visión de producto y local-first (#591, #327 GO, #326, #329, #331, #638-#646); pendiente de ahí: comparativa del scouting en el navegador y PDF (#638): [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
- Predictivo antiguo retirado (#852, #853); Administración y escrituras retiradas (#724, #334, #635, #751); sin Render: [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
- Dependencia de Atlas retirada (pasos 1-6, 05/11/2026); estrategia de testing (épica #540 cerrada el 10/11/2026); calidad de datos (#539, #502, #503); rotaciones deterministas (#828); lista de partidos por equipo (#119, #449, #456): [detalle](evaluaciones/2026-11-27_historia-roadmap.md).
