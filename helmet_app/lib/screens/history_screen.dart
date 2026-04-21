import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../config.dart';
import '../providers/violation_provider.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  Widget buildRiskBadge(int risk) {
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

  void confirmDelete(BuildContext context, Map e) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text("Delete event"),
        content: const Text("Are you sure you want to delete this event?"),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Cancel"),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              await Provider.of<ViolationProvider>(
                context,
                listen: false,
              ).deleteEvent(e);
            },
            child: const Text("Delete", style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = Provider.of<ViolationProvider>(context);

    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Text("History"),
        backgroundColor: Colors.orange,
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await Provider.of<ViolationProvider>(
            context,
            listen: false,
          ).refresh();
        },
        child: p.history.isEmpty
            ? const Center(child: Text("No history"))
            : ListView.builder(
                padding: const EdgeInsets.all(12),
                itemCount: p.history.length,
                itemBuilder: (_, i) {
                  final e = p.history[i];

                  return Dismissible(
                    key: Key(e['event_id']),
                    direction: DismissDirection.endToStart,
                    confirmDismiss: (_) async {
                      confirmDelete(context, e);
                      return false;
                    },
                    background: Container(
                      alignment: Alignment.centerRight,
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      decoration: BoxDecoration(
                        color: Colors.red,
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Icon(Icons.delete, color: Colors.white),
                    ),
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(
                            blurRadius: 6,
                            color: Colors.black.withValues(alpha: 0.08),
                          ),
                        ],
                      ),
                      child: ExpansionTile(
                        tilePadding: const EdgeInsets.all(12),
                        leading: ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: CachedNetworkImage(
                            imageUrl: AppConfig.imageUrl(e['image'] as String?),
                            width: 55,
                            height: 55,
                            fit: BoxFit.cover,
                            placeholder: (_, __) => const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                            errorWidget: (_, __, ___) =>
                                const Icon(Icons.broken_image),
                          ),
                        ),
                        title: Text(
                          e['name'] ?? "Unknown",
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        subtitle: buildRiskBadge(e['risk']),
                        children: [
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Divider(),
                                Text("Time: ${e['time']}"),
                                const SizedBox(height: 6),
                                Text("Duration: ${e['duration'].toInt()} sec"),
                                const SizedBox(height: 10),
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: IconButton(
                                    icon: const Icon(
                                      Icons.delete,
                                      color: Colors.red,
                                    ),
                                    onPressed: () => confirmDelete(context, e),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}
