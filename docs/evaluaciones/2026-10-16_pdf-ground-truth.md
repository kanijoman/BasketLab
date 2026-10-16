# Auditoría de datos: ¿podemos usar el PDF oficial de FEB como ground truth? (16/10/2026)

Épica #347 (estadísticas extendidas desde el pbp); sub-issues #348 (auditoría de rebotes) y #349 (spike del PDF).

## Método
- **Muestra**: los 16 partidos FEB de la LF Challenge 2026-27 de la BD local (`2524455`–`2524470`; 32 equipos-partido; 3 con prórroga) y los 6 partidos FBCYL (12 equipos-partido).
- **PDF**: `https://baloncestoenvivo.feb.es/BoxScore.aspx?p=<partido>&c=4&qd=4&t=FINAL`. Extracción con `pdftotext -raw` (poppler); no hace falta OCR (las fuentes Type3 no impiden la capa de texto; una lectura con un modelo de resumen daba un falso negativo).
- **Contraste** (script exploratorio, no entra en el producto): PDF ↔ `BOXSCORE` de Mongo ↔ pbp (`PLAYBYPLAY.LINES`) ↔ motor live (`LiveEngine`) ↔ `possession_core.extract_possession_rows`.
- Fixture resultante: `tests/fixtures/feb_pdf_ground_truth.json` (valores del PDF por equipo y partido).

## El PDF
- **Siempre es el partido completo**: `c` y `qd` no cambian el contenido (mismo tamaño y mismos totales con `c=1..4`). **No sirve para validar por cuarto**, salvo la línea de parciales `(16-13,14-6,…)`.
- Contenido: boxscore por jugador (con `*` en titulares), fila **Equipo/Entrenador** (rebotes de equipo), fila **Totales** (incluye los de equipo), parciales y un bloque de extras: puntos de **2ª oportunidad, contraataque, en la pintura, tras pérdida y de banquillo** por equipo, más máxima ventaja, mejor racha, cambios de ventaja y veces empatado.
- **Trampa del bloque de extras**: con `-layout` los valores no quedan alineados con sus etiquetas; el orden correcto (comprobado con el banquillo) es 2ª oportunidad, contraataque, pintura, tras pérdida, banquillo, primero los cinco del local y luego los del visitante.
- Particularidades de parseo: codificación cp1252 (los acentos salen rotos con otra), filas de jugador partidas en dos líneas, la fila de equipo pega las cifras en `-layout` (usar `-raw`) y los minutos de la fila Totales son `225:00` con una prórroga (no suponer `200:00`).
- El feed de Mongo ya trae los campos `fastb`, `ptsto`, `secpts`, `bench` y `paint` en `BOXSCORE.TEAM.TOTAL`, pero **siempre a `None`**: el PDF es hoy la única fuente de esos extras.

## Resultados FEB (32 equipos-partido)
| Comprobación | Resultado |
|---|---|
| Puntos del PDF = puntos de Mongo | 32/32 |
| `ro/rd` de Mongo + rebotes de equipo del PDF = REB del PDF | 32/32 (**el boxscore de Mongo excluye los rebotes de equipo**) |
| Rebotes sin `idPlayer` del pbp = rebotes de equipo del PDF | 32/32 |
| Rebotes con `idPlayer` del pbp = `ro+rd` de Mongo | 32/32 |
| Total de rebotes del pbp (jugador + equipo) = REB del PDF | 32/32 |
| PER del PDF − `to` de Mongo = `tov_team` del motor live | 32/32 |
| Puntos de banquillo del PDF = suma de jugadores con `inn != 1` de Mongo | 32/32 (derivable del boxscore, sin PDF) |
| ORB de **jugador** del motor live = `ro` de Mongo | 31/32 (1 rebote de diferencia en un partido) |
| ORB/DRB **de equipo** del motor live = PDF | 10 de 32 equipos-partido fallan por ±1–2 (ver el spike y la validación con el histórico más abajo) |
| `detect_offensive_rebounds` (`possession_core`) = ORB total del PDF | 22/32 |

**Conclusión sobre rebotes** (corregida dos veces: spike de #350 y validación con el histórico): el pbp contiene todos los rebotes (jugador y equipo) y su **total es exacto**. El reparto ofensivo/defensivo de los **de jugador** se infiere bien con «mismo equipo que el último fallo» (32/32 contra `ro/rd` de Mongo, tras #365; 346/350 en el histórico). Para los **de equipo** en los partidos de **2026-27** esa regla falla en 10/32 equipos-partido y el spike encontró que **un rebote de equipo tras un tiro libre fallado se clasifica al revés**: con esa inversión coincide con el PDF en 32/32 (solo 13 rebotes de equipo siguen a un tiro libre fallado). **Pero la validación con 350 equipos-partido de 6 competiciones-temporadas de 2024-25 y 2025-26 da lo contrario: la regla normal acierta 349/350 y la invertida solo 282/350.** La inversión es, pues, propia de la temporada 2026-27 (¿cambio del motor estadístico de FEB?), sin explicación conocida, y se apoya en 16 partidos de una semana. Ni el orden de los eventos (`num`, reloj, `LogTime`), ni los tiros libres no finales, ni las pérdidas, ni el tapón, el triple o el hueco de reloj la explican; el feed no trae el tipo de rebote (`logParam1` solo codifica local/visitante) y `LogTime` no distingue las temporadas (LF Endesa 2025 lo trae y cumple la regla normal). **Decisión (16/10/2026): se asume que el error está en el PDF de 2026-27.** El reparto ofensivo/defensivo de los rebotes de equipo sigue siempre la regla normal (mismo equipo que el último fallo = ofensivo), que es el sentido real del juego y la que necesitan las posesiones y los puntos de segunda oportunidad. No se replica la etiqueta del PDF de 2026-27: el ORB% y el DRB% mostrados pueden diferir ±1–2 rebotes por equipo-partido (≈ 31 % de los equipos-partido) del PDF oficial de esa temporada. Se sigue comparando con los PDFs de los partidos nuevos (#361) para detectar si FEB corrige su software; si lo hiciera, no habría nada que cambiar. La regla acordada (pbp ≥ boxscore, si no fallback) sigue siendo válida.

## Validación con el histórico (1.960 partidos FEB, 6 competiciones-temporadas)
Datos: `data/historical_games` (LF2 2024 y 2025, LF Challenge 2023, 2024 y 2025, LF Endesa 2024 y 2025). Parte A: todos los partidos contra el boxscore oficial; parte B: muestra estratificada de 210 partidos (30 por grupo) contra el PDF oficial.

**A. Coherencia del motor y del pbp (1.709 partidos con `action`, 3.418 equipos-partido)**
- Marcador del motor live = oficial en todos salvo 1 equipo-partido (el único `MATE DE 3 ANOTADO`).
- Rebotes de jugador del pbp = `ro+rd` del boxscore en el **100 %** de los equipos-partido. Hay rebotes de equipo en el 94 % (≈ 4 por equipo-partido, ~10 % de todos los rebotes).
- Reparto ORB de jugador del motor = boxscore salvo 31 equipos-partido (≈ 1 %), por textos de tiro anómalos.
- **LF Challenge 2023 (251 partidos)**: las líneas no traen `action`; el motor no extrae nada. Habría que derivar el tipo de evento del texto.
- Asistencias: en la temporada 2024 difieren pbp y boxscore ±1–2 con signo opuesto entre los dos equipos (suma igual) en ~45 % de los equipos-partido; en 2025, no. Atribución de equipo del feed, no del parser.
- Otros: 19 líneas de tiro sin resultado en el texto (`TIRO DE 2`, `TIRO DE 3`, `TIRO DE 1`) y un `MATE DE 3 ANOTADO`.

**B. Reparto ORB/DRB de equipo contra el PDF (350 equipos-partido = 175 partidos de LF2, LF Challenge y LF Endesa 2024 y 2025; de los 210 muestreados se descartan 30 de LF Challenge 2023, sin `action`, y 5 sin PDF)**
| Regla | Aciertos |
|---|---|
| Normal (mismo equipo que el último fallo) | **349/350** |
| Invertida tras tiro libre (hallada en 2026-27) | 282/350 |
| Total de rebotes pbp = PDF | 349/350 |
El único fallo de la regla normal es un partido con boxscore y PDF inconsistentes entre sí (LF Endesa 2024, 2412593). Los PDFs antiguos tienen la misma estructura que los actuales.

**Prueba de consistencia: ¿y si el error está en el PDF de 2026-27?** Con la regla normal (mismo equipo que el último fallo), todas las demás columnas del PDF de 2026-27 coinciden con el pbp en 32/32 equipos-partido: puntos, T2 y T3 (anotados e intentados), TL (anotados e intentados), rebotes totales, asistencias, robos y pérdidas totales (con las de equipo). La única columna que no cuadra es el reparto ORB/DRB de los 13 rebotes de equipo que siguen a un tiro libre fallado (en los ejemplos del partido 2524455 Q4 09:05 y 2524460 Q4 07:59 el equipo que tira se queda el rebote y anota o lanza a continuación, y el PDF lo cuenta como defensivo). Además, el PDF de 2026-27 incumple una identidad contable que cualquier convención razonable cumple: «ORB del que tira + DRB del rival = rebotes que siguen a los fallos del que tira». Se cumple en 345/350 equipos-partido históricos (98,6 %; los 5 restantes son los textos anómalos) y falla en 18/32 de 2026-27. Es coherente con un error de clasificación del PDF y no con otra convención, aunque no se puede probar sin conocer el software de FEB. Pendiente: los puntos de 2ª oportunidad del PDF podrían heredar el mismo error en esos 13 casos; no se puede comprobar todavía porque las posesiones actuales no reproducen esa columna con precisión (F2).

## Resultados FBCYL (6 partidos, 12 equipos-partido)
- El pbp real **sí trae «Rebote ofensivo» y «Rebote defensivo» explícitos**, siempre con jugador (la muestra del repo no los tenía). No hay rebotes de equipo en el pbp.
- Rebotes del pbp = suma de los de los jugadores del boxscore (`players[].data`): **12/12**.
- Los totales **de equipo** `stats.teams[].data.offensiveRebound/defensiveRebound` son **mayores** que la suma de jugadores (0–3 ORB y 0–6 DRB de diferencia): incluyen los rebotes de equipo, que **no** están en el pbp.
- Es lo contrario que en FEB. Hoy los pipelines FBCYL usan el total de equipo (con rebotes de equipo) y los FEB el de jugadores: **criterio inconsistente entre formatos** que F1b debe unificar. En FBCYL el fallback natural es el total de equipo (con reparto ofensivo/defensivo oficial). No existe un PDF equivalente.

## Extras del PDF frente al pbp (2ª oportunidad, tras pérdida)
Aproximación con las posesiones actuales (`extract_possession_rows`), puntos propios:
| Definición probada | Aciertos exactos / 32 | Error medio abs. |
|---|---|---|
| Tras pérdida: origen recuperación o violación, todos los puntos | 4 | 3,3 |
| Tras pérdida: igual, **sin posesiones que acaban en tiros libres** | 9 | 2,1 |
| 2ª oportunidad: posesión con RebO, todos los puntos | 2 | 3,3 |
| 2ª oportunidad: igual, **sin posesiones que acaban en tiros libres** | 12 | 1,7 |
Limitaciones: la lectura con las posesiones actuales sobrestima y no iguala exactamente al PDF; no se ha probado aún descontar solo los tiros libres de cada posesión (hace falta desglosar puntos por evento) ni cómo cuenta la FEB las pérdidas de equipo. **Contraataque y puntos en la pintura no se pueden derivar del pbp** (sin marca de contraataque; los tiros FEB no se asignan a la pintura con certeza). Para esos dos el PDF es la única fuente.

## Decisiones y siguientes pasos
1. **Go** para usar el PDF como **ground truth en tests** (fixture ya incluido) y como **fuente de contraataque, pintura y reparto oficial de rebotes de equipo** en FEB. Aún no automatizado en producción.
2. **Pendiente antes de automatizar**: aclarar con la FEB los términos de uso del acceso automatizado a `baloncestoenvivo.feb.es`; el PDF se generó con Chromium desde la página (¿tiene variantes/cambios de maquetación?). Un parser de producción necesita tests propios (TDD) y vigilancia de formato (como el canario existente).
3. F1b: rebotes = pbp (jugador + equipo) con el reparto de equipo **del PDF cuando exista**; si no, el inferido y marcado como estimado; FBCYL = total de equipo del boxscore. Unificar el criterio entre formatos.
4. F2: usar el PDF para calibrar las definiciones de 2ª oportunidad y tras pérdida (probablemente sin tiros libres) y para contraataque y pintura.
5. F3: el PDF **no** valida por cuarto; hará falta otra referencia (parciales y boxscore).
6. Ampliar la muestra: solo 16 partidos de una competición y una semana; repetir con otra categoría FEB antes de dar por buenas las conclusiones sobre el reparto de rebotes y el formato del PDF.
