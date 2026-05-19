/// Configuracion central de la app AgroPlus.
class AppConfig {
  /// URL base de la API. En emulador Android, usar 10.0.2.2 para acceder a localhost del host.
  /// En desktop/web, usar 127.0.0.1.
  static const String apiBaseUrl = 'http://10.0.2.2:8000';

  /// Centro inicial del mapa: Bogota, Cundinamarca.
  static const double initialLat = 4.65;
  static const double initialLon = -74.10;
  static const double initialZoom = 9.0;

  /// Tiles OpenStreetMap (libre, sin API key).
  static const String osmTileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

  /// Tiles satelitales ESRI World Imagery (libre, sin API key).
  /// Nota: ESRI usa orden {z}/{y}/{x}, distinto a OSM.
  static const String satelliteTileUrl =
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

  static const String userAgent = 'com.agroplus.app';
}
