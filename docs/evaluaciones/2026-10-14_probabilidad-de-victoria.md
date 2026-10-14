# Probabilidad de victoria: calibración con LF Challenge 2024/25 y 2025/26 (14/10/2026)

**Conclusión: el modelo es útil pero no cumple todavía el criterio para mostrarlo en la app.**

- **Datos**: 454 partidos (2024/25 y 2025/26, liga regular y play-offs), 6.356 cortes de 5 min, bajados con `python -m src.live_prep.download_games` (#301). La temporada 2023/24 **se descartó**: su play-by-play escribe los puntos como `(13 Pts)` y no como `(Puntos: 13)`, el motor lee 0-0 y cualquier previsión sería falsa (el evaluador ahora omite esos partidos).
- **Gana con claridad a «solo marcador y tiempo»** (log loss 0,373 frente a 0,420; MAE del margen 7,5 frente a 8,6 puntos). La probabilidad aporta, sobre todo, el valor previo.
- **No mejora a «solo valor previo»** (0,373 frente a 0,368): lo que muestra el partido (Four Factors) no añade nada a la previsión; `ff_beta` da igual entre 0 y 9. Hay que repensar cómo entra esa señal antes de venderla como «el partido se está torciendo».
- **Fiabilidad**: las medias por decil se acercan a la frecuencia (extremos 0-10 % y 90-100 % casi exactos), pero el mayor desvío es 6,4 puntos (9,1 en la temporada de validación) frente al límite de 5. Con 200-400 cortes por decil, y siendo los dos puntos de vista de un partido espejo uno del otro, el error de muestreo ronda ±3-4 puntos: **el criterio es más estricto que la precisión de la medición**.
- **Parámetros**: `wp_n0` = 120 gana en las tres ejecuciones y se adopta (antes 60). `wp_sigma` (12, mejor 13,5 en validación por 0,003) y `wp_home_adv` (4) se mantienen; `ff_beta` no se toca (no influye en la probabilidad). Mejora de log loss tras ajustar: 0,358 → 0,355 en la temporada de validación (2024/25 para ajustar, 2025/26 para validar).
- **Siguiente paso propuesto**: decidir con el usuario si se acepta un criterio acorde con la precisión medible (p. ej. «no peor que el valor previo ±0,005 en log loss, mejor que marcador y tiempo, desvío por decil ≤ 5 pts con n ≥ 400») y mejorar la señal del partido.

Las tablas son del modelo con `wp_n0=60` (los valores por defecto cuando se ejecutó); con 120 la mejora es la de arriba.

6356 cortes de 454 partidos (ambos puntos de vista, cortes cada 5 min). Parámetros actuales: `wp_sigma=12.0`, `wp_n0=60.0`, `wp_home_adv=4.0`, `ff_beta=9.0`.

## Variantes

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Modelo completo | 0.123 | 0.373 | 7.48 | 6.4 |
| Solo valor previo | 0.121 | 0.368 | 7.37 | 6.5 |
| Solo marcador y tiempo | 0.139 | 0.420 | 8.63 | 3.3 |

**Criterio para mostrarla en la app** (mejor que «solo marcador y tiempo» y que «solo valor previo» y desvío por decil ≤ 5 pts): NO cumplido.

## Fiabilidad del modelo completo

| Decil | n | P media | Frecuencia |
|---|---|---|---|
| 0-10 % | 1408 | 0.026 | 0.028 |
| 10-20 % | 512 | 0.147 | 0.164 |
| 20-30 % | 435 | 0.249 | 0.264 |
| 30-40 % | 424 | 0.347 | 0.410 |
| 40-50 % | 399 | 0.452 | 0.388 |
| 50-60 % | 399 | 0.548 | 0.612 |
| 60-70 % | 424 | 0.653 | 0.590 |
| 70-80 % | 434 | 0.751 | 0.735 |
| 80-90 % | 513 | 0.853 | 0.836 |
| 90-100 % | 1408 | 0.974 | 0.972 |

## Mejores parámetros (por log loss)

| Parámetros | Log loss | Brier | MAE |
|---|---|---|---|
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.370 | 0.122 | 7.44 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 4.5} | 0.370 | 0.122 | 7.43 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.370 | 0.122 | 7.42 |
| {'wp_sigma': 13.5, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.370 | 0.122 | 7.42 |
| {'wp_sigma': 13.5, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 4.5} | 0.371 | 0.122 | 7.43 |
| {'wp_sigma': 13.5, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.371 | 0.122 | 7.44 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 0.0, 'ff_beta': 0.0} | 0.371 | 0.122 | 7.47 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 0.0, 'ff_beta': 4.5} | 0.371 | 0.122 | 7.45 |

## Validación en una temporada aparte

3178 cortes de 227 partidos que no se usaron para ajustar. Parámetros ajustados: `{'wp_sigma': 13.5, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0}`.

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Parámetros por defecto (modelo completo) | 0.118 | 0.358 | 7.67 | 9.1 |
| Parámetros ajustados (modelo completo) | 0.117 | 0.355 | 7.60 | 7.1 |
| Solo valor previo | 0.116 | 0.350 | 7.53 | 8.2 |
| Solo marcador y tiempo | 0.136 | 0.412 | 9.00 | 5.3 |
