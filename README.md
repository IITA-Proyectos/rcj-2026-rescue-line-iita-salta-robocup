# 🤖 IITA Salta – RCJ 2026 Rescue Line

> [!CAUTION]
> ### 🚨 PLAN DE ACCIÓN DE AUDITORÍA (URGENTE)
> Se han detectado **Bugs Críticos P0** que pueden comprometer la integridad del robot. 
> **Revisar inmediatamente el [AUDIT-ACTION-PLAN.md](AUDIT-ACTION-PLAN.md)** para conocer las tareas de resolución prioritaria.

**Repositorio de ingeniería del equipo IITA Salta para RoboCup Junior 2026 – Rescue Line**

[![ICRS](https://img.shields.io/badge/ICRS-v1.1%20L2-blue)]() [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Equipo

| Rol | Nombre |
|---|---|
| Director | Gustavo Viollaz |
| Mentor | Enzo Juarez |
| Electrónica + Python | Benjamín Villagrán |
| Python + Raspberry Pi | Lucio Saucedo |
| C++ + Teensy | Laureano Monteros |

**Institución:** Instituto de Innovación y Tecnología Aplicada (IITA), Salta, Argentina

## Estructura del Repositorio

```
.
├── software/
│   ├── teensy/firmware/      # Firmware Teensy 4.1 (PlatformIO)
│   │   ├── src/              # Código fuente principal
│   │   ├── lib/              # Librerías (PID, drivebase, claw, sensores)
│   │   └── test/             # Tests de hardware y sensores
│   └── raspberry/            # Software Raspberry Pi (visión, IA, serial)
├── hardware/
│   ├── electronics/          # PCB, esquemáticos, BOM
│   ├── mechanical/           # CAD, STL, diseño mecánico
│   └── bom/                  # Lista de materiales general
├── docs/
│   ├── es/                   # Documentación en español (fuente)
│   └── en/                   # Documentación en inglés (auto-generada)
├── testing/                  # Evidencia de pruebas
├── journal/                  # Bitácora de ingeniería
├── research/                 # Investigación y benchmarks
├── competition/              # Reglas y material de competencia
├── archive/                  # Backups y código legacy
└── project/                  # Backlog y gestión de proyecto
```

## Robot

El robot utiliza una arquitectura de doble procesador:

- **Teensy 4.1**: Control de motores (PID), sensores (BNO055, VL53L0X, APDS9960, ultrasonidos), servos del claw, y lógica de estados.
- **Raspberry Pi 4B**: Visión por computadora (OpenCV), detección de objetos (YOLOv8 + ONNX Runtime), y comunicación serial con la Teensy.

Documentación técnica clave:

- [Protocolo de comunicación RPi ↔ Teensy](docs/es/comunicacion-rpi-teensy.md)
- [Pipeline de visión + YOLO](docs/es/yolo-raspberry.md)
- [Librerías del firmware](docs/es/librerias-firmware.md)

## Dependencias Raspberry Pi

```bash
pip install -r software/raspberry/requirements.txt
```

## Compilar firmware Teensy

Requiere [PlatformIO](https://platformio.org/).
requiere descargar https://www.pjrc.com/teensy/loader_win10.html

```bash
cd software/teensy/firmware
pio run
pio run --target upload
```

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para las reglas de commits, branches y PRs.

## Licencia

MIT License – ver [LICENSE](LICENSE)

---

> Repositorio migrado desde [RCJ-RescueLine-RoboCupJunior2026-IITA-SALTA](https://github.com/IITA-Proyectos/RCJ-RescueLine-RoboCupJunior2026-IITA-SALTA) (archivado). Estructura según ICRS v1.1 L2.
