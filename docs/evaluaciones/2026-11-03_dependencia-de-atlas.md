# Evaluación: quitar la dependencia de Atlas

Parte de la épica #326 (apagar Render, #334). Pregunta: ¿se puede dejar de usar MongoDB Atlas, ahora que el archivo privado y el Mongo efímero (#646) existen? Es una evaluación de lectura: **no se ha tocado Atlas** (sin credenciales en local, y los scripts puntuales no escriben ni leen de ahí) ni se ha cambiado ningún workflow.

**Veredicto: GO, por pasos y con una condición previa** (comprobar que el archivo no pierde nada que solo tenga Atlas). Es más corto de lo que parece porque el trabajo pesado ya está hecho: el archivo ya es la fuente de `web-data`.

## Quién usa Atlas hoy

| Consumidor | Qué hace con Atlas | Estado |
|---|---|---|
| `atlas-refresh.yml` | **escribe** (`ATLAS_WRITE_URI`) con `config/atlas_refresh.json`, 3 veces al día, y rellena `DERIVED` | lo sustituye, en la práctica, el paso de scrape de `web-data` |
| `web-data.yml` | con `ARCHIVE_DEPLOY_KEY` ya no lee Atlas: restaura el archivo en un Mongo efímero, **scrapea lo nuevo con `config/local_refresh.json`**, rellena `DERIVED`, construye, publica y guarda el archivo | Atlas solo como respaldo si falta la clave |
| `live-packages.yml` | **lee** (`ATLAS_READ_URI`, con la de escritura de respaldo) | **por migrar** |
| `rule-evaluation.yml` | **lee** (a mano) | **por migrar** (poco uso) |
| API de Render | lee | desaparece con #334 |
| Desarrollo local | cadena de conexión | pasa a archivo + Mongo local |

## Lo que se ha comprobado

**1. El scrape de `web-data` ya cubre lo mismo que el de Atlas.** Las dos configuraciones tienen las mismas 8 competiciones. Solo difieren en dos cosas: `local_refresh.json` añade `recheck_days` y trae la 3ª FEB con `groups: all` (la de Atlas, solo A-B, por el límite de 512 MB que ya no aplica al archivo; decisión de #435).

**2. La cadena actual y sus tiempos** (ejecuciones reales de los dos últimos días):

| Paso | Duración |
|---|---|
| `Atlas refresh` (scrape + `DERIVED`) | 4–5 min |
| `Live packages` (tras el refresh) | 6,5–7 min |
| `Web data` (tras el refresh) | 45–60 min; 1 h 37 la primera vez con imágenes de FBCYL |

`web-data` y `live-packages` arrancan **a la vez**, disparados por `workflow_run` del refresco de Atlas. Varias ejecuciones de `web-data` salen canceladas: con un solo grupo de concurrencia (`cancel-in-progress: false`) una ejecución en cola se sustituye por la más nueva si la anterior sigue en marcha (una dura casi una hora y el refresco dispara cada pocas horas), y los partidos nuevos esperan a la siguiente que sí corra.

**3. Mismo orden de magnitud para restaurar.** Cargar el archivo completo en un Mongo vacío tarda 12 s (medido en #646: 1.912 partidos, 49 MB comprimidos). No es el cuello de botella de ningún consumidor.

## Lo que NO se ha podido comprobar

- **Que el archivo tenga todo lo que tiene Atlas.** Requiere comparar el recuento de partidos por colección entre los dos, de solo lectura y con credenciales que no hay aquí. Es la **condición previa**: hay que hacerlo (una vez, a mano o con un workflow de solo lectura) antes de apagar nada.
- **De dónde sale FBCYL en el archivo.** Ninguna de las dos configuraciones lleva scrapes de FBCYL (`atlas_refresh.py` solo rellena su `DERIVED`; la ingesta FBCYL del refresco es #446, aplazado). Lo más probable es que entrara con la carga inicial desde la base local y se mantenga con ingestas a mano. Si es así, **Atlas no es la fuente de FBCYL**, pero hay que confirmarlo y dejar escrito cómo se mete un FBCYL nuevo en el archivo sin Atlas.

## Riesgos y cómo se tratan

| Riesgo | Tratamiento |
|---|---|
| **`live-packages` depende de la frescura**: hoy sale 7 min tras el refresco; detrás de `web-data` serían 1–1,5 h | no encadenarlo a `web-data`: darle su propio paso corto (descargar el archivo, restaurar, scrapear lo nuevo, construir). Alternativa: un job «refresco» que sube el archivo y del que cuelgan los dos |
| **Quién dispara `web-data`**: hoy lo dispara el refresco de Atlas; sin él no hay disparador | cron propio (las mismas 3 horas) y `workflow_dispatch` |
| **Un solo escritor del archivo**: se guarda con un commit forzado | que escriba solo el job de refresco; el resto lo lee. El guarda `--no-shrink` y `--force-with-lease` ya evitan pisar un archivo más nuevo |
| **Pérdida del respaldo**: Atlas es hoy una segunda copia | el archivo conserva las 10 últimas versiones como etiquetas; antes de borrar Atlas, una última copia completa fuera |
| **Ejecuciones canceladas de `web-data`** | al separar el refresco de la publicación, el scrape (y el guardado del archivo) no depende de que la publicación larga llegue a correr |
| **El viernes de la release de la app** | no migrar `live-packages` en semana de release sin medir una vuelta completa antes |

## Plan acordado (cada paso, un PR de la misma naturaleza)

1. **Comprobación previa** (de solo lectura): recuento de partidos por colección en Atlas y en el archivo, y confirmar el camino de FBCYL. Si hay diferencias, se importan al archivo antes de seguir.
2. **Catálogo único de competiciones** (`config/competitions.json`, decidido el 03/11/2026): una entrada por competición con el scrape (`competition_url`, `season_value`, `groups`, `recheck_days`), los paquetes y reglas (`level`, `gender`, `clubs`, `rule_config`, `group_rules`), lo que sigue el grabador y `active`. El refresco, `live-packages` y el grabador lo leen; `local_refresh.json` y `atlas_refresh.json` se derivan o desaparecen, y `feb_watchlist.json` y `package_publish.json` conservan solo lo que no es de competiciones (el club, el acceso, las claves). Un test falla si algo referencia una competición ausente del catálogo.
3. **Refresco sin Atlas**: un job que restaura el archivo, scrapea las competiciones activas del catálogo, rellena `DERIVED` y guarda el archivo (lo que `web-data` ya hace), con cron propio.
4. **`live-packages` y `rule-evaluation` leen del Mongo efímero**, con su propio paso corto (no colgados de `web-data`). Medir una vuelta completa antes de quitar la lectura de Atlas y no hacerlo en semana de release.
5. **Quitar el respaldo de Atlas de `web-data`** y retirar `atlas-refresh.yml`, `config/atlas_refresh.json` y `run_atlas_refresh.py` con sus tests y docs.
6. **Cierre**: copia final de Atlas, retirar los secretos `ATLAS_*` y la documentación (OPERATIONS, ARCHITECTURE, LIVE), y la API de Render con #334.

## Ciclo de vida de una competición

| Acción | Cómo | Efecto |
|---|---|---|
| **Añadir** | entrada en el catálogo por PR; primera carga pesada con *Run workflow* y `only`; demo con `demo_builder` (manual) | se scrapea, publica y graba |
| **Pausar** | `active: false` | deja de scrapearse, publicarse y grabarse; los datos siguen en el archivo y en la web; reversible |
| **Retirar de verdad (purga)** | orden aparte, con **confirmación explícita** (nombre de la competición), tras quitar la entrada | borra del archivo y de la publicación; es el único camino que reduce el archivo |
| **Cambio de temporada** | entrada nueva y la anterior a `active: false` | las temporadas viejas ya se guardan ligeras |

Retirar una entrada solo **pausa**: nunca borra datos por sí misma. La purga necesita un modo deliberado del archivo, porque hoy `--no-shrink` se niega a sustituirlo por uno con menos partidos (es la guarda que impide perder partidos por un fallo).

## Qué cambia en el uso diario

- Refrescar datos deja de ser «scrapear contra Atlas»: se lanza el workflow o, en local, `run_archive.py pull` + `load` y el scraper contra el Mongo local.
- Una competición nueva se añade a **una** configuración (el catálogo), no a cuatro ficheros.
- Se pierde la consulta directa en el panel de Atlas; sustituye el Mongo local cargado desde el archivo.

## Decisiones que quedan para el autor

- ~~Si se acepta el plan y el orden~~: aceptado el 03/11/2026, con `live-packages` en su propio paso, catálogo único y purga con confirmación.
- Qué hacer con la copia final de Atlas (dónde se guarda) antes del paso 5.
