class Violation {
  final String eventId;
  final String name;
  final DateTime timestamp;
  final double duration;
  final int risk;
  final int zone;
  final String image;
  final String status;

  const Violation({
    required this.eventId,
    required this.name,
    required this.timestamp,
    required this.duration,
    required this.risk,
    required this.zone,
    required this.image,
    required this.status,
  });

  factory Violation.fromJson(Map<String, dynamic> json) {
    return Violation(
      eventId: json['event_id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Unknown',
      timestamp: DateTime.tryParse(json['time']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      duration: ((json['duration'] ?? 0) as num).toDouble(),
      risk: ((json['risk'] ?? 0) as num).round(),
      zone: ((json['zone'] ?? 0) as num).round(),
      image: json['image']?.toString() ?? '',
      status: json['status']?.toString() ?? 'In Process',
    );
  }
}
