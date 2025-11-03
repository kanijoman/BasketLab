# Shot Charts - Funcionalidad de Gráficos de Lanzamiento

## Descripción

Esta nueva funcionalidad integra la visualización de shot charts (gráficos de lanzamiento) en la aplicación de estadísticas de baloncesto. Permite visualizar todos los lanzamientos realizados por un equipo en una pista FIBA.

## Características

### 1. **Botón de Shot Charts**
- Nuevo botón en la ventana principal: **"📊 Shot Charts - Gráficos de Lanzamiento"**
- Se encuentra debajo del botón de estadísticas
- Requiere seleccionar competición, temporada y grupo

### 2. **Ventana de Shot Charts**

La ventana incluye:

#### Controles:
- **Selector de Equipo**: Desplegable con todos los equipos disponibles en la competición/grupo seleccionado
- **Botón "🔄 Actualizar Datos"**: Descarga los datos de shot chart desde la FEB para todos los partidos
- **Botón "📊 Generar Shot Chart"**: Genera la visualización para el equipo seleccionado

#### Visualización:
- Pista FIBA en orientación vertical (media pista ofensiva)
- Lanzamientos anotados en **verde** (círculos)
- Lanzamientos fallados en **rojo** (X)
- Título con estadísticas: nombre del equipo, lanzamientos anotados/total y porcentaje
- Leyenda con el número de lanzamientos anotados y fallados

#### Funcionalidades adicionales:
- Barra de herramientas de Matplotlib para zoom, pan, guardar imagen
- Barra de progreso durante la actualización de datos
- Mensajes informativos sobre el estado de las operaciones

## Uso

### Paso 1: Preparar datos
1. Abre la aplicación
2. Selecciona competición, temporada y grupo
3. Haz clic en **"Actualizar y Ver Estadísticas"** para descargar los datos de los partidos

### Paso 2: Abrir Shot Charts
1. Con la misma competición/temporada/grupo seleccionados
2. Haz clic en **"📊 Shot Charts - Gráficos de Lanzamiento"**
3. Se abrirá la ventana de Shot Charts

### Paso 3: Actualizar datos de lanzamientos
1. En la ventana de Shot Charts, haz clic en **"🔄 Actualizar Datos"**
2. El sistema descargará los datos de shot chart para todos los partidos
3. Espera a que termine el proceso (se muestra el progreso)

### Paso 4: Generar visualización
1. Selecciona un equipo del desplegable
2. Haz clic en **"📊 Generar Shot Chart"**
3. Se mostrará la visualización con todos los lanzamientos del equipo

## Detalles Técnicos

### Conversión de Coordenadas

El sistema FEB usa un sistema de coordenadas 0-100 para toda la pista horizontal:
- X: 0-100 (a lo largo de la pista, 28m)
- Y: 0-100 (ancho de la pista, 15m)

El visualizador convierte estas coordenadas a una media pista FIBA vertical:
- X: 0-15m (ancho, horizontal en la visualización)
- Y: 0-14m (media pista, vertical en la visualización)

**Importante**: Todos los lanzamientos se muestran en la media pista ofensiva. Los lanzamientos desde la media pista defensiva se reflejan especularmente para mostrarlos en el lado ofensivo.

### Estructura de Datos

Los datos de shot chart se almacenan en MongoDB en el campo `SHOTCHART` de cada partido:

```python
{
    "_id": match_code,
    "SHOTCHART": {
        "SHOTS": [
            {
                "x": "45.5",      # Coordenada X (0-100)
                "y": "52.3",      # Coordenada Y (0-100)
                "m": "1",         # 1 = anotado, 0 = fallado
                "team": "0",      # 0 = local, 1 = visitante
                "player": "7",    # Dorsal del jugador
                "quarter": "2"    # Cuarto (1-4)
            },
            # ... más lanzamientos
        ]
    }
}
```

### Módulos Involucrados

1. **`src/ui/shotchart_window.py`**: Ventana principal de shot charts
2. **`src/shotcharts/shot_visualizer.py`**: Lógica de visualización y conversión de coordenadas
3. **`src/shotcharts/fiba_court.py`**: Dibujo de la pista FIBA
4. **`src/scraper/api_client.py`**: Descarga de datos de shot chart desde la API de FEB

## Solución de Problemas

### "No hay datos disponibles"
- Asegúrate de haber actualizado las estadísticas primero
- Verifica que la competición/temporada/grupo estén seleccionados

### "No se encontraron datos de lanzamientos"
- Haz clic en "🔄 Actualizar Datos" para descargar los shot charts
- Algunos partidos pueden no tener datos de shot chart disponibles

### La visualización no se muestra
- Verifica que matplotlib esté instalado: `pip install matplotlib`
- Verifica que PyQt6 esté instalado: `pip install PyQt6`

## Mejoras Futuras

Posibles mejoras que se pueden implementar:

1. **Filtros adicionales**:
   - Filtrar por cuarto
   - Filtrar por jugador
   - Filtrar por tipo de lanzamiento (2 puntos, 3 puntos)

2. **Mapas de calor**:
   - Mostrar zonas calientes/frías
   - Visualización de eficiencia por zona

3. **Comparación**:
   - Comparar shot charts de dos equipos
   - Comparar diferentes períodos de la temporada

4. **Exportación**:
   - Exportar shot chart como PNG/PDF
   - Exportar datos de lanzamientos como CSV

5. **Estadísticas avanzadas**:
   - Eficiencia por distancia
   - Porcentaje por zona de la pista
   - Análisis de tendencias
