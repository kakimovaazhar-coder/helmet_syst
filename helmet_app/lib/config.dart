class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://172.20.10.8:8000',
  );

  static String imageUrl(String? path) {
    if (path == null || path.isEmpty) {
      return apiBaseUrl;
    }

    final uri = Uri.tryParse(path);
    if (uri != null && uri.hasScheme) {
      return path;
    }

    return '$apiBaseUrl$path';
  }
}
