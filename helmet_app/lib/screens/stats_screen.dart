import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:provider/provider.dart';

import '../providers/violation_provider.dart';

class StatsScreen extends StatelessWidget {
  const StatsScreen({super.key});

  int _riskOf(Map event) {
    return ((event['risk'] ?? 0) as num).round().clamp(0, 100).toInt();
  }

  Widget _statCard({
    required IconData icon,
    required String title,
    required String value,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(blurRadius: 6, color: Colors.black.withValues(alpha: 0.08)),
        ],
      ),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: color.withValues(alpha: 0.14),
            child: Icon(icon, color: color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.grey),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _riskRow(String label, int count, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(label)),
          Text('$count', style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _riskChart(List<int> risks) {
    if (risks.isEmpty) {
      return const SizedBox.shrink();
    }

    final spots = List.generate(
      risks.length,
      (index) => FlSpot(index.toDouble(), risks[index].toDouble()),
    );

    return Container(
      height: 230,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(blurRadius: 6, color: Colors.black.withValues(alpha: 0.08)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Risk chart',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: LineChart(
              LineChartData(
                minY: 0,
                maxY: 100,
                minX: 0,
                maxX: risks.length <= 1 ? 1 : (risks.length - 1).toDouble(),
                gridData: FlGridData(
                  show: true,
                  horizontalInterval: 25,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (_) => FlLine(
                    color: Colors.grey.withValues(alpha: 0.25),
                    strokeWidth: 1,
                  ),
                ),
                borderData: FlBorderData(show: false),
                titlesData: FlTitlesData(
                  topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false, reservedSize: 0),
                  ),
                  rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false, reservedSize: 0),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 24,
                      interval: risks.length <= 6
                          ? 1
                          : (risks.length / 4).ceilToDouble(),
                      getTitlesWidget: (value, meta) {
                        final index = value.round();
                        if (index < 0 ||
                            index >= risks.length ||
                            (value - index).abs() > 0.01) {
                          return const SizedBox.shrink();
                        }

                        return Text(
                          '${index + 1}',
                          style: const TextStyle(
                            color: Colors.grey,
                            fontSize: 11,
                          ),
                        );
                      },
                    ),
                  ),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 30,
                      interval: 50,
                      getTitlesWidget: (value, meta) {
                        if (value != 0 && value != 50 && value != 100) {
                          return const SizedBox.shrink();
                        }

                        return Text(
                          value.toInt().toString(),
                          style: const TextStyle(
                            color: Colors.grey,
                            fontSize: 11,
                          ),
                        );
                      },
                    ),
                  ),
                ),
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    color: Colors.orange,
                    barWidth: 3,
                    isCurved: true,
                    dotData: const FlDotData(show: true),
                    belowBarData: BarAreaData(
                      show: true,
                      color: Colors.orange.withValues(alpha: 0.12),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ViolationProvider>();
    final active = provider.active;
    final history = provider.history;
    final allEvents = [...active, ...history];
    final risks = allEvents.map(_riskOf).toList();

    final total = allEvents.length;
    final resolved = history.length;
    final inProcess = active.length;
    final averageRisk = risks.isEmpty
        ? 0
        : (risks.reduce((a, b) => a + b) / risks.length).round();

    final low = risks.where((risk) => risk <= 30).length;
    final medium = risks.where((risk) => risk > 30 && risk <= 70).length;
    final high = risks.where((risk) => risk > 70).length;

    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Text('Statistics'),
        backgroundColor: Colors.orange,
      ),
      body: RefreshIndicator(
        onRefresh: provider.refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(12),
          children: [
            _statCard(
              icon: Icons.warning,
              title: 'Total violations',
              value: '$total',
              color: Colors.orange,
            ),
            const SizedBox(height: 12),
            _statCard(
              icon: Icons.pending_actions,
              title: 'In process',
              value: '$inProcess',
              color: Colors.blue,
            ),
            const SizedBox(height: 12),
            _statCard(
              icon: Icons.check_circle,
              title: 'Resolved',
              value: '$resolved',
              color: Colors.green,
            ),
            const SizedBox(height: 12),
            _statCard(
              icon: Icons.speed,
              title: 'Average risk',
              value: '$averageRisk%',
              color: Colors.red,
            ),
            const SizedBox(height: 16),
            _riskChart(risks),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Risk groups',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  _riskRow('Low', low, Colors.green),
                  _riskRow('Medium', medium, Colors.orange),
                  _riskRow('High', high, Colors.red),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
