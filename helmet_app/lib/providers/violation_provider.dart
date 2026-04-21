import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/api_service.dart';

class ViolationProvider extends ChangeNotifier {
  final ApiService api = ApiService();

  List<Map<String, dynamic>> active = [];
  List<Map<String, dynamic>> history = [];

  Timer? _timer;
  bool _isLoading = false;

  Function(Map)? onNewViolation;
  String? _lastEventId;

  String _fingerprint(List<Map<String, dynamic>> events) {
    return jsonEncode(
      events
          .map(
            (e) => {
              'event_id': e['event_id'],
              'name': e['name'],
              'status': e['status'],
              'risk': e['risk'],
              'time': e['time'],
              'image': e['image'],
            },
          )
          .toList(),
    );
  }

  bool _isSame(
    List<Map<String, dynamic>> a,
    List<Map<String, dynamic>> b,
  ) {
    return _fingerprint(a) == _fingerprint(b);
  }

  Future<void> loadAll() async {
    if (_isLoading) return;
    _isLoading = true;

    try {
      final results = await Future.wait([
        api.getEvents(),
        api.getHistory(),
      ]);

      final newActive = List<Map<String, dynamic>>.from(results[0]);
      final newHistory = List<Map<String, dynamic>>.from(results[1]);

      if (newActive.isNotEmpty) {
        final newest = newActive.first;
        if (_lastEventId != newest['event_id']) {
          _lastEventId = newest['event_id']?.toString();
          onNewViolation?.call(newest);
        }
      }

      var changed = false;

      if (!_isSame(active, newActive)) {
        active = newActive;
        changed = true;
      }

      if (!_isSame(history, newHistory)) {
        history = newHistory;
        changed = true;
      }

      if (changed) {
        notifyListeners();
      }
    } catch (e) {
      debugPrint('LOAD ERROR: $e');
    } finally {
      _isLoading = false;
    }
  }

  void start() {
    loadAll();
    _timer?.cancel();

    _timer = Timer.periodic(const Duration(seconds: 4), (_) {
      loadAll();
    });
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> resolveEvent(Map e) async {
    await api.resolve(e['event_id']);
    await loadAll();
  }

  Future<void> refresh() async {
    await loadAll();
  }

  Future<void> deleteEvent(Map e) async {
    await api.deleteEvent(e['event_id']);
    await loadAll();
  }
}
