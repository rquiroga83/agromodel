import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/prediction.dart';

/// Capa de heatmap: dibuja un CircleMarker por pixel coloreado
/// segun la probabilidad del cultivo seleccionado (azul -> rojo).
class PixelHeatmap extends StatelessWidget {
  final List<PixelPrediccion> pixeles;
  final String cultivo;

  const PixelHeatmap({
    super.key,
    required this.pixeles,
    required this.cultivo,
  });

  /// Color HSL: azul (240) -> rojo (0) segun valor en [0,1].
  Color _heatColor(double value) {
    final v = value.clamp(0.0, 1.0);
    final hue = (240 - v * 240); // 240=azul, 0=rojo
    return HSLColor.fromAHSL(0.65, hue, 0.85, 0.5).toColor();
  }

  @override
  Widget build(BuildContext context) {
    return CircleLayer(
      circles: [
        for (final p in pixeles)
          CircleMarker(
            point: LatLng(p.lat, p.lon),
            radius: 25,
            useRadiusInMeter: true,
            color: _heatColor(p.probabilidades[cultivo] ?? 0.0),
            borderColor: Colors.transparent,
            borderStrokeWidth: 0,
          ),
      ],
    );
  }
}
