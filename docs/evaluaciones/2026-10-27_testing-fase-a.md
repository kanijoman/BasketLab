# Estrategia de testing: evaluación de la fase A (27/10/2026, #540)

Pregunta: la fase A (TDD con el estado más real posible, prueba de rojo en el CI y constructor de partidos `tests/builders.py`, integrada el 23/10/2026) ¿funciona, y qué fases de B y C merecen la pena? La fecha prevista era el 6-9/11; se adelanta porque los criterios de entrada ya se cumplían (28 PRs con el job frente a los 6-8 pedidos, `builders.py` en uso y feedback de la 0.4.0 recibido).

## Método
- **Prueba de rojo**: los 28 PRs integrados del #549 (el que estrenó el job) al #609, sin Dependabot. Veredicto del job `red-proof` del CI y, con el script de #610, reejecución de cada PR (su cabeza frente al primer padre de su fusión, con los `node_modules` actuales).
- **Bugs**: los 24 issues con la etiqueta `bug` abiertos desde el 23/10. Causa raíz leída en el issue y en el commit del arreglo, si el arreglo llevó test de regresión (pytest o vitest) y si una de las esquinas del checklist de [TESTING.md](../TESTING.md) habría llevado a escribir el test que lo atrapa (criterio estricto: solo cuando la causa es de verdad ese tipo de esquina).
- **Fricción**: duración del job en 27 ejecuciones (API de Actions) y avisos falsos.

## Resultados

### Prueba de rojo
| Veredicto | Job del CI (antes de #610) | Reejecutado con #610 |
|---|---|---|
| RED | 14 | **20** |
| Solo documentación | — | 4 |
| Sin prueba de rojo | 2 | 1 |
| No cambia tests | 12 | 3 |

- **Ningún test que no probara nada.** Los avisos «sin prueba de rojo» fueron una retirada de código (#552, sus tests pasan con la base por definición), un cambio solo de tests para que no tocaran la red (#581, cerrado; su cambio fue en #579) y #579, cuyos tests de verdad eran de vitest.
- **El defecto real era un punto ciego**: el job solo veía pytest y 13 de los 28 PRs traían tests de vitest (web o app live); 6 de ellos (#572, #574, #578, #579, #584, #606) solo tienen prueba de rojo en vitest. Corregido en #610, que además encontró un rojo falso en Windows (ruta corta `MANUEL~1`: vite no encontraba sus ficheros de arranque).
- Los 3 «no cambia tests» que quedan son legítimos: la migración de react-router 6 → 7 (#553, sin cambio de comportamiento, cubierta por la suite) y dos estudios con scripts y docs (#582, #589).
- **Coste**: 36 s de media (29-45 s) frente a ≈ 6 min del job del backend, en paralelo; con #610 los PRs con vitest añaden su `npm ci`. Sin falsos positivos en el CI.
- `tests/builders.py`: lo usan 39 ficheros de tests, 14 de los tocados desde el 23/10.

### Bugs desde el 23/10 frente al checklist de esquinas
| Clase | Bugs | Cuáles |
|---|---|---|
| **Esquina del checklist** | **6** | frontera de periodo y prórroga (#515, #561), datos que llegan tarde o corregidos (#564, #560 en parte), FEB y FBCYL (#514), determinismo (#539) |
| Lógica o definición de producto | 3 | #563, #565, #602 |
| Estado entre pantallas o ciclo de vida de la app | 3 | #513, #556, #557 |
| Interacción entre reglas | 2 | #517 (misma evidencia contada otra vez), #568 (posturas contradictorias) |
| Integración entre componentes o caché | 2 | #601 (cuartiles sin los filtros de la tabla), #605 (dos formas en una clave de React Query) |
| Maquetación, dispositivo, permisos del CI | 3 | #507, #559, #554 |
| No era un fallo del código o hueco conocido | 5 | #518, #519, #558, #594, #603 |

- **El checklist habría atrapado 6 de los 19 fallos de código** (32 %); 5 de esos 6 llegaron al staff. La muestra es sobre todo de código anterior a la fase A (la 0.4.0 salió el 23/10): mide lo que el checklist *habría* atrapado, no lo que ha atrapado.
- **21 de los 24 los encontró el uso real** (staff o usuario); 3 el CI o una comparación (#539, test intermitente; #554, ejecución programada; #594, contraste con el PDF).
- **Los puntos débiles están en las apps, no en el motor**: los 8 fallos de la app live y la web son de maquetación, estado entre pantallas, ciclo de vida o integración con la caché, y ninguno es una esquina del checklist. En el motor son esquinas de datos (periodo, retraso del pbp) o interacción entre reglas.
- Tests de regresión: 9 arreglos con pytest, 7 con vitest, 2 con ambos y 6 sin test (4 sin cambio de código, #559 solo con un test de diagnóstico y #594 con una guarda que ya existía): **la mitad de los arreglos con test eran de vitest**, invisibles para la prueba de rojo hasta #610.

## Decisión
- **La fase A se mantiene** tal cual, con #610: la prueba de rojo es barata, no da ruido y ya cubre las tres suites.
- **Checklist ampliado** con las esquinas de los fallos que no cubría (regla del propio checklist: cada bug añade la suya): en las apps, volver a una pantalla o cambiar de partido con el estado anterior cargado, ciclo de vida (desconexión, cerrar y volver), una clave de caché con una sola forma y lo que se pinta junto con los mismos filtros; en el motor, dos reglas sobre el mismo momento (contradicción o la misma evidencia repetida).
- **Propuesta para la fase B y C** (pendiente de decisión del usuario):
  - **B1 #544 (invariantes del motor) y B3 #546 (partidos raros)**: sí, acotadas a lo que ha fallado. Invariantes: los parciales no cruzan cuartos, la duración es la de los periodos jugados, no hay dos posturas contrarias ni la misma evidencia dos veces en la misma ventana. Partidos raros: los que causaron #560, #561 y #564 (tabla corregida, fin de partido, pbp con retraso).
  - **B2 #545 (nightly de robustez)**: sigue aplazada. El único fallo de determinismo (#539) ya lo destapó el CI en paralelo con `xdist`.
  - **C1 #547 (`mongod` real y schemathesis) y C2 #548 (mutación)**: archivar. Ningún fallo de la muestra viene de la semántica de Mongo ni del contrato de la API, y la prueba de rojo no ha encontrado tests vacíos. C1 se reabre con el contrato de la web multiusuario (#110, #591).
