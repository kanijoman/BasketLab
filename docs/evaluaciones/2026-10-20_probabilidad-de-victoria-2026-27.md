# Probabilidad de victoria: reevaluación con 2026/27 (20/10/2026)

Continuación de [2026-10-14_probabilidad-de-victoria.md](2026-10-14_probabilidad-de-victoria.md) (#261, #255): lo pendiente era repetir la medición con los partidos de 2026/27 como validación.

## Resumen
- **Muestra**: 24 partidos de LF Challenge 2026/27 (334 cortes de 5 min, ambos puntos de vista). **Poca**: 20-37 cortes por decil y los intervalos de confianza (remuestreo por partido) son anchos.
- **Sin valor previo útil**: los ids de equipo cambian cada temporada y los equipos llevan 2-3 jornadas, así que `--min-prior-games 3` no deja ningún partido y se usó `--min-prior-games 0`. «Solo valor previo» y «completo» no son comparables todavía; sí lo es «completo» frente a «solo marcador y tiempo».
- **Criterio de la app: no cumplido** (el modelo completo no mejora a «solo marcador y tiempo»: log loss 0,417 frente a 0,407). En octubre el valor previo no aporta; el criterio se evaluó antes con temporadas completas.
- **Mismo patrón que el 14/10**: el decil 30-40 % se desvía +13,7 pp y el 60-70 % −13,7 pp (antes, en LF Challenge, +7,4 y −7,5): el modelo da demasiada ventaja al favorito en la zona media. Ningún intervalo excluye el 0 con esta muestra; los extremos (0-10 % y 90-100 %) están bien calibrados (±1,3 pp).
- **Decisión**: sin cambios en el motor ni en los parámetros; la tarjeta sigue **experimental**. Reevaluar con ≥ 8 jornadas de 2026/27 y equipos con ≥ 3 partidos previos (entonces ya con valor previo real).

Reproducir: `PYTHONPATH=".;src" python -m src.live_prep.wp_cli --games-dir <carpeta con los partidos de 2026/27> --no-grid --bootstrap 300 --min-prior-games 0 --out informe.md` (los partidos se bajan con `python -m src.live_prep.download_games --season 2026 --out <carpeta>`, #301).

## Informe del evaluador
334 cortes de 24 partidos (ambos puntos de vista, cortes cada 5 min). Parámetros actuales: `wp_sigma=12.0`, `wp_n0=120.0`, `wp_home_adv=4.0`, `ff_beta=9.0`.

### Variantes

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Modelo completo | 0.142 | 0.417 | 8.63 | 13.7 |
| Solo valor previo | 0.143 | 0.418 | 8.59 | 12.3 |
| Solo marcador y tiempo | 0.137 | 0.407 | 8.56 | 4.4 |

**Criterio para mostrarla en la app**: mejor que «solo marcador y tiempo» (no), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: -). **NO cumplido.**

### Fiabilidad del modelo completo

| Decil | n | P media | Frecuencia |
|---|---|---|---|
| 0-10 % | 65 | 0.028 | 0.015 |
| 10-20 % | 22 | 0.150 | 0.182 |
| 20-30 % | 21 | 0.246 | 0.238 |
| 30-40 % | 37 | 0.349 | 0.486 |
| 40-50 % | 22 | 0.452 | 0.545 |
| 50-60 % | 22 | 0.548 | 0.455 |
| 60-70 % | 37 | 0.651 | 0.514 |
| 70-80 % | 21 | 0.754 | 0.762 |
| 80-90 % | 22 | 0.850 | 0.818 |
| 90-100 % | 65 | 0.972 | 0.985 |

### Intervalos de confianza por decil (remuestreo por partido)

Desvío = frecuencia real − probabilidad prevista, en puntos. Un intervalo que no contiene el 0 indica que el desvío no es solo ruido.

| Decil | Cortes | Partidos | P media | Frecuencia | Desvío | IC 95 % | ¿Distinto de 0? |
|---|---|---|---|---|---|---|---|
| 0-10 % | 65 | 20 | 0.028 | 0.015 | -1.3 | [-3.3, 3.0] | no |
| 10-20 % | 22 | 13 | 0.150 | 0.182 | +3.1 | [-15.1, 25.1] | no |
| 20-30 % | 21 | 15 | 0.246 | 0.238 | -0.8 | [-17.5, 20.6] | no |
| 30-40 % | 37 | 20 | 0.349 | 0.486 | +13.7 | [-6.8, 31.6] | no |
| 40-50 % | 22 | 12 | 0.452 | 0.545 | +9.3 | [-12.6, 27.9] | no |
| 50-60 % | 22 | 12 | 0.548 | 0.455 | -9.3 | [-28.4, 12.1] | no |
| 60-70 % | 37 | 20 | 0.651 | 0.514 | -13.7 | [-32.3, 5.9] | no |
| 70-80 % | 21 | 15 | 0.754 | 0.762 | +0.8 | [-20.7, 16.6] | no |
| 80-90 % | 22 | 13 | 0.850 | 0.818 | -3.1 | [-26.4, 14.9] | no |
| 90-100 % | 65 | 20 | 0.972 | 0.985 | +1.3 | [-3.1, 3.3] | no |
