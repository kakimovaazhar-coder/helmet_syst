import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../config.dart';

class ViolationCard extends StatelessWidget {
  final Map e;
  final VoidCallback onTap;

  const ViolationCard({super.key, required this.e, required this.onTap});

  Widget buildRisk(int risk) {
    String text;
    Color color;

    if (risk <= 30) {
      text = "LOW";
      color = Colors.green;
    } else if (risk <= 70) {
      text = "MEDIUM";
      color = Colors.orange;
    } else {
      text = "HIGH";
      color = Colors.red;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        style: const TextStyle(color: Colors.white, fontSize: 12),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(blurRadius: 6, color: Colors.black.withValues(alpha: 0.06)),
        ],
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.all(12),
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: CachedNetworkImage(
            imageUrl: AppConfig.imageUrl(e['image'] as String?),
            width: 60,
            height: 60,
            fit: BoxFit.cover,
            placeholder: (_, __) => const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            errorWidget: (_, __, ___) => const Icon(Icons.broken_image),
          ),
        ),
        title: Text(
          e['name'] ?? "Unknown",
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(e['time']),
            const SizedBox(height: 4),
            buildRisk(e['risk']),
          ],
        ),
        trailing: const Icon(Icons.arrow_forward_ios, size: 16),
        onTap: onTap,
      ),
    );
  }
}
