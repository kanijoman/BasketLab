# La regla de la jugadora rival caliente desde una zona, ahora activa en 2ª y 3ª FEB (27/10/2026, #599)

Contexto: el boxscore del directo de 2ª y 3ª FEB no trae el dorsal, así que el motor no podía atribuir ningún tiro del shot chart a una jugadora y `rival_player_zone` (Z4: «Rival K. JOHNSON: 3/4 desde el aro») no actuaba. Con el dorsal leído del shot chart (`jerseys.py`, #599) sí. Esta medición dice qué hace la regla y si aporta.

## Método
`python -m src.live_prep.rule_evaluation --games-dir <235 partidos de 2026/27 sin el `no` del boxscore> --min-prior-games 3` (152 equipos-partido evaluados, como los ve el directo de 2ª/3ª FEB), y para cada aviso, los tiros de esa jugadora en esa familia de zonas **después** del aviso, comparados con el rendimiento medio de esa familia en los 235 partidos (tiros de campo del shot chart con el dorsal del boxscore oficial).

## Resultados
- **Volumen**: 246 avisos en 152 equipos-partido (**1,6 por equipo-partido**, el 2,0 % de los 12.189 avisos); 129 equipos-partido reciben alguno; máximo 5 en un partido; mediana en el minuto 27,7. Siempre `warning`. 207 de los 246 saltan justo en el mínimo (4 intentos; 3 aciertos).
- **¿Siguen calientes?** Después del aviso tiran **1,09 puntos por tiro** (324 tiros, 47,8 % de acierto) frente a **1,00** que harían jugadoras medias en esas mismas familias: +0,09, con un error típico de ≈ 0,06 (≈ 1,5 σ): **no se distingue del ruido**.

| Familia | Acierto de la liga | Pts/tiro de la liga | Tiros tras el aviso | Acierto | Pts/tiro |
|---|---|---|---|---|---|
| ala (triples a 45°) | 31,3 % | 0,94 | 132 | 32,6 % | 0,98 |
| aro | 64,9 % | 1,30 | 52 | 69,2 % | 1,38 |
| zona | 47,0 % | 0,94 | 138 | 55,1 % | 1,10 |

- Coincide con el estudio de los modelos ([2026-10-26](2026-10-26_modelos-de-probabilidad-y-palancas.md)): lo que se ve en el partido de un equipo o de una jugadora **casi no predice lo que viene**. El aviso es, sobre todo, un **diagnóstico** de lo que ha pasado («lleva 3/4 desde el aro»), no una previsión de que va a seguir.
- «3/4 desde el aro» (75 %) es poco raro para una jugadora de aro (65 % de media): el umbral de 1,5 puntos por tiro es exigente para un triple y flojo para una zona de aro.

## Decisión
**Se deja como está**: el volumen es bajo (1,6 por equipo-partido), la redacción ya es de diagnóstico y no promete un efecto, y no hay un umbral que mejore la predicción de forma clara. Se revisa con el feedback del staff (#235): si molesta o no se sigue, bajar a `info` o exigir más muestra por familia (`zone_player_min_attempts`, `zone_player_min_makes`, `zone_player_pps`).
