import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../config.dart';

class ApiService {
  final String baseUrl = AppConfig.apiBaseUrl;

  Future<List<dynamic>> getEvents() async {
    final res = await http.get(Uri.parse("$baseUrl/events"));

    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    } else {
      throw Exception("Failed to load events");
    }
  }

  Future<List<dynamic>> getHistory() async {
    final res = await http.get(Uri.parse("$baseUrl/history"));

    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    } else {
      throw Exception("Failed to load history");
    }
  }

  Future<void> resolve(String id) async {
    final res = await http.post(Uri.parse("$baseUrl/resolve/$id"));

    if (res.statusCode != 200) {
      throw Exception("Resolve failed");
    }
  }

  Future<void> deleteEvent(String id) async {
    final res = await http.delete(Uri.parse("$baseUrl/event/$id"));

    if (res.statusCode != 200) {
      throw Exception("Delete failed");
    }
  }

  Future<bool> login(String email, String password) async {
    final res = await http.post(
      Uri.parse("$baseUrl/login"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"email": email, "password": password}),
    );

    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      return data["status"] == "ok";
    } else {
      return false;
    }
  }

  Future<String> register(String email, String password) async {
    final res = await http.post(
      Uri.parse("$baseUrl/register"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"email": email, "password": password}),
    );

    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      return data["status"];
    } else {
      return "error";
    }
  }

  Future<Map<String, dynamic>> getStats() async {
    final res = await http.get(Uri.parse("$baseUrl/stats"));

    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    } else {
      throw Exception("Stats error");
    }
  }

  Future<void> sendToken(String token) async {
    try {
      final res = await http.post(
        Uri.parse("$baseUrl/token"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"token": token}),
      );

      if (res.statusCode == 200) {
        debugPrint("TOKEN SENT");
      } else {
        debugPrint("TOKEN FAILED: ${res.statusCode}");
      }
    } catch (e) {
      debugPrint("TOKEN ERROR: $e");
    }
  }
}
