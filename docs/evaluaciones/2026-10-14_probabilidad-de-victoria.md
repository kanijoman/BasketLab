# Probabilidad de victoria: primera calibración (14/10/2026)

**Conclusión: sin datos suficientes para calibrar ni para mostrarla en la app.** Con la competición de este año solo hay 16 partidos con play-by-play y, al pedir al menos 1 partido previo por equipo, quedan 8 partidos y 112 cortes (los dos puntos de vista de un partido no son independientes). Con esa muestra:

- El modelo completo gana claramente a «solo marcador y tiempo», pero **no** a «solo valor previo» (el prior es ruidoso con pocos partidos, y los Four Factors aún no aportan sobre él).
- El mayor desvío por decil (6,9 pts) supera el criterio de 5 pts, aunque con 7-21 cortes por decil no es concluyente.
- La rejilla prefiere `wp_sigma` bajos (9) y `wp_n0` altos (120), pero con 8 partidos sería sobreajuste: **no se cambian los valores por defecto** (`wp_sigma=12`, `wp_n0=60`, `wp_home_adv=4`, `ff_beta=9`).
- Siguiente paso: importar temporadas anteriores de FEB a MongoDB y repetir (`python -m src.live_prep.wp_cli --collection <colección> --out ...`).

Generado con `python -m src.live_prep.wp_cli` (cortes cada 5 min, latencia 0, prior solo con partidos anteriores).

112 cortes de 8 partidos (ambos puntos de vista, cortes cada 5 min). Parámetros actuales: `wp_sigma=12.0`, `wp_n0=60.0`, `wp_home_adv=4.0`, `ff_beta=9.0`.

## Variantes

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Modelo completo | 0.112 | 0.344 | 9.73 | 6.9 |
| Solo valor previo | 0.106 | 0.330 | 9.64 | 3.1 |
| Solo marcador y tiempo | 0.131 | 0.392 | 9.98 | 9.3 |

**Criterio para mostrarla en la app** (mejor que «solo marcador y tiempo» y que «solo valor previo» y desvío por decil ≤ 5 pts): NO cumplido.

## Fiabilidad del modelo completo

| Decil | n | P media | Frecuencia |
|---|---|---|---|
| 0-10 % | 21 | 0.027 | 0.000 |
| 10-20 % | 8 | 0.153 | 0.125 |
| 20-30 % | 9 | 0.259 | 0.111 |
| 30-40 % | 11 | 0.342 | 0.273 |
| 40-50 % | 7 | 0.449 | 0.714 |
| 50-60 % | 7 | 0.551 | 0.286 |
| 60-70 % | 11 | 0.658 | 0.727 |
| 70-80 % | 9 | 0.741 | 0.889 |
| 80-90 % | 8 | 0.847 | 0.875 |
| 90-100 % | 21 | 0.973 | 1.000 |

## Mejores parámetros (por log loss)

| Parámetros | Log loss | Brier | MAE |
|---|---|---|---|
| {'wp_sigma': 9.0, 'wp_n0': 120.0, 'wp_home_adv': 8.0, 'ff_beta': 0.0} | 0.321 | 0.110 | 9.61 |
| {'wp_sigma': 9.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.322 | 0.107 | 9.66 |
| {'wp_sigma': 9.0, 'wp_n0': 120.0, 'wp_home_adv': 8.0, 'ff_beta': 4.5} | 0.322 | 0.110 | 9.63 |
| {'wp_sigma': 9.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 4.5} | 0.322 | 0.108 | 9.68 |
| {'wp_sigma': 9.0, 'wp_n0': 120.0, 'wp_home_adv': 8.0, 'ff_beta': 9.0} | 0.323 | 0.111 | 9.65 |
| {'wp_sigma': 9.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.323 | 0.108 | 9.70 |
| {'wp_sigma': 9.0, 'wp_n0': 60.0, 'wp_home_adv': 8.0, 'ff_beta': 0.0} | 0.326 | 0.111 | 9.63 |
| {'wp_sigma': 10.5, 'wp_n0': 120.0, 'wp_home_adv': 8.0, 'ff_beta': 0.0} | 0.327 | 0.109 | 9.61 |
