# Visualización de Cancha de Baloncesto FIBA y Gráficos de Tiros

Módulo Python para generar visualizaciones de media cancha FIBA y gráficos de tiros de baloncesto a partir de datos de partidos FEB.

## Características

### Generación de Cancha
- Dimensiones oficiales de cancha FIBA (todas en metros)
- Elementos completos de la cancha:
  - Borde de media cancha
  - Zona/área de pintura
  - Línea de tres puntos
  - Círculo de tiro libre
  - Área restringida
  - Tablero y aro
  - Círculo de media cancha
- Temas de color predefinidos (light, wood, dark, classic, modern)
- Fondo blanco por defecto para visualizaciones limpias
- Colores y tamaños personalizables
- Exportación a PNG, PDF, SVG, etc.

### Visualización de Gráficos de Tiros
- Cargar datos de tiros desde archivos JSON de FEB
- Conversión automática de coordenadas (formato FEB → metros FIBA)
- Filtrar por equipo, cuarto o jugador
- Distinción visual entre tiros anotados/fallados
- Estadísticas de tiros y cálculo de precisión
- Estilo de cancha personalizable

## Dimensiones Oficiales FIBA

Basado en las reglas oficiales de baloncesto FIBA:
- Ancho de la cancha: 15.0 metros
- Longitud de media cancha: 14.0 metros (28/2)
- Zona (pintura): 5.8m × 4.9m
- Radio de línea de tres puntos: 6.75 metros
- Radio de círculo de tiro libre: 1.8 metros
- Radio de área restringida: 1.25 metros
- Diámetro del aro: 0.45 metros
- Ancho del tablero: 1.8 metros

Referencias:
- [Reglas Oficiales de Baloncesto FIBA (2020)](https://www.fiba.basketball/documents/official-basketball-rules/2020.pdf)
- [Equipamiento de Baloncesto FIBA](https://www.fiba.basketball/documents/BasketballEquipment.pdf)

## Uso

### Uso Básico

```python
from src.shotcharts import plot_court
import matplotlib.pyplot as plt

# Generar una cancha básica (fondo blanco por defecto)
fig = plot_court()
plt.show()

# Guardar en archivo
fig = plot_court(save_path='mi_cancha.png')
```

### Usando la Clase FIBACourt

```python
from src.shotcharts import FIBACourt
import matplotlib.pyplot as plt

# Crear instancia de cancha
court = FIBACourt()

# Generar gráfico
fig = court.plot_court(
    court_color='#FFFFFF',  # Fondo blanco (predeterminado)
    line_color='#000000',    # Líneas negras (predeterminado)
    title='Media Cancha FIBA',
    save_path='cancha_fiba.png',
    figsize=(12, 12),
    dpi=150
)

plt.show()
```

### Usando Temas Predefinidos

```python
from src.shotcharts import plot_court_with_theme
import matplotlib.pyplot as plt

# Temas disponibles: 'light' (blanco), 'wood', 'dark', 'classic', 'modern'
fig = plot_court_with_theme(
    theme='light',  # Fondo blanco
    title='Cancha FIBA - Tema Claro',
    figsize=(12, 12)
)

plt.show()
```

### Colores Personalizados

```python
from src.fiba_court import plot_court

fig = plot_court(
    court_color='#1E90FF',  # Azul dodger
    line_color='#FFD700',    # Dorado
    title='Cancha con Colores Personalizados'
)
```

### Superposición de Datos (ej. Gráfico de Lanzamientos)

```python
from src.shotcharts import FIBACourt
import matplotlib.pyplot as plt

# Crear cancha
court = FIBACourt()
fig = court.plot_court(title='Gráfico de Lanzamientos')
ax = fig.axes[0]

# Agregar datos de lanzamientos
shot_x = [7.5, 8.2, 6.8]
shot_y = [3.5, 5.2, 7.1]
made = [True, True, False]

# Graficar lanzamientos
for x, y, m in zip(shot_x, shot_y, made):
    color = 'green' if m else 'red'
    marker = 'o' if m else 'x'
    ax.scatter(x, y, c=color, s=100, marker=marker, zorder=10)

plt.show()
```

## Referencia de la API

### Clase FIBACourt

Clase principal para generar visualizaciones de media cancha FIBA.

**Métodos:**

- `plot_court(court_color, line_color, figsize, title, save_path, dpi)`: Genera y grafica la cancha

**Atributos:**

Todas las dimensiones se almacenan como atributos de instancia en metros (ej. `width`, `height`, `three_point_radius`, etc.)

### Funciones

**`plot_court(...)`**

Función de conveniencia para generar rápidamente una cancha.

Parámetros:
- `court_color` (str): Color de fondo
- `line_color` (str): Color de líneas
- `figsize` (tuple): Tamaño de figura (ancho, alto)
- `title` (str, opcional): Título del gráfico
- `save_path` (str, opcional): Ruta para guardar la imagen
- `dpi` (int): DPI para la imagen guardada

Retorna: `matplotlib.figure.Figure`

**`plot_court_with_theme(theme, ...)`**

Genera cancha con un tema predefinido.

Parámetros:
- `theme` (str): Nombre del tema ('light', 'dark', 'classic', 'modern')
- Parámetros adicionales iguales a `plot_court()`

Retorna: `matplotlib.figure.Figure`

### Temas Predefinidos

El diccionario **`COURT_THEMES`** contiene:

- **light**: Cancha blanca con líneas negras (predeterminado)
- **wood**: Cancha de madera clara con líneas negras
- **dark**: Cancha gris oscuro con líneas blancas
- **classic**: Madera clásica con líneas marrón silla
- **modern**: Gris claro con líneas azul real

## Dependencias

- `numpy`: Operaciones matemáticas
- `matplotlib`: Gráficos y visualización

## Formatos de Exportación

Soporta todos los formatos compatibles con matplotlib:

```python
# PNG (recomendado para web)
plot_court(save_path='court.png', dpi=150)

# PDF (recomendado para impresión)
plot_court(save_path='court.pdf', dpi=300)

# SVG (vectorial, editable)
plot_court(save_path='court.svg')

# JPG
plot_court(save_path='court.jpg', dpi=150)
```

---

## Visualización de Gráficos de Lanzamientos

### Inicio Rápido

```python
from src.shotcharts import plot_shot_chart
import matplotlib.pyplot as plt

# Crear un gráfico de lanzamientos para el equipo local
fig = plot_shot_chart(
    'path/to/feb_game.json',
    team=0,  # 0=local, 1=visitante
    title='Gráfico de Lanzamientos Equipo Local'
)
plt.show()
```

### Usando la Clase ShotChartVisualizer

```python
from src.shotcharts import ShotChartVisualizer

# Crear visualizador
viz = ShotChartVisualizer()

# Cargar lanzamientos desde JSON
shots = viz.load_shots_from_json('path/to/feb_game.json')

# Graficar todos los lanzamientos
fig = viz.plot_shots(shots, title='Todos los Lanzamientos')

# Filtrar por equipo
fig = viz.plot_shots(shots, team=0, title='Equipo Local')

# Filtrar por cuarto
fig = viz.plot_shots(shots, quarter=3, title='3er Cuarto')

# Filtrar por jugador
fig = viz.plot_shots(shots, player='15', title='Jugador #15')

# Combinar filtros
fig = viz.plot_shots(
    shots,
    team=1,
    quarter=4,
    title='Equipo Visitante - 4º Cuarto'
)
```

### Formato de Datos de Lanzamientos

El visualizador espera formato JSON de FEB con un array `SHOTCHART.SHOTS`. Cada lanzamiento tiene:
- `m`: Convertido (1) o fallado (0)
- `x`, `y`: Coordenadas (0-100, porcentaje de cancha completa)
- `team`: Identificador de equipo (0=local, 1=visitante)
- `player`: Dorsal/número del jugador
- `quarter`: Cuarto (1-4)
- `t`: Tiempo en el cuarto (mm:ss)

### Conversión de Coordenadas

El módulo convierte automáticamente coordenadas FEB (cancha horizontal completa, 0-100) a metros de media cancha FIBA:
- FEB usa una cancha completa (28m × 15m) con orientación horizontal
- Las visualizaciones muestran media cancha (14m × 15m) con orientación vertical
- Los lanzamientos se mapean hacia la canasta de ataque para cada equipo

### Personalización

```python
# Colores de cancha personalizados
fig = viz.plot_shots(
    shots,
    court_color='#E8F4F8',  # Azul claro
    line_color='#2C5F8D',    # Azul oscuro
    figsize=(14, 14),
    dpi=200
)

# Posición de leyenda personalizada (evita superposición con lanzamientos)
fig = viz.plot_shots(
    shots,
    legend_loc='lower center'  # Predeterminado: debajo de la cancha
    # Opciones: 'lower center', 'upper left', 'upper right', 'lower left', 'lower right'
)

# Ocultar leyenda
fig = viz.plot_shots(shots, show_legend=False)

# Guardar directamente
fig = viz.plot_shots(
    shots,
    save_path='mi_grafico_lanzamientos.png',
    dpi=300
)
```

### Métodos de Gráficos de Lanzamientos

#### `plot_shot_chart(json_path, team=None, quarter=None, player=None, **kwargs)`

Función de conveniencia para crear un gráfico de lanzamientos en un solo paso.

Parámetros:
- `json_path` (str|Path): Ruta al archivo JSON de FEB
- `team` (int, opcional): Filtrar por equipo (0 o 1)
- `quarter` (int, opcional): Filtrar por cuarto (1-4)
- `player` (int|str, opcional): Filtrar por número de jugador
- Parámetros adicionales iguales a `plot_shots()`

Retorna: `matplotlib.figure.Figure`

#### `ShotChartVisualizer.load_shots_from_json(json_path)`

Cargar datos de lanzamientos desde archivo JSON de FEB.

Parámetros:
- `json_path` (str|Path): Ruta al archivo JSON

Retorna: `list` de diccionarios de lanzamientos

Lanza:
- `FileNotFoundError`: Si el archivo JSON no existe
- `ValueError`: Si la estructura JSON es inválida

#### `ShotChartVisualizer.plot_shots(shots, **kwargs)`

Grafica lanzamientos en media cancha FIBA.

Parámetros:
- `shots` (list): Lista de diccionarios de lanzamientos
- `team` (int, opcional): Filtrar por equipo
- `quarter` (int, opcional): Filtrar por cuarto
- `player` (int|str, opcional): Filtrar por jugador
- `court_color` (str): Color de fondo de cancha (predeterminado: '#FFFFFF')
- `line_color` (str): Color de líneas de cancha (predeterminado: '#000000')
- `figsize` (tuple): Tamaño de figura (predeterminado: (12, 12))
- `title` (str, opcional): Título del gráfico
- `show_legend` (bool): Mostrar leyenda (predeterminado: True)
- `save_path` (str, opcional): Ruta de guardado
- `dpi` (int): DPI para imagen guardada (predeterminado: 150)

Retorna: `matplotlib.figure.Figure`

---

## Detalles de Implementación

### Línea de Tres Puntos

La línea de tres puntos se dibuja como tres componentes separados para evitar artefactos visuales:
1. Línea vertical izquierda desde la línea de fondo hasta el inicio del arco
2. Arco conectando ambas líneas verticales
3. Línea vertical derecha desde el final del arco hasta la línea de fondo

Los puntos de conexión del arco se calculan matemáticamente para asegurar una alineación perfecta sin espacios.

### Área Restringida

Similar a la línea de tres puntos, el área restringida se dibuja como:
1. Línea vertical izquierda desde el tablero hasta el inicio del arco
2. Arco semicircular
3. Línea vertical derecha desde el final del arco hasta el tablero

Esto asegura que no haya líneas horizontales cruzando el área.

### Calidad del Código

El módulo ha sido refactorizado con las siguientes mejoras:

- **Anotaciones de tipo**: Anotaciones de tipo completas para todas las funciones y métodos
- **Validación de entrada**: Todos los parámetros son validados con mensajes de error claros
- **Principio DRY**: Duplicación de código eliminada con métodos auxiliares
- **Propiedades**: Valores computados usan decoradores `@property` para claridad
- **Constantes**: Números mágicos reemplazados con constantes de clase nombradas
- **Manejo de errores**: Validación exhaustiva con excepciones informativas
- **Separación de responsabilidades**: Lógica de dibujo dividida en métodos enfocados

## Ejemplos

Ejecuta el módulo directamente para ver un ejemplo básico:

```bash
python -m src.shotcharts.fiba_court
```

O explora los scripts de uso de ejemplo:

```bash
# Ejemplos de generación de canchas
python -m src.shotcharts.example_usage

# Ejemplos de gráficos de lanzamientos
python -m src.shotcharts.example_shot_charts
```

Estos generarán visualizaciones de ejemplo y las mostrarán.

## Licencia

Este código genera canchas de baloncesto con dimensiones oficiales FIBA para propósitos de visualización de datos.

