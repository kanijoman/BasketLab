# Local-first P1c: medición previa del archivo privado y el Mongo efímero (#646)

Las dos medidas que pedía #646 antes de escribir código: qué ocupa el archivo de partidos y cuánto tarda cargarlo en un Mongo efímero. Parte de la épica #326. El diseño y las decisiones siguen en el issue; aquí solo hay datos.

## Qué se midió y con qué

Sobre la **base local** del autor (`BASKETBALL`, 63 colecciones, 3 temporadas completas: 1.912 partidos y 635 MB en bruto), con un script puntual: serializar cada partido a JSON (`bson.json_util`) una línea por partido, comprimir en gzip nivel 6 por colección, volver a descomprimir, parsear e insertar en una base temporal de un `mongod` local (borrada al terminar). **No se pudo medir Atlas**: no hay credenciales en este entorno. Para tener el dato real basta `db.stats()` en Atlas (el límite gratuito es de 512 MB; la base local ya no cabría).

## Resultados

| Variante | Tamaño | Por partido |
|---|---|---|
| Bruto (JSON) | 632 MB | ≈ 330 KB |
| **Completo con PBP** (`PLAYBYPLAY`, `SHOTCHART`, caja, `DERIVED`…), gzip | **49,0 MB** | **25,6 KB** |
| **Ligero** (sin `PLAYBYPLAY`), gzip | 14,4 MB | 7,5 KB |

Coinciden con la estimación del issue (≈ 25 KB y ≈ 8 KB). El `PLAYBYPLAY` es ≈ 80 % del documento (272 KB de ≈ 320 KB en un partido de Primera FEB).

Por temporada (en comprimido): 2024-25 = 20,6 MB completo / 6,0 ligero; 2025-26 = 19,3 / 5,7; 2026-27 (en curso, 273 partidos) = 7,0 / 2,0. Es decir, el **conjunto de trabajo** de la política del issue (en curso + anterior completas, el resto ligero) ≈ 27 + 6 = **≈ 33 MB comprimidos** hoy, y crece ≈ 20 MB por temporada completa (≈ 5 MB si se pasa a ligero).

| Paso | Tiempo (PC local) |
|---|---|
| Serializar + gzip de los 1.912 partidos (completo **y** ligero) | 32 s |
| Descomprimir + parsear + insertar en un `mongod` vacío (completo) | **12 s** |

## Lectura

- **El archivo cabe sobrado en un repositorio privado**: 49 MB para todo lo que hay, un fichero por competición y temporada (el mayor, Primera FEB 24-25, ≈ 4 MB; el límite de GitHub es 100 MB por fichero).
- **La carga del Mongo efímero es barata** (12 s para todo; con el conjunto de trabajo, menos de la mitad). En el runner habrá que **levantar un `mongod`** (contenedor de servicio) y su arranque suma unos segundos; no se ha medido en Actions, y el ritmo de disco/CPU del runner será distinto del de este PC. Orden de magnitud: segundos, no minutos.
- **Atlas ya no es el cuello para los jobs**: el efímero no tiene límite de 512 MB (la base local de 635 MB cabe en el disco del runner). Sí lo sigue siendo para la API de Render hasta P7 (#334), con solo la temporada en curso (273 partidos = 103 MB hoy).

## Qué hay que decidir al implementar (no medido)

- **Historial del repositorio privado**: si cada refresco hace un commit con ficheros cambiados, la temporada en curso (≈ 7 MB completo hoy) se añade al historial 3 veces al día. Camino previsto: el mismo patrón que `live-packages` (commit único con `push -f`), conservando las últimas N versiones con **etiquetas** (un objeto referenciado por una etiqueta sobrevive al `push -f`). Alternativa: ficheros por temporada cerrada (inmutables, nunca se reescriben) y solo se reemplaza el de la temporada en curso.
- **Ventana de reescrapeo** de partidos recientes (correcciones de FEB): tamaño de la ventana y qué pasa con un partido que FEB corrige tarde. Sale de #393/#352.
- **Sembrado inicial**: la propia BD local (este script ya hace casi todo el trabajo).
- Con **FBCYL** el documento tiene otro esquema; el archivo es opaco (un documento por línea), no hace falta entenderlo.
