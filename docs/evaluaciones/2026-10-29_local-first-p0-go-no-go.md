# Local-first P0: informe del spike (go/no-go) — #327

Cierra el spike de la épica #326 (29/10/2026). Pregunta: ¿se pueden servir las tablas y los informes de la web desde ficheros estáticos calculados en Actions, con las mismas cifras que la API y sin un servidor de lectura? Contexto y decisiones previas: [acceso y reparto (#591)](2026-10-28_acceso-y-reparto-591.md).

## Veredicto: **GO**

Los criterios de salida de #327 se cumplen con holgura y no ha aparecido ninguna funcionalidad probada que obligue a mantener un servidor de lectura. Las reservas (abajo) son trabajo conocido, no incógnitas.

| Criterio de #327 | Resultado |
|---|---|
| Paridad numérica con la API en las páginas portadas | **0 diferencias** (vectores a 9 decimales y datos reales; ver *Paridad*) |
| Primera consulta < ~2 s | Estimada en ≈ 0,7 s (4G rápida) a ≈ 2 s (4G lenta); ver *Rendimiento* |
| Paquete de temporada < ~15 MB | **0,3 MB comprimidos** (Primera FEB 25/26, la mayor): 50 veces menos |
| Medición en móvil de gama media | **No se hace**: decisión del 29/10 (la web en móvil es responsabilidad de quien la use; se optimiza la web, no se contrasta con una gama de teléfonos). Solo hay una estimación con CPU simulada |

## Qué se ha construido (todo integrado, ninguna página depende aún de ello salvo con `?data=local`)

1. **Contrato de filas** (#645): una fila por equipo y partido (FEB y FBCYL) y una por jugador y partido (FEB), exportada con los *pipelines* de Mongo que ya existían.
2. **Agregación en el dispositivo** (`frontend/src/localdata`): tablas de equipo y rival con los filtros de local/visitante, resultado y fechas; jugadores con USG%, ORtg, DRtg, PIE… (port de `live_core/advanced_stats`, redondeo como Python).
3. **Exportador y fuente local** (#648): `run_local_export.py` y `?data=local`, con vuelta a la API cuando no hay datos locales.
4. **Clase B** (#638, esta entrega): `run_local_reports.py` precalcula y sella por alcance el informe de equipo y el scouting de cada equipo.

## Paridad con la API

- **Vectores deterministas** (CI): una liga pequeña con partidos con y sin `DERIVED`, prórroga, empate FBCYL y jugador renombrado; los *pipelines* reales sobre mongomock con 11–14 filtros; el navegador reproduce las cifras a 9 decimales. Mutar una fórmula hace fallar entre 10 y 12 tests.
- **Datos reales** (puntual, tu Mongo local): 5 competiciones × 8 filtros —equipo, rival y jugador, FEB y FBCYL— sin diferencias.
- **Informes** (clase B): 120 informes descifrados idénticos al JSON de `GET /reports/team-report`.

## Rendimiento (estimación, no medida en dispositivo)

Primera FEB 25/26 completa (542 filas de equipo, 5.859 de jugador; 2,35 MB en bruto, 282 KB comprimidos):

| CPU | Del fichero a la tabla pintada (parseo + agregación + render) | Heap JS |
|---|---|---|
| normal | 43–48 ms | 11–12 MB |
| ×4 más lenta | 231–246 ms | 11–13 MB |
| ×6 más lenta | 341–353 ms | 11–12 MB |

La red es analítica: 282 KB ≈ 0,4 s en 4G rápida y ≈ 1,6 s en 4G lenta, y en visitas siguientes sale de la caché. Cada cambio de filtro es local (≈ 15 ms en escritorio). Con varias temporadas a la vez el coste crece de forma lineal (0,3 MB cada una).

## Precálculo en Actions

| Qué | Resultado |
|---|---|
| Exportar las filas de **toda** la BD local (60+ colecciones) | 4 s; 16 MB en bruto, **1,9 MB comprimidos** |
| Informes de equipo y scouting de **todas** las competiciones | **1.000 informes en 41 s**; 4 MB en total (≈ 4 KB cada uno); Primera 5 s, LF Challenge 2 s |

El precálculo cabe con mucho margen en un job (Actions es gratis y sin límite de minutos en repo público; `live-packages` tiene un tope de 60 min). Salvedades: se midió contra Mongo local, no contra el Mongo efímero de #646; no incluye los PDF, que se precalcularían en el mismo job.

## Política de acceso de los informes

Un informe se sella una vez con una clave aleatoria y esa clave se envuelve para los alcances que pueden leerlo (`report_scopes`): el análisis propio de un equipo, para `club:<equipo>`; el scouting de un rival, para los clubes de la competición; todo, para `competicion:<col>`; y `abierto` mientras dure la beta. Las pruebas cubren que la clave de un club abre su análisis y todos los scoutings pero no el análisis de otro club. Los niveles y precios no están decididos (#591): cambiarlos es cambiar esa función y republicar, sin recifrar. Sigue vigente el límite de que no hay revocación dentro del periodo (se corta rotando el alcance).

## Hallazgos del spike (bugs de la API actual)

- **#642** FBCYL: la vista «Rivales» repite las cifras del propio equipo.
- **#643** El filtro «hasta» deja fuera los partidos del último día en FEB (no en FBCYL).
- **#647** Los jugadores de un equipo con el nombre inconsistente entre partidos pierden las cifras avanzadas.

El port local replica los tres comportamientos para tener paridad exacta (en FBCYL, el rival se comprueba por invariantes). Al corregirlos en la API se cambian a la vez los vectores y `frontend/src/localdata`.

## Reservas: lo que el spike NO prueba

- **Jugadores de FBCYL** (#644): su *pipeline* resuelve identidades por nombre y UUID; el diseño es resolverlas en el exportador.
- **Páginas que no leen estas dos tablas**: Comparativas (`/teams/{col}/compare`, derivable de las mismas filas: clase C), Posesiones, «Análisis pbp», Quintetos, Rotaciones (necesitan PBP o `DERIVED`), Evolución, Gráficos de tiro (zonas), Partido y Predictivo. Cada una es una fila más del contrato o un artefacto precalculado; ninguna parece imposible, pero ninguna está probada.
- **Scouting del rival completo** (`scouting_rival_service`, con comparación contra el equipo propio): solo se ha precalculado el informe por reglas (`team_report`). La comparación depende de un par de equipos (n²) y sigue abierta (#638).
- **Descifrado y desbloqueo en la web** (#639) y **alojamiento de los artefactos** (#640): la clase B se publica sellada, pero ninguna página la lee todavía.
- **Dispositivo real**: no se prueba (decisión del 29/10).

## Coste y riesgos de seguir

La estimación de la épica (3–6 meses a tiempo parcial hasta la paridad) sigue siendo razonable y se concentra en reescribir en TypeScript las consultas de cada página que no sea una suma de filas. Lo medido reduce el riesgo de las dos incógnitas principales (tamaño y paridad numérica). Los riesgos que quedan son de mantenimiento: dos implementaciones de cada fórmula (Python y TypeScript) que los vectores vigilan, y el cifrado sin revocación.

## Plan propuesto tras el go

1. **#640** Alojamiento de los artefactos (decide cómo se publican las filas y los informes) y **#646** archivo privado + Mongo efímero (quita el límite de Atlas y permite 3ª FEB completa).
2. **P1 (#328)** Exportador en Actions tras el refresco: filas e informes publicados con manifiesto versionado.
3. **#639** Desbloqueo en la web con claves por alcance, y primera página real servida estática para el staff (informe de equipo).
4. **P2 (#329)** `DataSource` con interruptor por página y migración de páginas en U5a–d.
5. Corregir #642, #643 y #647 en la API cuando convenga, con sus vectores.
6. Retomar #641 (predictivo) cuando se haga su rework.

Si el spike hubiera salido **no-go**, se habrían cerrado la épica y reanudado los issues congelados (#200, #202, #203, #112, #201). No es el caso.
