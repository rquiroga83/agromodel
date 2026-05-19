import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../config.dart';
import '../models/prediction.dart';

class ApiService {
  static Future<RecomendarResponse> recomendar(
    List<LatLng> poligono, {
    String? semestre,
  }) async {
    final coords = poligono.map((p) => [p.longitude, p.latitude]).toList();
    if (coords.isNotEmpty && coords.first != coords.last) {
      coords.add(coords.first);
    }

    final body = {
      'poligono': {
        'type': 'Polygon',
        'coordinates': [coords],
      },
      if (semestre != null) 'semestre': semestre,
    };

    final url = Uri.parse('${AppConfig.apiBaseUrl}/recomendar');
    final resp = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );

    if (resp.statusCode != 200) {
      throw Exception('API ${resp.statusCode}: ${resp.body}');
    }
    return RecomendarResponse.fromJson(jsonDecode(resp.body));
  }

  static Future<Map<String, dynamic>> health() async {
    final url = Uri.parse('${AppConfig.apiBaseUrl}/health');
    final resp = await http.get(url);
    if (resp.statusCode != 200) {
      throw Exception('Health ${resp.statusCode}: ${resp.body}');
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }
}
