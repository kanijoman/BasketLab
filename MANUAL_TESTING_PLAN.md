# Plan de Pruebas Manuales — Análisis Predictivo (FASE 2-5)

> **Prerequisito:** La API está corriendo (`python run_api.py` o `uvicorn src.api.app:app --reload --port 8000`) y el frontend está arrancado (`cd frontend && npm run dev`).  
> **Herramienta recomendada:** Swagger UI en `http://localhost:8000/docs`

---

## 1. Preparación de datos (obligatorio antes de las fases 3-5)

### 1.1 Verificar que hay datos en el HISTORICAL

```
GET http://localhost:8000/api/v1/historical/summary
```

- **Espera:** Lista con al menos una entrada `{"league": "FEB", "competition": "LF2", "season": "...", "match_count": N}`.  
- **Si está vacío:** Ve al frontend → menú Admin → pestaña "Histórico" e ingesta mínimo 2 temporadas de la misma competición.  
  Se recomienda: 2 temporadas de FEB LF2 (≥ 20 partidos por temporada).

### 1.2 Anotar un `team_id` existente

```
GET http://localhost:8000/api/v1/historical/summary
```

Luego en MongoDB Compass (o mediante `GET /api/v1/historical/summary`) identifica un equipo con ≥ 15 partidos en la temporada más reciente. Anota:
- `team_id` (ej. `"100001"`)
- `season` (ej. `"2024-25"`)

---

## 2. FASE 2 — Estadísticas ajustadas por rival

### TC-2.1 Colección FEB vacía

```
GET /api/v1/analysis/FEB_LF2_2025_A/rival_adjusted
```
(usando una colección que exista pero sin partidos)

- **Espera:** `{}` con status 200.

### TC-2.2 Colección FEB con datos

```
GET /api/v1/analysis/<nombre_coleccion_feb>/rival_adjusted
```

- **Espera:** Dict `{nombre_equipo: {net_rtg: {raw_avg, adj, adj_avg, sos, n}, ...}}`.  
- **Verificaciones manuales:**  
  - `n` debe ser igual al número de partidos del equipo en esa colección.  
  - `adj_avg = raw_avg + adj` (comprueba con calculadora con un valor al azar).  
  - Si un equipo jugó solamente contra rivales débiles, su `adj_avg < raw_avg` (el rival era fácil → ajuste negativo).  
  - Ordena por `adj_avg` DESC: el equipo top debería ser el más consistente contra buenas defensas, no necesariamente el de mayor `raw_avg`.

### TC-2.3 Colección FBCYL

```
GET /api/v1/analysis/FBCYL_SE_2025_A/rival_adjusted
```

- **Espera:** Misma estructura que FEB. `pts` y `net_rtg` son las más relevantes.

### TC-2.4 Comprobación en el frontend

- Navega a `http://localhost:5173/<coleccion>/predictive` → pestaña "Ajuste por Rival".  
- Selecciona un stat del dropdown.  
- Comprueba que la tabla se ordena por "Media ajustada" de mayor a menor.  
- La columna "Ajuste rival" debe mostrar "+" verde para equipos con agenda dura y "−" rojo para agenda fácil.

---

## 3. FASE 3/4 — Modelo de elasticidades Ridge

### TC-3.1 Entrenamiento sin datos HISTORICAL (error)

```
POST /api/v1/analysis/elasticity/train
{}
```

Con HISTORICAL vacío → **Espera: 422** con mensaje `"No hay datos en HISTORICAL..."`.

### TC-3.2 Entrenamiento con datos suficientes

Con ≥ 2 temporadas y ≥ 3 equipos en el HISTORICAL:

```
POST /api/v1/analysis/elasticity/train
{"leagues": ["FEB"]}
```

- **Espera:** 200 con dict `{stat: {model_a: {r2, n}, model_b: {r2, n}}}`.  
- **Verificaciones:**  
  - `r2` entre -1 y 1 (valores ≥ 0 indican modelo útil; es normal que sean bajos ~0.1-0.4 con datos reales).  
  - `n > 0` para todos los stats que tengan datos.  
  - El entrenamiento activa los modelos en la colección `ELASTICITIES` de MongoDB.

### TC-3.3 Listar modelos después de entrenar

```
GET /api/v1/analysis/elasticity/models
```

- **Espera:** Lista de dicts, cada uno con `model_type` ("A" o "B"), `stat`, `r2_train`, `n_samples`, `n_teams`, `trained_at`.  
- **Verificación:** Deben aparecer 12 docs (6 stats × 2 modelos).

### TC-3.4 Predicción equipo con historial

```
GET /api/v1/analysis/elasticity/predict/<team_id>?season=<season>
```

- **Espera:** Dict `{stat: {model_a: {estimate, ci_low, ci_high, r2}, model_b: {...}}}`.  
- **Verificaciones:**  
  - `ci_low ≤ estimate ≤ ci_high`.  
  - Comparar `estimate` del `net_rtg` con el rolling promedio manual de los últimos 3 partidos del equipo. Deben ser cercanos.

### TC-3.5 Predicción con `is_home` y `opp_net_rtg` (Modelo B)

```
GET /api/v1/analysis/elasticity/predict/<team_id>?season=<season>&is_home=true&opp_net_rtg=5.0
```

- **Espera:** Respuesta igual pero `model_b.estimate` diferirá de `model_a.estimate` (el condicionamiento tiene efecto).

### TC-3.6 Predicción equipo sin historial

```
GET /api/v1/analysis/elasticity/predict/equipo-inexistente?season=2024-25
```

- **Espera:** 404.

### TC-3.7 Flujo completo en frontend

- Navega a pestaña "Elasticidades".  
- Pulsa "Entrenar modelos" → debe aparecer tabla de metadatos con 12 filas.  
- Introduce `team_id` y `season`, pulsa "Predecir" → tabla con Modelo A / Modelo B, estimación ± IC.

---

## 4. FASE 5 — Proyección Monte Carlo

### TC-5.1 Sin modelos entrenados

(Si saltaste el paso anterior, borra la colección ELASTICITIES)

```
POST /api/v1/analysis/montecarlo/<team_id>
{"season": "2024-25", "n_games": 3, "n_simulations": 100}
```

- **Espera:** 404 con `"No hay modelos entrenados..."`.

### TC-5.2 Sin historial del equipo

(Con modelos entrenados pero `team_id` inexistente)

```
POST /api/v1/analysis/montecarlo/equipo-fake
{"season": "2024-25", "n_games": 3, "n_simulations": 100}
```

- **Espera:** 404.

### TC-5.3 Simulación mínima (3 partidos, 100 sims)

```
POST /api/v1/analysis/montecarlo/<team_id>
{"season": "<season>", "n_games": 3, "n_simulations": 100}
```

- **Espera:** 200 con:
  ```json
  {
    "team_id": "...",
    "n_games": 3,
    "games": [
      {"game_index": 1, "win_prob": 0.55, "stats": {"net_rtg": {"mean": ..., "ci_low": ..., "ci_high": ...}, ...}},
      ...
    ],
    "projected_wins_mean": 1.65,
    "projected_wins_std": 0.79,
    "projected_wins_ci_low": 0.0,
    "projected_wins_ci_high": 3.0
  }
  ```
- **Verificaciones:**  
  - `0 ≤ win_prob ≤ 1` para cada partido.  
  - `ci_low ≤ mean ≤ ci_high` para cada stat.  
  - `projected_wins_mean` entre 0 y 3 (n_games).

### TC-5.4 Simulación con agenda personalizada

```
POST /api/v1/analysis/montecarlo/<team_id>
{
  "season": "<season>",
  "n_games": 4,
  "n_simulations": 500,
  "is_home_schedule": [true, false, true, false],
  "opp_net_rtg_schedule": [2.0, -3.0, 5.0, 0.0]
}
```

- **Verificación:** Los partidos contra rival fuerte (`opp_net_rtg=5.0`) deben tener `win_prob` menor que contra rival débil (`opp_net_rtg=-3.0`).

### TC-5.5 Validación de límites de parámetros

```
POST /api/v1/analysis/montecarlo/<team_id>
{"season": "2024-25", "n_games": 11, "n_simulations": 100}
```

- **Espera:** 422 (n_games > 10 no está permitido).

```
POST /api/v1/analysis/montecarlo/<team_id>
{"season": "2024-25", "n_games": 3, "n_simulations": 50}
```

- **Espera:** 422 (n_simulations < 100 no está permitido).

### TC-5.6 Estabilidad con muchas simulaciones

```
POST /api/v1/analysis/montecarlo/<team_id>
{"season": "<season>", "n_games": 5, "n_simulations": 2000}
```

- **Verificación:** Los IC deben ser más estrechos que con 100 sims (más sims = intervalos más precisos). La mediana de `projected_wins_mean` no debe diferir más de 0.3 respecto al resultado de 100 sims.

### TC-5.7 Flujo completo en frontend

- Navega a pestaña "Proyección MC".  
- Introduce `team_id`, `season`, sube n_sims a 1000 y n_games a 5.  
- Pulsa "Simular" → tarjetas resumen (media victorias ± σ, IC 90%) + tabla por partido (P(victoria) con colores, stats con IC).

---

## 5. Regresión — rutas existentes no afectadas (validar rapidamente)

| Endpoint | Espera |
|----------|--------|
| `GET /` | `{"status": "ok"}` |
| `GET /api/v1/historical/summary` | lista de grupos |
| `GET /api/v1/teams/<coleccion>/stats` | stats de equipo |
| `GET /api/v1/players/<coleccion>/stats` | stats de jugadores |
| `GET /api/v1/collections/list` | lista de colecciones |

---

## 6. Métricas de calidad esperadas (datos reales)

| Métrica | Umbral aceptable |
|---------|-----------------|
| `r2_train` de Modelo A (net_rtg) | ≥ 0.05 (los últimos 3-10 partidos predicen algo, aunque débilmente) |
| Ancho IC neto_rtg (90%) | 5-20 puntos (muy ancho = poca señal de datos; muy estrecho = sobreajuste) |
| `win_prob` rango en 5 partidos | Debe variar (no todos ≈ 0.5; el modelo debe diferenciar partidos) |
| Tiempo de entrenamiento | < 30 s para < 5 equipos × 2 temporadas |
| Tiempo de simulación (1000 sims × 5 partidos) | < 2 s |

---

## 7. Entornos a cubrir

- [ ] FEB LF2 (colección tipo `FEB_LF2_YYYY_A`)
- [ ] FBCYL (colección tipo `FBCYL_SE_YYYY_A`)
- [ ] Equipo con datos insuficientes (< 10 partidos) → verifiar graceful error
- [ ] Conexión perdida a MongoDB → todas las rutas devuelven error gestionado (no 500)
