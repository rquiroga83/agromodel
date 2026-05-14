# API AgroPlus - Que Sembrar?

API REST de inferencia para recomendacion de cultivos sobre polígonos en Cundinamarca.

## Arranque

Desde la raiz del proyecto:

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

El primer arranque tarda ~30s cargando la vista minable (4.16M filas) y los modelos.
Si `l2_scaler.joblib` no existe, se reconstruye automáticamente al arrancar.

## Endpoints

### `GET /health`
Estado del servicio.

### `GET /cultivos`
Lista de los 18 cultivos soportados.

### `POST /recomendar`
Body:
```json
{
  "poligono": {
    "type": "Polygon",
    "coordinates": [[
      [-74.10, 4.60],
      [-74.10, 4.61],
      [-74.09, 4.61],
      [-74.09, 4.60],
      [-74.10, 4.60]
    ]]
  },
  "semestre": "2024A"
}
```

Respuesta:
```json
{
  "n_pixeles": 42,
  "semestre": "2024A",
  "ranking": [
    {"cultivo": "Papa", "prob_media": 0.72, "prob_max": 0.91, "color": "#8B4513"},
    {"cultivo": "Arveja", "prob_media": 0.18, "prob_max": 0.32, "color": "#7CFC00"}
  ],
  "pixeles": [
    {"lat": 4.512, "lon": -74.123, "cultivo_top1": "Papa",
     "probabilidades": {"Papa": 0.72, ...}}
  ]
}
```

## Prueba rápida con curl

```bash
curl -X POST http://localhost:8000/recomendar \
  -H "Content-Type: application/json" \
  -d '{
    "poligono": {
      "type": "Polygon",
      "coordinates": [[
        [-74.05, 5.05], [-74.05, 5.06],
        [-74.04, 5.06], [-74.04, 5.05],
        [-74.05, 5.05]
      ]]
    }
  }'
```
