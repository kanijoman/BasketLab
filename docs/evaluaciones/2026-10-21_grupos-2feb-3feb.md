# 2ª FEB A/B y 3ª FEB A-B para la app live: verificación con partidos terminados (21/10/2026)

Parte de #436 (épica #435) que se puede comprobar **sin partido en directo**. Todo es de solo lectura (web de FEB y API pública con el token de la página); no se ha escrito nada en Atlas. Lo que sigue pendiente del spike necesita un partido en vivo (ver el final).

## Resumen
| Comprobación | Resultado |
|---|---|
| Alta de los grupos (#437) | `get_feb_competitions` / `get_seasons` / `get_groups_for_season` dan los valores; 21, 20 y 21 partidos jugados (≈ 0,5 s cada uno) |
| Ids de los equipos de interés | Cultural y Deportiva Leonesa **1008857** (2ª A) · Club Esportiu Bàsquet Llíria **1008978** (2ª B) · **CAJA RURAL RDL** **1010490** (3ª A-B) |
| Formato de los datos (`canary`) | **OK** en un partido terminado de cada grupo (2536115, 2536298, 2536843): esquema e invariantes (el motor reproduce marcador, faltas y tiros); solo campos nuevos `slug`/`LogTime`/`LogTimeUtc`, los mismos de LF Challenge |
| `LogTimeUtc` en el pbp | Presente → se puede medir el retraso del feed como en LF Challenge (#411) |
| Plantilla / «Formación» | La columna existe y se lee en los tres equipos (Cultural: 8 sí / 4 no; Llíria: 11 / 1; RDL: 11 / 0) |
| Reglas FIBA que asume el motor | 4×10 min y prórroga de 5; máx. 2 tiempos muertos por equipo en la 1.ª parte, 3 en la 2.ª y 1 por prórroga en los 62 partidos (el único «4» es una línea duplicada del feed: 2536129, mismo segundo) → **sin cambios en `clock.py` ni `timeouts.py`** |
| **Calendario por grupo** | ❌ **No funciona hoy**: ver abajo |

## Calendario por grupo (hallazgo)
`MatchScheduleService.calendar_url` devuelve la `competition_url` guardada, que es la **de la competición** (`calendario.aspx?g=2&t=2026&nm=segundafeb`, la misma para el grupo A y el B), y `_fetch` la descarga con un GET. Esa página enseña **un solo grupo** y no el que se quiere:
- la URL de 2ª FEB trae el grupo A (14 de 14 equipos del A, ninguno del B): `upcoming` de Llíria diría «El equipo no aparece en el calendario» y `next_round` de la colección del grupo B publicaría la jornada del grupo A;
- la URL de 3ª FEB trae otro grupo (0 de 14 equipos son del A-B): RDL tampoco aparecería.

Sí funciona seleccionar el grupo con el *postback* de ASP.NET que ya usa el scraper (`FEBWebScraper.select_group(session, url, season_value, group_value, hidden_fields)`): devuelve 182 partidos y 14 equipos, **14 de 14 del grupo pedido** en 2ª B y en 3ª A-B. Arreglo: guardar `group_value`/`season_value` en `COLLECTION_META` (ya los recibe `save_feb_meta`) y que `http_calendar` haga el postback cuando la colección tenga grupo (la caché de 60 s pasa a clave `url + grupo`). Issue propio en la épica.

## Pendiente (necesita un partido en directo, fin de semana)
- Valores de `HEADER.status` durante el partido y 404 antes de empezar en estas competiciones.
- Vigencia del token, caché y retraso real del feed (`LogTimeUtc` frente a la hora de llegada).
- Grabar un partido de Cultural, Llíria o RDL con `recorder.py` y revisar las alertas con el replay.
