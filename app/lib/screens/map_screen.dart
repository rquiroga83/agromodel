import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../config.dart';
import '../services/api_service.dart';
import 'results_screen.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();
  final List<LatLng> _polygonPoints = [];
  bool _loading = false;
  bool _satellite = false;

  void _addPoint(TapPosition tapPos, LatLng latlng) {
    setState(() => _polygonPoints.add(latlng));
  }

  void _undo() {
    if (_polygonPoints.isNotEmpty) {
      setState(() => _polygonPoints.removeLast());
    }
  }

  void _clear() {
    setState(_polygonPoints.clear);
  }

  Future<void> _analizar() async {
    if (_polygonPoints.length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Necesitas al menos 3 puntos para formar una parcela.')),
      );
      return;
    }

    setState(() => _loading = true);
    try {
      final response = await ApiService.recomendar(_polygonPoints);
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ResultsScreen(
            response: response,
            poligono: List<LatLng>.from(_polygonPoints),
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Error'),
          content: Text(e.toString()),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK')),
          ],
        ),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Que Sembrar?'),
        backgroundColor: Colors.green[700],
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: Icon(_satellite ? Icons.map : Icons.satellite_alt),
            tooltip: _satellite ? 'Vista mapa' : 'Vista satelital',
            onPressed: () => setState(() => _satellite = !_satellite),
          ),
          IconButton(
            icon: const Icon(Icons.undo),
            tooltip: 'Deshacer ultimo punto',
            onPressed: _polygonPoints.isEmpty ? null : _undo,
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Limpiar',
            onPressed: _polygonPoints.isEmpty ? null : _clear,
          ),
        ],
      ),
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: const LatLng(AppConfig.initialLat, AppConfig.initialLon),
              initialZoom: AppConfig.initialZoom,
              onTap: _addPoint,
            ),
            children: [
              TileLayer(
                urlTemplate: _satellite ? AppConfig.satelliteTileUrl : AppConfig.osmTileUrl,
                userAgentPackageName: AppConfig.userAgent,
              ),
              if (_polygonPoints.length >= 3)
                PolygonLayer(
                  polygons: [
                    Polygon(
                      points: _polygonPoints,
                      color: Colors.green.withValues(alpha: 0.3),
                      borderColor: Colors.green[800]!,
                      borderStrokeWidth: 2.5,
                    ),
                  ],
                ),
              if (_polygonPoints.isNotEmpty)
                MarkerLayer(
                  markers: [
                    for (final p in _polygonPoints)
                      Marker(
                        point: p,
                        width: 20,
                        height: 20,
                        child: Container(
                          decoration: BoxDecoration(
                            color: Colors.green[800],
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 2),
                          ),
                        ),
                      ),
                  ],
                ),
            ],
          ),
          Positioned(
            top: 12,
            left: 12,
            right: 12,
            child: Card(
              elevation: 4,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _polygonPoints.isEmpty
                      ? 'Toca el mapa para marcar los limites de tu parcela.'
                      : 'Puntos: ${_polygonPoints.length}. Toca para agregar mas, luego Analizar.',
                  style: const TextStyle(fontSize: 14),
                ),
              ),
            ),
          ),
          if (_loading)
            const ColoredBox(
              color: Color(0x66000000),
              child: Center(child: CircularProgressIndicator(color: Colors.white)),
            ),
        ],
      ),
      floatingActionButton: _polygonPoints.length >= 3
          ? FloatingActionButton.extended(
              onPressed: _loading ? null : _analizar,
              backgroundColor: Colors.green[700],
              icon: const Icon(Icons.analytics, color: Colors.white),
              label: const Text('Analizar parcela', style: TextStyle(color: Colors.white)),
            )
          : null,
    );
  }
}
