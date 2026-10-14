# Probabilidad de victoria: calibración con LF Challenge 2024/25 y 2025/26 (14/10/2026)

**Conclusión: el modelo es útil pero NO cumple el criterio para mostrarlo en la app. Se vuelve a medir cuando haya más datos de la temporada en curso.**

Criterio acordado el 14/10/2026: mejor que «solo marcador y tiempo», no peor que «solo valor previo» en más de 0,005 de log loss, y desvío ≤ 5 pts en los deciles con al menos 400 cortes.

- **Datos**: 454 partidos (2024/25 y 2025/26, liga regular y play-offs), 6.356 cortes de 5 min, bajados con `python -m src.live_prep.download_games` (#301). **2023/24 se descartó**: su play-by-play escribe los puntos como `(13 Pts)`, el motor lee 0-0 y cualquier previsión sería falsa (#303); el evaluador omite esos partidos.
- **Cumple las dos comparaciones**: log loss 0,370 frente a 0,420 de «solo marcador y tiempo» y a 0,368 de «solo valor previo» (dentro de la tolerancia). El MAE del margen es 7,4 frente a 8,6 puntos. Pero los Four Factors del partido **no aportan** sobre el prior: `ff_beta` da igual entre 0 y 9.
- **No cumple la fiabilidad**: con todo junto el mayor desvío es 7,5 pts (deciles 30-40 % y 60-70 %, con 409 cortes cada uno: la probabilidad es demasiado extrema en el tramo medio). **Solo con 2024/25 sí se cumple** (1,1 pts), pero 2025/26, la más reciente, se desvía hasta 10 pts: el modelo no es estable entre temporadas.
- **Ajuste**: `wp_n0` = 120 (adoptado). Se amplió la rejilla de `wp_sigma` hasta 18 (el mejor estaba en el borde con 13,5) y se probó encoger el prior del paquete: ninguna combinación arregla el tramo medio (log loss plano en 0,369-0,370) y el valor de `wp_sigma` sigue en 12 (13,5 mejora en 0,000-0,003, ruido). El factor de encogimiento del prior se descartó por no aportar.
- **Siguiente paso**: repetir con los partidos que se vayan jugando de 2026/27 (también como validación) y mejorar la señal del partido antes de mostrar nada al staff; la probabilidad, de mostrarse, descansaría sobre todo en el valor previo.

6356 cortes de 454 partidos (ambos puntos de vista, cortes cada 5 min). Parámetros actuales: `wp_sigma=12.0`, `wp_n0=120.0`, `wp_home_adv=4.0`, `ff_beta=9.0`.

## Variantes

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Modelo completo | 0.122 | 0.370 | 7.42 | 7.5 |
| Solo valor previo | 0.121 | 0.368 | 7.37 | 6.5 |
| Solo marcador y tiempo | 0.139 | 0.420 | 8.63 | 3.3 |

**Criterio para mostrarla en la app**: mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 7.5). **NO cumplido.**

## Fiabilidad del modelo completo

| Decil | n | P media | Frecuencia |
|---|---|---|---|
| 0-10 % | 1426 | 0.025 | 0.031 |
| 10-20 % | 514 | 0.146 | 0.160 |
| 20-30 % | 445 | 0.250 | 0.254 |
| 30-40 % | 409 | 0.349 | 0.423 |
| 40-50 % | 383 | 0.453 | 0.418 |
| 50-60 % | 385 | 0.547 | 0.582 |
| 60-70 % | 408 | 0.651 | 0.576 |
| 70-80 % | 445 | 0.749 | 0.746 |
| 80-90 % | 515 | 0.854 | 0.841 |
| 90-100 % | 1426 | 0.975 | 0.969 |

## Mejores parámetros (por log loss)

| Parámetros | Log loss | Brier | MAE |
|---|---|---|---|
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 0.0, 'ff_beta': 0.0} | 0.370 | 0.122 | 7.41 |
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 0.0, 'ff_beta': 9.0} | 0.370 | 0.122 | 7.40 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.370 | 0.122 | 7.44 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.370 | 0.122 | 7.42 |

## Validación en una temporada aparte

3178 cortes de 227 partidos que no se usaron para ajustar. Parámetros ajustados: `{'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0}`.

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Parámetros por defecto (modelo completo) | 0.117 | 0.354 | 7.60 | 10.1 |
| Parámetros ajustados (modelo completo) | 0.116 | 0.354 | 7.57 | 10.5 |
| Solo valor previo | 0.116 | 0.350 | 7.53 | 8.2 |
| Solo marcador y tiempo | 0.136 | 0.412 | 9.00 | 5.3 |
