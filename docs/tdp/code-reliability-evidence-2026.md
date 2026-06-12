# Code reliability evidence - 2026 TDP

Source files (verified against the repository on 2026-06-08):

- [`software/raspberry/final_rpi/Main.py`](../../software/raspberry/final_rpi/Main.py)
- [`software/teensy/firmware/src/main.cpp`](../../software/teensy/firmware/src/main.cpp)
- [`software/teensy/firmware/src/priority_fix_flags.h`](../../software/teensy/firmware/src/priority_fix_flags.h)

Purpose: summarize the code-level reliability mechanisms that support the TDP claims. These are not physical performance measurements; they are confirmed implementation details from the current code. All line ranges below were re-checked against the source on 2026-06-08 and reflect the version that is publicly visible in the repository.

## Raspberry Pi vision and AI reliability

| Mechanism | Evidence | Why it matters |
|---|---|---|
| UART contract and sync bytes | `Main.py:28-39` (constants), `Main.py:101-113` (`send_frame`) | The RPi sends a compact 8-byte command frame with fixed sync bytes (`0xFF`/`0xFE`/`0xFD`/`0xFC`) and named status bytes (`0xFA` boot, `0xF9` ready, `0xF8` rescue-done, `0xF7` evacuation, `0xFF` stop, `0xF1` rescue). |
| Serial timeout | `Main.py:39` (`SERIAL_TIMEOUT_S = 0.05`), `Main.py:70` (port opened with read+write timeout) | The RPi UART uses a 50 ms read/write timeout instead of blocking indefinitely. |
| TFLite global interpreter | `Main.py:265-289` | The model is initialized once at module scope, outside the rescue loop, with a `tflite_runtime` → `tensorflow.lite` fallback. |
| TFLite warmup | `Main.py:291-300` | A 256×256 zero-filled dummy image is invoked before the run, reducing the first-inference latency spike (177 ms → 67 ms on the Pi 4B). |
| AGCWD stabilization | `Main.py:204-220` (`agcwd()`), `Main.py:262` (chained after anti-flash), `Main.py:482` (rescue intermediate frames) | Adaptive Gamma Correction with Weighting Distribution applied on a per-frame histogram; bright frames receive a softer blend to avoid over-processing. |
| Anti-flash preprocessing | `Main.py:232-261` (`anti_flash_preprocess()`), `Main.py:481` (rescue inference frame) | Saturated low-saturation LED highlights (HSV `V≥215`, `S≤60`) are compressed by factor 0.45 before AGCWD so the histogram is not dominated by white flash regions. |
| Detection cadence | `Main.py:326` (`DETECT_EVERY = 3`), `Main.py:477-485` | AI inference runs every 3 frames while intermediate frames keep enhancement and tracking continuity, letting the robot move smoothly instead of frame-by-frame. |
| Centroid tracking | `Main.py:355-440` (`CentroidTracker`), `Main.py:593` (`max_lost=8`) | The tracker maintains object continuity between detection frames and drops lost objects after `max_lost=8` missed detections. |
| Rescue serial monitor | `Main.py:563-585` (`serial_monitor_local` + `threading.Thread(daemon=True)`) | A background daemon thread watches Teensy state bytes during rescue so stop/boot/evacuation events can interrupt behavior without polling. |
| Line-mode serial drain | `Main.py:887-892` (`while ser.in_waiting > 0`) | The line loop drains the serial buffer with a `while` (not an `if`) so 30 ACKs/s do not accumulate when the vision loop takes ~25 ms; the `break` on `0xFF` exits immediately when the state changes. |
| Camera-thread join timeouts on shutdown | `Main.py:734-736` | Worker threads are joined with bounded timeouts so a stuck capture/inference cannot block program exit. |

## Teensy firmware reliability

| Mechanism | Evidence | Why it matters |
|---|---|---|
| Priority fix master flag and per-fix flags | `priority_fix_flags.h` (12 individual flags + `kEnableAllPriorityFixes` master) | All priority reliability fixes can be enabled individually or together at compile time, so each safeguard is traceable to a specific audit issue. |
| UART frame contract | `main.cpp:62-74` | The Teensy documents the same 8-byte protocol as the RPi and declares payload limits (`SERIAL_MAX_SPEED=100`, `_ANGLE=180`, `_GREEN_STATE=20`, `_SILVER_LINE=1`). |
| UART payload validation | `main.cpp:816-820` (`serialPayloadOutOfRange()`), `main.cpp:850-895` (`serialEvent5`) | Out-of-range speed, angle, task and silver_line payloads are rejected without affecting motion (Issue #74 fix). |
| Background serial servicing during motion | `main.cpp:232-233`, `main.cpp:661`, `main.cpp:918`, `main.cpp:958` (calls to `serialEvent5()`/`actualizarRescate()`/`claw.update()` inside motion loops) | The Teensy keeps servicing the serial buffer and the non-blocking claw/rescue state machines while `runDistance()`/`runAngle()` are executing (Issue #59/#63 fix). |
| `runDistance()` timeout | `main.cpp:236-244` (`computeRunDistanceTimeoutMs()`), `main.cpp:1048-1055` (timeout applied) | Encoder-based movement cannot loop forever if a motor stalls or the encoder count is not reached; the timeout is computed from speed and distance with a 50 % safety margin + 500 ms. |
| `runAngle()` timeout | `main.cpp:246-253` (`computeRunAngleTimeoutMs()`), `main.cpp:937-944` (timeout applied) | IMU turn routines cannot loop forever if yaw does not converge (Issue #112 fix). |
| Physical switch / stop byte path | `main.cpp:930`, `:968`, `:1086`, `:1118`, `:1423` (`Serial5.write(255)`), `main.cpp:1449` (`digitalRead(SWITCH) == 0`) | Switch-off writes the stop byte `0xFF` (255) and exits motion routines so the referee always has a single deterministic stop path. |
| APDS9960 non-blocking fresh-read | `main.cpp:650` (`get_color_fresh()`), `main.cpp:1337` (`apds.begin()` check) | Color sensing has its own polling/integration timing and a fresh-read timeout, and the init result is captured in `color_sensor_ok`. |
| VL53L0X ToF timeout | `main.cpp:1378`, `main.cpp:1382` (`setTimeout(500)`) | Both VL53L0X sensors have a 500 ms timeout so a stalled I2C transaction cannot block the loop. |
| Sensor init visibility | `main.cpp:1237`/`1330` (`bno.begin()` checked), `main.cpp:1337` (`apds.begin()` captured) | BNO055 and APDS9960 init failures are surfaced as flags instead of silently ignored (Issue #62 fix). |
| Boot handshake | `main.cpp:1391` (`Serial5.write(0xFA)`) | The Teensy emits `0xFA` boot bytes so the RPi can detect a Teensy reset and re-enter the safe waiting state. |
| Serial telemetry | `main.cpp:1146`, `:1471` (`Serial5.write(249)` "ready" pings), counters elsewhere | Periodic status bytes confirm liveness, allowing the RPi to detect a hung firmware (Issue #75). |

## Active reliability fixes (compile-time flags)

`priority_fix_flags.h` currently enables (`true`) these 11 reliability fixes:

- `kFixIssue57RescueWallTurnDirection`
- `kFixIssue58Case12ControlFlow`
- `kFixIssue59ServiceStateMachinesDuringMotion`
- `kFixIssue60RunDistanceTimeout`
- `kFixIssue61ColorSensorTimeout`
- `kFixIssue62VisibleSensorInitFailures`
- `kFixIssue67InitializeMotorPulseCount`
- `kFixIssue74ValidateSerialPayloads`
- `kFixIssue75SerialTelemetry`
- `kFixIssue76DocumentSerialProtocol`
- `kFixIssue112RunAngleTimeout`

(`kFixIssue63KeepSerialDuringMotions` is currently `false` because Issue #59 supersedes it.)

## TDP-safe claim

The robot reliability strategy is implemented in code, not only described in prose: the Raspberry Pi has a 50 ms serial timeout, a background serial-monitor thread, a global TFLite warmup, anti-flash + AGCWD preprocessing, and a `while`-based serial drain in the line loop. The Teensy has UART range validation, computed `runDistance()`/`runAngle()` timeouts, sensor timeouts and visible init failures, a deterministic `0xFF` stop path on switch-off, and a `0xFA` boot handshake. Physical testing in [`testing/TEST_LOG.md`](../../testing/TEST_LOG.md) (T-001…T-008) validates the real-world effect of these safeguards.
