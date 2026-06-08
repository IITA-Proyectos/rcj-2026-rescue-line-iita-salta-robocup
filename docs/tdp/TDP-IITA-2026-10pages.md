# ROBOCUPJUNIOR RESCUE LINE 2026 — TEAM DESCRIPTION PAPER

**Team Name:** RescueBot IITA · **Robot:** Jesus · **Institution:** IITA — Instituto de Innovacion y Tecnologia Aplicada · **Country:** Argentina
**Members:** Lucio Saucedo, Benjamin Villagran, Laureano Monteros · **Mentors:** Enzo Juarez, Gustavo Viollaz · **Contact:** rescuebot.salta@gmail.com

## Abstract

RescueBot IITA is a fully autonomous RoboCupJunior Rescue Line robot built to complete the whole mission: line following, green-marker decisions, obstacle handling, rescue-zone entry, victim collection, sorting, evacuation-zone deposit and exit. It uses a dual-controller architecture: a Raspberry Pi 4B runs camera processing, high-level state decisions and AI object detection, while a Teensy 4.1 handles deterministic motor control, sensors, servos, serial parsing and safety routines. The robot combines a custom Fusion 360 3D-printed chassis, four encoder motors, a five-servo rescue mechanism, a team-designed PCB, separated power rails, a wide-angle camera, ToF and ultrasonic sensors, a BNO055 IMU and APDS9960 floor sensing. Its competitive advantage is integration: classical vision gives fast, deterministic line and marker decisions; an exported TFLite detector handles the rescue zone; and the Teensy keeps low-level movement and fail-safe behavior alive even while the Pi is under heavy vision load. For 2026 the team prioritized robustness, serviceability, documented testing and evidence-based iteration, validated against the 2026 rules (including the new LED-wall and fake-victim rules) and our own measured test log.

## 1. Introduction

### a. Team

**Lucio Saucedo — Line vision and camera processing.** Builds the Raspberry Pi line-following pipeline: camera processing, black-line tracking, green-marker detection and red/silver visual states. Owns reliable behavior on the line course before the rescue zone.

**Benjamin Villagran — RPi integration, AI and electronics.** Owns RPi↔Teensy integration, the rescue-zone AI pipeline, model training/export, TFLite deployment, anti-flash/AGCWD preprocessing, PCB documentation and power distribution.

**Laureano Monteros — 3D design, firmware and rescue mechanism.** Owns CAD/3D design, the printed structure and rescue mechanism, and the Teensy C++ firmware: motor control, sensor acquisition, serial parsing, encoder/IMU movements and claw/deposit routines.

Each member has a main area, but the final behavior depends on constant integration between vision, AI, firmware, electronics and mechanical testing.

**Figure 1: Robot evolution, first prototype to national-championship robot**

![Robot evolution 2023-2025](assets/robot-evolution-2023-2025.png)

The robot evolved from a simple first-year platform into a compact 2025 competition robot. One week before a national competition a major hardware failure forced a full rebuild in very little time; that experience made modular parts, clear wiring, PCB documentation and reliability gates design requirements for 2026 instead of optional extras.

## 2. Project Planning

### a. Overall Project Plan

The 2026 objective is a robot that completes Rescue Line *consistently*, not one that only solves isolated tasks. Requirements were derived from the 2026 rules, the rescue-zone constraints, past competition experience and the short time before the world final.

**Table 1: Requirements, competition basis and design solution**

| Requirement | Rule / challenge basis | Final solution |
|---|---|---|
| Follow line, curves, gaps, intersections | **3.3** (1–2 cm line, gaps ≤20 cm) · **3.2** (steps ≤3 mm) | Pi processes a 160×120 frame, extracts the line, sends speed/angle to the Teensy |
| Green markers and red stop line | **3.6** (25 mm green markers; 2 = dead end) · **3.3.5** (red goal strip) | LAB/HSV masks → `green_state` commands (left/right/double/stop) |
| Avoid obstacles | **3.5** (obstacles ≥15 cm) | 3× HC-SR04 + BNO055 yaw-controlled bypass turns |
| Detect rescue-zone entry | **3.9.4** (silver tape) · **3.9.5** (black exit tape) | Silver mask + APDS9960 floor confirmation → state transition |
| Search, collect and sort victims | **3.10** (4–5 cm spheres, ≤80 g; 2 silver, 1 black) · **3.9.7** (red/green deposit points) | TFLite detector + camera tracking + ToF/US walls + five-servo claw |
| Deposit into correct zone | **3.9.7a-b** (black→red, silver→green) · **5.6.6** (×1.4 multiplier) | Sort servo + deposit servo + FCL/FCR wall alignment |
| Survive 2026 LED walls and fake victims | **3.9.12** *(new)* LED lights · **3.10.5** *(new)* fake victims · **3.11** lighting | Anti-flash + AGCWD preprocessing + APDS hardware floor path |
| Stop safely, LoP recovery, be repairable | **4.2.8** (single switch) · **5.5** (LoP) · **4.4** (re-inspection) | Physical switch, UART stop byte, firmware timeouts, modular M3 prints |

Milestones were sequenced so each layer depends on the previous one (stable mechanics/electronics → line following → rescue behavior → reliability tests + documentation), because rescue cannot be tuned without a stable drivetrain and reliable serial link. Member assignment, the full timeline and the review gates (diamonds) are shown in Figure 2, including the November 2025 RoboCup qualification.

**Figure 2: Project Gantt — milestones, member assignment, review gates and RoboCup qualification**

![Detailed project Gantt with tasks, owners, review gates and RoboCup qualification milestone](assets/project-gantt-2026-detailed.png)

### b. Integration Plan

The robot is a distributed control system: the Pi makes perception and high-level decisions; the Teensy executes time-critical motion and safety. Both synchronize over a serial link.

**Figure 3: Processor, sensor and actuator integration overview**

![Simplified processor sensor and actuator integration overview](assets/system-integration-simple-2026.png)

**Table 2: Interfaces — connection, protocol and requirement met**

| Interface | Protocol / rate | Payload | Requirement supported |
|---|---|---|---|
| Camera → Pi | USB video | 160×120 line frames, 256×256 AI crops | Line, markers, rescue perception |
| Pi → Teensy | UART 115200, 50 ms timeout | 8-byte frame: speed, angle, `green_state`, silver | Perception-to-motion integration |
| Teensy → Pi | UART status byte | `0xF9` ready, `0xF1` rescue, `0xF8` rescue-done, `0xF7` evac, `0xFF` stop | Safe state transitions / recovery |
| Teensy ↔ drivebase | PWM + encoder interrupts | Effort, direction, encoder feedback | Line following, calibrated moves |
| Teensy → rescue module | Servo PWM | Grip, lift, sort, deposit | Pickup, sorting, deposit |
| Teensy ↔ nav/floor sensors | I2C, trig/echo, digital | BNO055, VL53L0X, HC-SR04, APDS9960, FCL/FCR, switch | Turns, walls, obstacles, floor, alignment, stop |

The Pi→Teensy frame is intentionally tiny — `[0xFF, speed, 0xFE, angle, 0xFD, green_state, 0xFC, silver]` — keeping the robot synchronized without a complex network stack.

## 3. Hardware

The hardware is fully custom, organized around stability on the course, serviceability between runs, and clear separation of sensing, computation, power and actuation. Figure 4 shows the power, sensor, control and serial paths: the 11.1 V 3S battery feeds the 12 V motors directly, an XL4016 supplies the 5 V compute rail, and an MP1584 supplies the 6 V servo rail.

**Figure 4: Hardware overview (power, sensor, control and serial paths)**

![Hardware overview](assets/hardware-overview-2026.png)

### a. Mechanical Design and Manufacturing

The structure was designed in Fusion 360 and printed as multiple PLA modules. Figure 5 compares side/front/top CAD views with the physical robot. The CAD envelope is **157 × 177 × 176 mm** and the robot masses **1404 g** (measured). The lower level holds the drivetrain (four 12 V encoder motors, fixed wheels + omniwheels) with battery and motors low for a stable centre of gravity on ramps and seesaws; the middle level holds electronics; the front/upper holds the camera and rescue mechanism; the rear/upper holds storage and deposit.

**Figure 5: CAD-to-built comparison (side, front, top)**

![CAD-to-built comparison of side, front and top robot views](assets/mechanical-cad-built-comparison-2026.png)

The rescue mechanism is the key subsystem: **five servos** — two grippers, one lift, one sort, one deposit. Servo Left/Right close custom-printed fingers around the ball; Servo Lift raises the closed gripper off the floor (the three front servos share one 3D-printed PLA rail, so grip width and lift height tune independently). Servo Sort routes the lifted victim into the correct storage channel; Servo Deposit releases it toward the selected side once the FCL/FCR limit switches confirm wall contact. Figure 6 shows the claw; Figure 7 shows how every submodule mounts to the PLA chassis backbone and how a victim travels claw → storage → deposit → zone.

**Figure 6: Claw mechanism — exploded view with servo labels (Fusion 360)**

![Claw mechanism exploded view with servo labels](assets/claw-exploded-servos-2026.png)

**Figure 7: Mechanical submodule interaction map — mounting interfaces and victim pathway**

![Mechanical submodule interaction map showing chassis backbone, mounting interfaces and victim pathway](assets/mechanical-interaction-map-2026.png)

The **entire structure is original team design** (chassis, motor mounts, wheel hubs, corner supports, camera arm, electronics tray, claw housing, storage channel, deposit guide) — no third-party chassis kit. Parts print in PLA (30 % infill structural / 20 % covers, 0.20 mm layers, 3 perimeters on impact zones), and every module uses M3 screws so a damaged housing, camera arm or motor mount can be reprinted and swapped in under 10 minutes — a requirement adopted after the 2025 rebuild. Three decisions make the mechanism innovative for 2026: (1) **universal grip geometry** — identical servo angles grip both black and silver spheres, no reconfiguration; (2) **sort-during-lift** — the sort channel is set as the gripper lifts, removing a sequential step; (3) **fully decoupled functions** — grip, lift, sort and deposit each have one dedicated servo, so any one can be recalibrated or replaced without affecting the rest (a direct lesson from the 2024 cage design, where grip and sort were coupled).

**Table 3: Mechanical reliability tests (criterion · result · sample · verdict)**

| Test | Criterion | Result | Sample | Verdict | Src |
|---|---|---|---|---|---|
| Straight distance | error ≤ ~2 cm (25 counts/cm) | ≈1–2 cm | repeated | PASS | T-001 |
| Turn accuracy | within ±1° (IMU) | ≈1° | repeated | PASS | T-001 |
| Victim pickup | ≥80 % captured, no drop | 8/10 | n=10 | PASS | T-005 |
| Deposit (FCL/FCR) | ≥90 % correct release | 10/10 | n=10 | PASS | T-005 |
| Full-course pickup | 3 victims, one pass | 3/3 | 1 run | PASS | T-003 |
| Ramp-up stability | no false-silver / loss | 8/10 | n=10 | PASS | T-006 |
| Seesaw / abrupt drop | recover after impact | 9/10 | n=10 | PASS | T-006 |
| Lateral ramp | hold trajectory, no tip | 0/10 | n=10 | **FAIL** | T-006 |

### b. Electronic Design and Manufacturing

The architecture centres on the Raspberry Pi 4B (vision, AI, high-level states) and Teensy 4.1 (real-time motors, sensors, servos, safety), plus a custom PCB, 3S LiPo, regulated rails, XT60, five servos, 3× HC-SR04, 2× VL53L0X, BNO055, APDS9960, buzzer, LEDs, relay and switches. Figure 8 shows the team-designed PCB layout and schematic, which make every interface explicit — power input, regulated rails, Teensy pinout, Pi UART, motor/servo outputs, I2C sensors, indicators and switches.

**Figure 8: Custom PCB layout (a) and schematic (b)**

![Main PCB layout](assets/pcb-main-layout.svg)

![Electronics schematic](assets/schematic-main.svg)

**Separated power rails (measured):** the five DFRobot SER0056 servos run on an MP1584 at **6.1 V**; the Pi and Teensy run on a separate XL4016 at **5.0 V**, so rescue-mechanism current spikes cannot load the compute supply. **PCB–chassis co-design:** the board footprint matches the chassis base and the chassis was modeled directly from the board outline and hole positions, so any future reprint aligns to the PCB without re-routing. **Power iteration driven by measured failure:** in 2024 a 3 A MP1584 fed the Pi and caused repeated resets under vision load; in 2025 it was replaced with an 8 A XL4016, after which no reset has been observed. The drivetrain uses 12 V 159 RPM encoder motors (calibrated 25 counts/cm vs 28.65 theoretical); IMU turns stop within ±1°; the five clutch servos use a 540–2390 µs / 274° range, and the firmware never commands all five together (at most two), so five-servo stall is only a conservative electrical upper bound.

**Table 4: Key Teensy interfaces (grouped)**

| Subsystem | Pins / bus | Source |
|---|---|---|
| Pi UART | `Serial5` (115200) | `main.cpp` |
| 4 motors | PWM/DIR/ENC (e.g. 29/28/27 …) | `main.cpp` |
| 5 servos | sort 23, left 14, right 15, lift 22, deposit 12 | `main.cpp`,`claw.cpp` |
| 3 HC-SR04 | trig/echo pairs | `main.cpp` |
| BNO055 / APDS9960 / 2× VL53L0X | I2C (`0x28`…) | `main.cpp` |
| FCL/FCR · switch · buzzer/LED · relay | 40/41 · 32 · 31/30 · 0 | `main.cpp` |

**Table 5: Electronic reliability tests (criterion · result · verdict)**

| Test | Criterion | Result | Verdict | Src |
|---|---|---|---|---|
| Battery start / idle | full charge / no drop | 12.6 V / 12.6→12.5 V | PASS | T-001 |
| Continuous autonomy | long session | 1 h to 10.5 V | PASS | T-001 |
| High-stress drop | no reset under load | 1.4 V drop, no reset | PASS | T-001 |
| Servo / compute rails | separate ~6 V / ~5 V | 6.1 V / 5.0 V | PASS | T-007 |
| Rail isolation | no cross-reset | confirmed separate | PASS | T-007 |
| RPi↔Teensy UART | frame counter rising | `frames_sent` 1→2204 | PASS | T-002 |
| Boot / stop-switch | init OK / motors stop | OK / OK | PASS | bench |

## 4. Software

### a. General Software Architecture

The software is split by timing: the Pi runs Python (OpenCV, NumPy, serial, camera threads, the exported detector); the Teensy runs Arduino/C++ (motor, sensor, serial and claw control). Figure 9 shows the full data flow — Roboflow dataset → YOLOv8n training → TFLite model on the Pi; a camera thread feeds 160×120 frames to the classical Line Process and 256×256 crops to the AI Detection Process; `Main.py` selects line/rescue/deposit/evacuation mode and builds compact UART commands; the Teensy's serial state machine validates payloads and the controller selects safety-priority actions with motion timeouts; an APDS9960 "critical floor confirmation" block reduces camera-only false positives.

**Figure 9: Overall software architecture and data flow**

![Main process overall software architecture](assets/main-process-flow-2026.png)

**Line mode (Figure 10)** runs classical vision at 160×120 (black-line steering angle, green markers, red/silver redundancy) and a Teensy priority tree: switch-off → stop; silver/APDS → rescue; red strip → stop 10 s; obstacle <12 cm → bypass; single/double green → turn / 180°; ramp by pitch → adjust speed; else normal steering. **Rescue mode (Figure 11)** is four stages: initialize the TFLite detector; search + pickup (CentroidTracker selects a target, the robot approaches and the claw collects until `ball_counter == 3`); deposit (AI detects green then red zones, deposits with FCL/FCR alignment); and exit (APDS confirms the black exit line or reverses on silver, else wall-follows out).

**Figure 10: Line following — RPi vision pipeline and Teensy decision tree**

![Line following Teensy decision flow and RPi vision pipeline](assets/line-following-flow-2026.png)

**Figure 11: Rescue zone — search, pickup, deposit and exit flow**

![Rescue zone victim search deposit and exit flow](assets/rescue-zone-flow-2026.png)

Confirmed production parameters: 160×120 line vision (140° camera); 256×256 detector every 3 frames; confidence 45–60 % by class; UART 115200 / 8-byte / 50 ms. Firmware guards include UART payload validation, `runDistance()`/`runAngle()` timeouts, serial-buffer draining, a TFLite warmup and visible init failures, so a sensor fault fails visibly instead of trapping the robot.

### b. Innovative Solutions

**1 — Hybrid classical + AI perception.** Classical vision handles line following at full speed (deterministic, easy to debug); AI is reserved for the rescue zone, where masks fail under variable lighting — so the robot never pays AI cost on the line. Because 2026 walls may be any non-semantic colour (committee notes include bright orange), and a fluorescent-orange wall was confusing the detector with the red zone, the dataset was expanded: **6256 images / 9521 annotations / 4 classes** (`plateado` 3029, `negro` 2488, `verde_alto` 2147, `rojo_alto` 1857), annotating white/brown/orange/yellow/gray walls plus flashlight-stress cases. Trained from `yolov8n.pt`, 100 epochs at 256×256 with aggressive saturation/brightness augmentation but low hue shift (so red/green are not swapped). Kaggle validation: **P 0.971 · R 0.929 · mAP50 0.932 · mAP50-95 0.767** (per-class mAP50: negro 0.995, plateado 0.904, rojo 0.929, verde 0.898).

**2 — TFLite migration with embedded NMS and global warmup.** The ONNX runtime was the rescue-mode bottleneck on the Pi 4B. Migrating to a TFLite interpreter with NMS embedded in the model (`nms=True`) and the XNNPack/NEON delegate gave a measured jump, and a startup warmup removes the first-inference spike.

| Configuration | FPS (Pi 4B) | | Warmup | First inf. | Avg |
|---|---:|---|---|---:|---:|
| ONNX + ultralytics | ~7 | | Without | 177.7 ms | 38.7 ms |
| TFLite + NMS | ~18 (**+157 %**) | | With | 67.0 ms | 50.6 ms |

`DETECT_EVERY=3` with a CentroidTracker keeps target continuity between inferences.

**Figure 12: Measured FPS — ONNX (7.14) vs TFLite + AGCWD (18.10) on the Pi 4B**

![ONNX FPS 7.14](assets/fps-onnx-7fps.jpg)

![TFLite FPS 18.10 with AGCWD](assets/fps-tflite-18fps.jpg)

**3 — Anti-flash + AGCWD preprocessing for the 2026 LED-wall rule.** LED glare creates over- and under-exposed regions in one frame, defeating fixed thresholds. `anti_flash_preprocess()` targets glare pixels (HSV `V≥215`, `S≤60`) and compresses them (`V_out = 215 + (V_in−215)×0.45`) under a soft mask, removing the histogram spike before AGCWD. **AGCWD** (Adaptive Gamma Correction with Weighting Distribution, Huang et al., IEEE TIP 2013) computes a per-intensity gamma from the frame histogram (`LUT[i] = 255·(i/255)^(1−w_cdf[i])`), correcting dark pixels aggressively and leaving bright ones nearly unchanged (blended 30/70 when already well-lit). It costs ~1–2 ms/frame via `cv2.LUT`, beats fixed gamma (no intra-frame adaptation) and CLAHE (amplifies dark-region noise) and needs no per-environment tuning. T-004 documents the regression that justified it: AGCWD-only produced deposit-zone false positives; anti-flash + AGCWD + the 100-epoch model removed them under strong glare.

**4 — Reliability over premium components.** Instead of a Coral USB + Pi 5, the team reached ~18 FPS on a Pi 4B through runtime choice, embedded NMS and frame-skip tracking — no AI accelerator. A Coral failure mid-run would be unrecoverable; a software regression can be rolled back. The same philosophy drives the binary UART protocol and firmware timeout guards: fail visibly and recover, not silently.

## 5. Performance Evaluation

The team adds challenges to the test course without removing earlier ones, so a new fix cannot silently break a previous task. Tests T-001…T-008 are recorded in `testing/TEST_LOG.md`; key results are below.

**Table 6: Physical, service and functional measurements (T-001…T-008)**

| Measurement | Result | Meaning |
|---|---|---|
| Line-following loop | 91.33 FPS (30 s service run) | Full pipeline incl. camera, masks, UART |
| Rescue/deposit AI loop | 22.25–22.40 FPS | TFLite + anti-flash/AGCWD + tracking |
| Distance / turn accuracy | ≈1–2 cm / ≈1° | 25 counts/cm + IMU tolerance met |
| Pickup / deposit sample | 8/10 / 10/10 | Pickup miss = reflective-tape proxy artifact |
| Full-course completion | 1 complete recorded run (video) | Exit-search fixed; previous 0/5 was isolated to exit nav |
| Ramp-up / seesaw | 8/10 / 9/10 | After APDS+LED silver fix; seesaw recovers |
| Lateral ramp | 0/10 | Known open weakness |
| Power: runtime / stress | 1 h to 10.5 V / 1.4 V drop, no reset | Survives long + high-load sessions |
| Flashlight + colored walls | black, red zone, silver reliable; green slowest (+~20 s) | Deployed TFLite model holds under glare |

The analysis points to specific modules and how each was fixed: **RPi resets** under vision load → root cause undersized MP1584 → replaced with XL4016 (no reset since); **false silver on up-ramps** → added APDS9960 + high-brightness LED confirmation → 8/10; **orange wall confused with red zone** → dataset expansion + retrain; **deposit-zone false positives** → anti-flash + AGCWD + 100-epoch model (T-004); **evacuation exit 0/5** → exit-search correction → one complete run validated on video. Two honest open items remain: the **lateral ramp (0/10)** and converting the single full-course run into a repeated success rate before competition.

## 6. Conclusion

RescueBot IITA was developed as a complete system, not a collection of parts: the custom PLA chassis, PCB-centred electronics, dual-controller architecture, hybrid classical/AI vision, encoded UART protocol and five-servo rescue mechanism all serve one goal — reliable completion of Rescue Line. The measured evidence (Table 6 and the T-001…T-008 log) covers FPS, power autonomy and rail separation, distance/turn accuracy, pickup/deposit rates, ramp/seesaw behavior, flashlight robustness and a full recorded run including the evacuation exit. The strongest lesson is that integration and evidence matter as much as individual features: every major design choice is tied to a requirement, an interface, a test, or a failure that drove the next iteration — and that traceability is what the team carries into RoboCup 2026.

## Appendix (external links only — not scored)

- Hardware/CAD: `hardware/mechanical/_legacy/CAD/` · `hardware/electronics/PCB_Main/` · power-tree `hardware/electronics/power-tree/README.md`
- Software: `software/raspberry/final_rpi/Main.py` · `software/teensy/firmware/src/main.cpp` · libs `drivebase/`, `claw/`
- Evidence: `testing/TEST_LOG.md` · `docs/tdp/code-reliability-evidence-2026.md` · `docs/tdp/roboflow-dataset-status-2026-05-23.md`
- **Full-course run video:** *(add link before submission)*

## References

- RoboCupJunior Rescue documents: https://rescue.rcj.cloud/documents
- RoboCupJunior Rescue Line: https://junior.robocup.org/rcj-rescue-line/
- 2026 RCJ Rescue Draft Rules: https://junior.forum.robocup.org/t/2026-rcj-rescue-draft-rules/5108
- Huang, Cheng, Chiu, "Efficient Contrast Enhancement Using Adaptive Gamma Correction With Weighting Distribution," IEEE TIP, 2013. DOI: 10.1109/TIP.2012.2226047
