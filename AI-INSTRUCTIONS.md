# Instrucciones para Asistentes de IA

Este repositorio sigue el estándar ICRS v1.1 L2 (IITA Competition Repository Standard).

## Estructura

- `software/teensy/firmware/`: Proyecto PlatformIO para Teensy 4.1
- `software/raspberry/`: Código Python para Raspberry Pi 4B
- `hardware/`: Electrónica (PCB, esquemáticos) y mecánica (CAD, STL)
- `docs/es/`: Documentación fuente en español
- `docs/en/`: Mirror auto-generado en inglés (NO EDITAR)

## Reglas

1. Siempre vincular cambios a un Issue.
2. Usar Conventional Commits.
3. No hacer push directo a `main`.
4. Documentar en `docs/es/` (español es fuente de verdad).
5. Declarar uso de IA en los PRs.
6. Hardware versionado por revisiones (`rev-a`, `rev-b`, etc.).

## Contexto técnico

- Teensy 4.1 controla motores, sensores y servos.
- Raspberry Pi 4B corre visión (OpenCV + YOLO ONNX).
- Comunicación serial UART a 115200 baudios.
- Protocolo: [255, speed, 254, angle, 253, green_state, 252, silver_line]
