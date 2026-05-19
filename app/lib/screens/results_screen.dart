import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../config.dart';
import '../models/prediction.dart';
import '../widgets/crop_ranking.dart';
import '../widgets/pixel_heatmap.dart';

class ResultsScreen extends StatefulWidget {
  final RecomendarResponse response;
  final List<LatLng> poligono;

  const ResultsScreen({
    super.key,
    required this.response,
    required this.poligono,
  });

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  late String _cultivoSeleccionado;
  final MapController _mapController = MapController();

  @override
  void initState() {
    super.initState();
    _cultivoSeleccionado = widget.response.ranking.first.cultivo;
  }

  LatLng _centroide() {
    if (widget.poligono.isEmpty) {
      return const LatLng(AppConfig.initialLat, AppConfig.initialLon);
    }
    var lat = 0.0, lon = 0.0;
    for (final p in widget.poligono) {
      lat += p.latitude;
      lon += p.longitude;
    }
    return LatLng(lat / widget.poligono.length, lon / widget.poligono.length);
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.response;
    final centro = _centroide();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Recomendaciones'),
        backgroundColor: Colors.green[700],
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Icon(Icons.grid_on, color: Colors.green[700]),
                  const SizedBox(width: 8),
                  Text('${r.nPixeles} pixeles  ·  Semestre ${r.semestre}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Text('Ranking de cultivos',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          CropRanking(ranking: r.ranking),
          const SizedBox(height: 20),
          const Text('Mapa de probabilidad',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Text('Cultivo: '),
                  const SizedBox(width: 8),
                  Expanded(
                    child: DropdownButton<String>(
                      isExpanded: true,
                      value: _cultivoSeleccionado,
                      items: [
                        for (final c in r.ranking)
                          DropdownMenuItem(
                            value: c.cultivo,
                            child: Text(c.cultivo.replaceAll('_', ' ')),
                          ),
                      ],
                      onChanged: (v) {
                        if (v != null) setState(() => _cultivoSeleccionado = v);
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 380,
            child: Card(
              clipBehavior: Clip.hardEdge,
              child: Stack(
                children: [
                  FlutterMap(
                    mapController: _mapController,
                    options: MapOptions(
                      initialCenter: centro,
                      initialZoom: 14.0,
                      interactionOptions: const InteractionOptions(
                        flags: InteractiveFlag.pinchZoom | InteractiveFlag.drag,
                      ),
                    ),
                    children: [
                      TileLayer(
                        urlTemplate: AppConfig.satelliteTileUrl,
                        userAgentPackageName: AppConfig.userAgent,
                      ),
                      PolygonLayer(
                        polygons: [
                          Polygon(
                            points: widget.poligono,
                            color: Colors.transparent,
                            borderColor: Colors.greenAccent,
                            borderStrokeWidth: 2.5,
                          ),
                        ],
                      ),
                      PixelHeatmap(
                        pixeles: r.pixeles,
                        cultivo: _cultivoSeleccionado,
                      ),
                    ],
                  ),
                  Positioned(
                    right: 8,
                    bottom: 8,
                    child: Column(
                      children: [
                        FloatingActionButton.small(
                          heroTag: 'zoom_in',
                          backgroundColor: Colors.white,
                          foregroundColor: Colors.black87,
                          onPressed: () => _mapController.move(
                            _mapController.camera.center,
                            _mapController.camera.zoom + 1,
                          ),
                          child: const Icon(Icons.add),
                        ),
                        const SizedBox(height: 4),
                        FloatingActionButton.small(
                          heroTag: 'zoom_out',
                          backgroundColor: Colors.white,
                          foregroundColor: Colors.black87,
                          onPressed: () => _mapController.move(
                            _mapController.camera.center,
                            _mapController.camera.zoom - 1,
                          ),
                          child: const Icon(Icons.remove),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}
