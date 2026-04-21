import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/violation_provider.dart';
import '../widgets/violation_card.dart';
import 'violation_detail_screen.dart';
import 'history_screen.dart';
import 'login_screen.dart';
import 'stats_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    Provider.of<ViolationProvider>(context, listen: false).start();
  }

  @override
  void dispose() {
    Provider.of<ViolationProvider>(context, listen: false).stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Text("Violations"),
        backgroundColor: Colors.orange,
      ),

      // Drawer
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: Colors.orange),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.security, color: Colors.white, size: 40),
                  SizedBox(height: 10),
                  Text(
                    "Helmet System",
                    style: TextStyle(color: Colors.white, fontSize: 18),
                  ),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.warning),
              title: const Text("Violations"),
              onTap: () {
                Navigator.pop(context);
              },
            ),
            ListTile(
              leading: const Icon(Icons.bar_chart),
              title: const Text("Statistics"),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const StatsScreen()),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text("History"),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const HistoryScreen()),
                );
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text("Logout"),
              onTap: () {
                Navigator.pushAndRemoveUntil(
                  context,
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                  (route) => false,
                );
              },
            ),
          ],
        ),
      ),

      // Body
      body: Selector<ViolationProvider, List<Map<String, dynamic>>>(
        selector: (_, p) => p.active,
        builder: (_, active, __) {
          if (active.isEmpty) {
            return const Center(
              child: Text(
                "No violations",
                style: TextStyle(color: Colors.grey),
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () async {
              await Provider.of<ViolationProvider>(
                context,
                listen: false,
              ).refresh();
            },
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: active.length,
              itemBuilder: (_, i) {
                final e = active[i];

                return ViolationCard(
                  e: e,
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => ViolationDetailScreen(event: e),
                      ),
                    );
                  },
                );
              },
            ),
          );
        },
      ),
    );
  }
}
