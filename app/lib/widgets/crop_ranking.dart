import 'package:flutter/material.dart';
import '../models/prediction.dart';

class CropRanking extends StatelessWidget {
  final List<CultivoRanking> ranking;
  final int top;

  const CropRanking({super.key, required this.ranking, this.top = 8});

  Color _parseHex(String hex) {
    var s = hex.replaceFirst('#', '');
    if (s.length == 6) s = 'FF$s';
    return Color(int.parse(s, radix: 16));
  }

  @override
  Widget build(BuildContext context) {
    final items = ranking.take(top).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            for (final c in items) _filaCultivo(c),
          ],
        ),
      ),
    );
  }

  Widget _filaCultivo(CultivoRanking c) {
    final pct = (c.probMedia * 100).clamp(0, 100);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 14,
                height: 14,
                decoration: BoxDecoration(
                  color: _parseHex(c.color),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(c.cultivo.replaceAll('_', ' '),
                    style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
              Text('${pct.toStringAsFixed(1)} %',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: c.probMedia.clamp(0.0, 1.0),
              minHeight: 10,
              backgroundColor: Colors.grey[200],
              valueColor: AlwaysStoppedAnimation<Color>(_parseHex(c.color)),
            ),
          ),
        ],
      ),
    );
  }
}
