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
| ORB/DRB **de equipo** del motor live = PDF | 10 de 32 equipos-partido fallan por ±1–2 |
| `detect_offensive_rebounds` (`possession_core`) = ORB total del PDF | 22/32 |

**Conclusión sobre rebotes**: el pbp contiene todos los rebotes (jugador y equipo) y su **total es exacto**. Lo que no se puede inferir con fiabilidad es el **reparto ofensivo/defensivo de los rebotes de equipo** (la inferencia «mismo equipo que el último fallo» falla en ~31 % de los equipos-partido, siempre por 1–2 rebotes). El PDF da el reparto oficial. La regla acordada (pbp ≥ boxscore, si no fallback) es coherente en FEB (por construcción el pbp con equipo ≥ boxscore; solo saltó en 1/32 para el ORB, por un rebote de jugador mal clasificado), pero **no detecta** los errores de reparto de los rebotes de equipo.

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
