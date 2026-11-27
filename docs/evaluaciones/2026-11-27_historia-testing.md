# Historia de TESTING.md (incidentes, hallazgos y cronología)

Pasajes movidos de [TESTING.md](../TESTING.md) el 27/11/2026: cómo se encontró o cambió algo. El estado vigente y las reglas que salieron de ello están en TESTING.md.

## Cómo diseñamos los tests (prueba de rojo)

- Hasta #610 solo veía pytest: los arreglos de la web y de la app salían «sin tests» aunque los tuvieran.

## Cómo diseñamos los tests (invariantes del motor)

- Halló un fallo real: #619 (un aviso de flujo repetido contaba otra vez el evento del segundo en que se dijo).

## Mapa de tests

### Datos locales
- Con datos reales (puntual): 120 informes descifrados = JSON de `/reports/team-report` sin diferencias.

### Datos locales (comparación con la API)
- Con datos reales (puntual): informes reales de `raw.githubusercontent.com` abiertos con la clave abierta del manifiesto.

### Predictivo / páginas (verificación con axe)
- y **verificado con una publicación local real del LF Challenge (16 equipos) con axe en claro y oscuro a 390 y a 1280 px**, que encontró y obligó a arreglar el foco del mapa de calor y los contrastes de las insignias (#856).

### Archivo, refresco, catálogo
- Antes de quitar los ficheros se comprobó que el catálogo da lo mismo: el mismo refresco que `local_refresh.json`, el mismo catálogo de paquetes por nombre y los mismos calendarios.

### App Android live (maquetación #508)
- Su primera ejecución encontró dos desbordes reales a 320 px (la barra de velocidades del partido y el formulario de importar fichero).

### Datos locales (aislamiento de los vectores, #916)
- antes lo dejaban cambiado y `test_local_vectors.py` tras `test_market_vectors.py` creía ver un mongod real y corría el pipeline de FBCYL (`$substrCP`) sobre mongomock.

## CI

- Con `loadscope` un módulo entero iba a un solo proceso y los de vectores, de 80-180 s, dejaban a los demás esperando (#741).
- Antes: 8 min en un solo proceso; medido en local con 4 procesos, los 3.002 tests tardan 1 min 22 s.
- Base de cobertura medida 77,7 % (primer run de `main` con xdist, 14/10; antes 71,8 %).

## Marco cloud para la app Android (diseño original)

Capas gratuitas en GitHub Actions/Google: pytest del motor → motor en Pyodide (hecho) → UI en perfiles Android de Playwright con FEB y Drive simulados (`fake_feb`) → APK en emulador con Maestro → Firebase Test Lab → App Distribution. Fluidez: motor en Web Worker; con reproducción ×30 y CPU ×4 más lenta contar tareas largas del hilo principal. Canario diario contra un partido FEB finalizado.
