# Code reliability evidence - 2026 TDP

Source files:

- `software/raspberry/final_rpi/Main.py`
- `software/teensy/firmware/src/main.cpp`
- `software/teensy/firmware/src/priority_fix_flags.h`

Purpose: summarize code-level reliability mechanisms that support the TDP claims. These are not physical performance measurements; they are confirmed implementation details from the current code.

## Raspberry Pi vision and AI reliability

| Mechanism | Evidence | Why it matters |
|---|---|---|
| UART contract and sync bytes | `Main.py:20-39`, `Main.py:100-110` | The RPi sends a compact 8-byte command frame with fixed sync bytes and payload ranges. |
| Serial timeout | `Main.py:39`, `Main.py:69` | The RPi UART uses 50 ms read/write timeout instead of blocking indefinitely. |
| TFLite global interpreter | `Main.py:264-288` | The model is initialized once, outside the rescue loop. |
| TFLite warmup | `Main.py:290-299` | A 256 x 256 black dummy image is invoked before the run, reducing first-inference latency spikes. |
| Anti-flash preprocessing | `Main.py:229-246`, `Main.py:259-261`, `Main.py:479-481` | Saturated low-saturation LED highlights are compressed before AGCWD so the histogram is not dominated by white flash regions. |
| AGCWD stabilization | `Main.py:203-220` | Adaptive gamma correction is applied with a high-brightness blend to avoid over-processing already bright frames. |
| Detection cadence | `Main.py:325`, `Main.py:476-484` | AI inference runs every 3 frames while intermediate frames keep enhancement/tracking continuity. |
| Centroid tracking | `Main.py:354-442`, `Main.py:592` | The tracker maintains object continuity between detection frames and drops lost objects after `max_lost=8`. |
| Rescue serial monitor | `Main.py:561-585` | A background thread watches Teensy state bytes during rescue so stop/boot/evacuation events can interrupt behavior. |
| Line-mode serial drain | `Main.py:881-890` | The line loop drains the serial buffer with `while ser.in_waiting > 0`, preventing stale ACKs from building up. |

## Teensy firmware reliability

| Mechanism | Evidence | Why it matters |
|---|---|---|
| Priority fix master flag | `priority_fix_flags.h:5` | All priority reliability fixes are enabled through a single compile-time master switch. |
| UART frame contract | `main.cpp:61-73` | Teensy documents the same 8-byte protocol and payload limits as the RPi. |
| UART payload validation | `main.cpp:848-890` | Out-of-range speed, angle, task and silver payloads are rejected. |
| Motion background service | `main.cpp:951-955`, `main.cpp:1061-1073`, `main.cpp:1095-1105`, `main.cpp:1128-1138` | The Teensy continues servicing serial/claw tasks while motion functions are running. |
| `runDistance()` timeout | `main.cpp:235-242`, `main.cpp:1049-1055`, `main.cpp:1089` | Encoder-based movement cannot loop forever if a motor stalls or encoder count is not reached. |
| `runAngle()` timeout | `main.cpp:245-253`, `main.cpp:939-959` | IMU turn routines cannot loop forever if yaw does not converge. |
| Physical switch stop path | `main.cpp:961-965`, `main.cpp:1081-1084`, `main.cpp:1113-1115` | Switch-off writes stop byte `255` and exits motion routines. |
| APDS non-blocking/fresh timeout | `main.cpp:625-662` | Color sensing has polling/integration timing and fresh-read timeout while still servicing serial. |
| ToF timeout | `main.cpp:1370-1376` | Both VL53L0X sensors have 500 ms timeout. |
| Sensor init visibility | `main.cpp:1323-1336` | BNO055 and APDS init failures are surfaced instead of silently ignored. |
| Boot handshake | `main.cpp:1382-1385` | Teensy sends 20 boot bytes (`0xFA`) spaced 100 ms apart so the RPi can detect reset/boot state. |

## TDP-safe claim

The robot reliability strategy is implemented in code, not only described in prose: the Raspberry Pi has serial timeouts, model warmup, anti-flash/AGCWD preprocessing, tracking across skipped detections, and serial monitoring; the Teensy has UART range validation, motion timeouts, background task servicing during motion, sensor timeouts, and visible stop/boot behavior. Physical testing must still validate the real-world effect of these safeguards.
