# AgroPlus App — Que Sembrar?

Aplicacion movil/desktop en Flutter para consultar recomendaciones de cultivos sobre una parcela dibujada en el mapa.

## Caracteristicas

- Mapa OpenStreetMap (sin API key)
- Dibujo de poligono por toques sucesivos sobre el mapa
- Consulta del endpoint `/recomendar` de la API
- Pantalla de resultados con:
  - Ranking de los 8 cultivos mas probables (barras horizontales)
  - Mapa de calor por pixel para el cultivo seleccionado (azul = baja prob, rojo = alta prob)
  - Selector de cultivo

## Requisitos

- Flutter SDK 3.x
- API AgroPlus corriendo (ver `../api/README.md`)

## Configuracion de la URL de la API

Editar `lib/config.dart`:

```dart
// Para emulador Android (localhost del host = 10.0.2.2)
static const String apiBaseUrl = 'http://10.0.2.2:8000';

// Para desktop o web (mismo equipo)
static const String apiBaseUrl = 'http://127.0.0.1:8000';

// Para dispositivo fisico, usar la IP local del equipo donde corre la API
static const String apiBaseUrl = 'http://192.168.1.42:8000';
```

## Ejecutar

```bash
cd app

# Desktop (Windows)
flutter run -d windows

# Android (emulador o dispositivo)
flutter run -d <device-id>

# Listar dispositivos disponibles
flutter devices
```

## Estructura

```
lib/
├── main.dart                  # Entrada de la app
├── config.dart                # URL de la API y constantes
├── models/
│   └── prediction.dart        # Modelos de datos
├── services/
│   └── api_service.dart       # HTTP POST /recomendar
├── screens/
│   ├── map_screen.dart        # Pantalla 1: mapa + dibujo de poligono
│   └── results_screen.dart    # Pantalla 2: ranking + heatmap
└── widgets/
    ├── crop_ranking.dart      # Barras de probabilidad por cultivo
    └── pixel_heatmap.dart     # CircleMarker layer coloreada
```

## Flujo de uso

1. Usuario abre la app — ve el mapa centrado en Cundinamarca
2. Toca el mapa para marcar los limites de su parcela (>= 3 puntos)
3. Toca "Analizar parcela"
4. La app envia el poligono (GeoJSON WGS84) a la API
5. Recibe el ranking + lista de pixeles con sus probabilidades
6. Pantalla de resultados:
   - Ranking ordenado de cultivos
   - Mapa con heatmap del cultivo seleccionado
