# Tests de Playwright - End-to-End

Este directorio contiene tests end-to-end que usan Playwright para verificar el flujo completo de búsqueda de trenes en la aplicación.

## 🎭 Características

- **Navegador Visible por Defecto**: Los tests en esta carpeta se ejecutan con el navegador visible (`headless=False`)
- **Ralentización de Acciones**: Las acciones se ralentizan 500ms para mejor visualización
- **Configuración Automática**: El archivo `conftest.py` configura automáticamente el modo debug

## 📁 Estructura

```
tests_playwright/
├── conftest.py           # Configuración de pytest para modo debug
├── test_search_flow.py   # Tests del flujo completo de búsqueda
└── README.md            # Este archivo
```

## 🚀 Ejecutar Tests

### Ejecutar todos los tests de Playwright (navegador visible):

```bash
pytest tests_playwright/ -v -s
```

### Ejecutar un test específico:

```bash
pytest tests_playwright/test_search_flow.py::test_search_trains_flow_ourense_madrid -v -s
```

### Ejecutar excluyendo tests lentos:

```bash
pytest tests_playwright/ -v -s -m "not slow"
```

### Ejecutar solo tests lentos:

```bash
pytest tests_playwright/ -v -s -m "slow"
```

## ⚙️ Configuración

La configuración se maneja a través de variables de entorno y el archivo `playwright.config.py` en la raíz del proyecto.

### Variables de Entorno Disponibles:

| Variable | Por Defecto | Descripción |
|----------|-------------|-------------|
| `PLAYWRIGHT_HEADLESS` | `true` | `false` para navegador visible |
| `PLAYWRIGHT_SLOWMO` | `0` | Milisegundos de ralentización por acción |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Timeout global en milisegundos |
| `PLAYWRIGHT_VIDEO` | `false` | `true` para grabar videos |
| `PLAYWRIGHT_WIDTH` | `1280` | Ancho del viewport |
| `PLAYWRIGHT_HEIGHT` | `720` | Alto del viewport |

### Ejemplo con variables de entorno:

```bash
# Modo headless con grabación de video
PLAYWRIGHT_HEADLESS=true PLAYWRIGHT_VIDEO=true pytest tests_playwright/ -v

# Modo visual con ralentización de 1 segundo
PLAYWRIGHT_HEADLESS=false PLAYWRIGHT_SLOWMO=1000 pytest tests_playwright/ -v -s

# Viewport más grande
PLAYWRIGHT_WIDTH=1920 PLAYWRIGHT_HEIGHT=1080 pytest tests_playwright/ -v -s
```

## 📝 Tests Disponibles

### `test_search_trains_flow_ourense_madrid`
- **Ruta**: Ourense → Madrid (solo ida)
- **Pasajeros**: 1 adulto
- **Verifica**: Flujo completo básico

### `test_search_trains_flow_barcelona_madrid_roundtrip`
- **Ruta**: Barcelona → Madrid (ida y vuelta)
- **Pasajeros**: 2 adultos
- **Verifica**: Viaje redondo

### `test_search_trains_flow_multiple_passengers`
- **Ruta**: Madrid → Sevilla
- **Pasajeros**: 4 adultos
- **Verifica**: Múltiples pasajeros

### `test_search_trains_flow_valencia_alicante` (marcado como `slow`)
- **Ruta**: Valencia → Alicante
- **Pasajeros**: 1 adulto
- **Verifica**: Test adicional

## 🐛 Debug

Para debug más detallado, puedes:

1. **Ver logs en tiempo real**: Usa `-s` con pytest
   ```bash
   pytest tests_playwright/ -v -s
   ```

2. **Ejecutar solo un test**: Especifica el test exacto
   ```bash
   pytest tests_playwright/test_search_flow.py::test_search_trains_flow_ourense_madrid -v -s
   ```

3. **Aumentar ralentización**: Para ver acciones más despacio
   ```bash
   PLAYWRIGHT_SLOWMO=2000 pytest tests_playwright/ -v -s
   ```

4. **Grabar video**: Para análisis posterior
   ```bash
   PLAYWRIGHT_VIDEO=true pytest tests_playwright/ -v
   # Videos guardados en: test_results/videos/
   ```

## 📊 Resultados

Los tests generan archivos de respuesta en el directorio `responses/` con el formato:
```
[AAMMDD_HH24MISS]_[Status code]_buscarTrenFlow.do.log
```

Ejemplo: `251008_120802_200_buscarTrenFlow.do.log`

## 🔧 Añadir Nuevos Tests

Para añadir un nuevo test:

```python
@pytest.mark.asyncio
async def test_mi_nuevo_flujo():
    """Descripción del test."""
    print("\n🚂 Test: Mi ruta")
    
    filepath = await search_trains_flow(
        origin="ORIGEN",
        destination="DESTINO",
        date_out="2025-10-20",
        date_return=None,
        adults=1,
        headless=False,  # Visible en modo debug
    )
    
    assert filepath is not None
    assert os.path.exists(filepath)
    print(f"✅ Test completado: {filepath}")
```

## 💡 Consejos

- **Ejecuta primero un solo test** para verificar que todo funciona
- **Usa `-s`** para ver los prints en tiempo real
- **Marca tests lentos** con `@pytest.mark.slow` para poder excluirlos
- **El modo debug está activado por defecto** en este directorio gracias a `conftest.py`

