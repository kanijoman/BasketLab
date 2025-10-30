# MetricsForAll
Metrics for all es una aplicación para análisis estadístico avanzado de baloncesto usando información proporcionada por la FEB y distintas federaciones regionales en España. La funcionalidad básica es un scraper de datos de las fuentes configuradas donde están alojadas las competiciones (actualmente, sólo la FEB), para recuperar información estructurada y almacenarla en una base de datos en el cloud (MongoDB orientada a JSON).

Actualmente está en una primera fase de prueba de concepto con la competición de Liga Femenina 2 (LF2) de la FEB. Potencialmente se irán añadiendo más competiciones de la FEB y de otras federaciones autonómicas.

Añadir nuevas federaciones resulta un cambio complejo que se abordará en fases posteriores debido a que la estructura de la información difiere de la FEB y, por tanto, habría que aplicar una transformación a estos datos de origen para poder usar los mismos métodos de análisis.
Las funcionalidades actuales incluyen:
  * Ventana usando PyQt6 para selección de competición, temporada y grupo:
  * Botón "Actualizar y ver estadísticas:
     * Actualiza la información para la competición en la base de datos, de forma que tengamos siempre la versión más actualizada posible
     * Muestra una nueva ventana de estadísticas con dos pestañas: una de estadísticas básicas y otra de estadísticas avanzadas
  * Ventana de Estadísticas:
     * La información está coloreada en base a cuartiles: Q1 verde; Q2 amarillo, Q3 naranja y Q4 rojo
     * Se puede ordenar por cualquier columna de forma ascendente o descendente
