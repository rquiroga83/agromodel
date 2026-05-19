import 'package:flutter/material.dart';
import 'screens/map_screen.dart';

void main() => runApp(const AgroPlusApp());

class AgroPlusApp extends StatelessWidget {
  const AgroPlusApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AgroPlus - Que Sembrar?',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.green[700]!),
        useMaterial3: true,
      ),
      home: const MapScreen(),
    );
  }
}
