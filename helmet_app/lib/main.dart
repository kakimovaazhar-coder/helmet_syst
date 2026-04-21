import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app.dart';
import 'providers/violation_provider.dart';
import 'services/api_service.dart';
import 'services/notification_service.dart';

Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  debugPrint('BACKGROUND MESSAGE: ${message.notification?.title}');
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  await NotificationService.init();

  final violationProvider = ViolationProvider();

  FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);
  await FirebaseMessaging.instance.setForegroundNotificationPresentationOptions(
    alert: true,
    badge: true,
    sound: true,
  );

  final messaging = FirebaseMessaging.instance;

  await messaging.requestPermission(
    alert: true,
    badge: true,
    sound: true,
  );

  final token = await messaging.getToken();

  debugPrint('--------- FCM TOKEN ---------');
  debugPrint(token);
  debugPrint('-----------------------------');

  if (token != null) {
    await ApiService().sendToken(token);
  }

  FirebaseMessaging.instance.onTokenRefresh.listen((newToken) {
    debugPrint('TOKEN UPDATED: $newToken');
    ApiService().sendToken(newToken);
  });

  FirebaseMessaging.onMessage.listen((RemoteMessage message) {
    debugPrint('FOREGROUND MESSAGE: ${message.notification?.title}');

    final title = message.notification?.title ?? 'Helmet Safety';
    final body = message.notification?.body ?? 'New safety alert';

    unawaited(NotificationService.showNotification(title, body));
    unawaited(violationProvider.refresh());
  });

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: violationProvider),
      ],
      child: const MyApp(),
    ),
  );
}
