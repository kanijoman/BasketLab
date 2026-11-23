# Euroliga femenina como fuente externa: spike del feed de partidos (#1039, D6b de la épica #872)

Medido el 23/11/2026 con el cliente de FIBA que ya existe (`src/external/fiba_client`, pausa de 1,5 s en las mediciones), el conversor de FIBA y la reconciliación compartida. Solo lectura: no se cargó nada.

## Veredicto

**GO, y sin fuente nueva**: la Euroliga femenina (y la EuroCup femenina) están en `fiba.basketball` y se leen con la fuente de FIBA que ya hay (#887). Lo que faltaba en el issue era el **nombre del evento**: usa el formato corto `YY-YY` (`euroleague-women-25-26`), no `YYYY-YY`, y por eso los eventos que se probaron el 20/11 devolvían la página genérica. Lo que hay que hacer es **añadir estos eventos al catálogo de FIBA** (`candidate_events`), no escribir un cliente, un lector ni un conversor.

**Alcance real: solo 3 temporadas**: 2024/25, 2025/26 y la actual 2026/27. Antes de 2024/25 no hay evento bajo ningún nombre que haya funcionado.

## Dónde está

* El dominio oficial `euroleaguewomen.basketball` redirige a `https://www.fiba.basketball/en/events/euroleague-women-26-27`. La organiza FIBA Europe y publica en el mismo sitio y con el mismo formato (páginas con los datos en trozos de Next) que los eventos de selecciones que ya leemos.
* La página de cada edición enlaza solo con la anterior y la siguiente, y con la **EuroCup femenina** (`eurocup-women-26-27`), que está en el mismo sitio.
* No está en la API de la Euroliga masculina (`api-live.euroleague.net/v2/competitions`): sus 43 competiciones son la masculina, la EuroCup masculina y ligas nacionales, ninguna femenina.

## Volumen (con `FibaClient.event_games`)

| Evento | Partidos listados | Jugados |
|---|---|---|
| `euroleague-women-26-27` (en curso) | 110 | 40 |
| `euroleague-women-25-26` | 110 | 110 |
| `euroleague-women-24-25` | 92 | 89 |
| `eurocup-women-26-27` (en curso) | 216 (154 con partido ya definido) | 105 |
| `eurocup-women-25-26` | 216 | 215 |
| `eurocup-women-24-25` | 216 | 216 |
| `euroleague-women-23-24` y anteriores, y `euroleague-women-2025-26` | 5 «partidos» sin enlace ni equipos | 0 |

**Una petición por partido** (la página de un partido trae caja, jugada a jugada y la biografía) y una por evento para el listado: la Euroliga femenina de una temporada son ≈ 110 peticiones, unos 4 minutos con la pausa de 2 s de la fuente; la EuroCup, ≈ 216.

## Calidad, con los partidos reales por el conversor de FIBA y la reconciliación compartida

Muestras al azar de partidos jugados:

| Evento | Muestra | Válidos | **Fiables** | Con jugada a jugada |
|---|---|---|---|---|
| `euroleague-women-25-26` | 14 | 14 | **14** | 14 |
| `euroleague-women-24-25` | 14 | 14 | **14** | 14 |
| `euroleague-women-26-27` | 10 | 10 | **10** | 10 |
| `eurocup-women-25-26` | 10 | 10 | **10** | 10 |

Las 48 páginas dicen «Women» (el sexo de la entrada se comprueba contra la página, como en FIBA). Las estadísticas informativas discrepan solo en las **faltas** (10 de 76 equipos-partido de la Euroliga, 2 de 20 de la EuroCup), que no descartan el partido.

## Biografía

Del jugador viene en la propia página del partido: nacimiento, altura, nacionalidad y club.

| Evento | Jugadoras | Nacimiento | Altura | Nacionalidad |
|---|---|---|---|---|
| `euroleague-women-25-26` | 307 | 298 (97 %) | 291 (95 %) | 298 |
| `euroleague-women-24-25` | 305 | 287 (94 %) | 277 (91 %) | 287 |
| `euroleague-women-26-27` | 229 | 227 (99 %) | 223 (97 %) | 227 |
| `eurocup-women-25-26` | 219 | 214 (98 %) | 200 (91 %) | 214 |

## Lo que hay que hacer (por orden)

1. **Catálogo**: añadir a `candidate_events` los eventos de clubes con su nombre `YY-YY` (`euroleague-women-25-26`, `eurocup-women-25-26`, …), femeninos, con la etiqueta de temporada de dos años (`2025/2026`, valor `2025`). Pausados, como los demás.
2. **Activarlos** por el mismo camino (`run_catalogue_activate.py --league fiba`, que hoy no lo admite) y mirar la primera carga.
3. **Enlace con FEB y biografía prestada**: ya funciona para FIBA (#885, #979); las jugadoras de clubes españoles en la Euroliga femenina son las que más se enlazarán.

## Hallazgos de paso

* **Un evento que no existe devuelve una página genérica**, no un 404: 5 «partidos» sin enlace, sin equipos y sin fecha, siempre los mismos ids. Hoy no hace daño (`new_entries` exige equipos y `FibaSource` solo pide partidos terminados), pero cualquier lector nuevo que cuente los partidos listados se lo creería. Queda anotado.
* **Qué más hay en la API de la Euroliga masculina** (`api-live.euroleague.net/v2`): se midió el 23/11/2026, ver el apartado «Otras competiciones del mismo endpoint» del [informe de la masculina](2026-11-23_euroliga-spike-1038.md). Corrige una frase de la primera versión de este informe: las ligas nacionales de la lista **no tienen datos**.
* **Mapa de tiros**: FIBA da las coordenadas de cada tiro; la fuente de FIBA todavía no las convierte a las zonas del motor (`SHOTCHART` vacío). Aplica a esta competición como a las demás de FIBA.
* Con la regla del histórico de 10 temporadas (OPERATIONS, 23/11/2026) el tope **no limita** aquí: las tres temporadas que existen entran todas.
