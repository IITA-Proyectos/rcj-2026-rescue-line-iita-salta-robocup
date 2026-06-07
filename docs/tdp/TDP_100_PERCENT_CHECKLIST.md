# TDP 100% checklist - RescueBot IITA 2026

This checklist is for the final pass before exporting the RoboCupJunior Rescue Line 2026 TDP PDF. It separates the remaining work into items that are required for a top-score document, items that improve judge confidence, and optional polish.

## Current strong points already covered

- [x] Requirements mapped to competition constraints.
- [x] Project timeline and Gantt evidence.
- [x] Integration plan with RPi + Teensy split.
- [x] Custom PCB, schematic and power tree documented.
- [x] Software architecture diagrams added.
- [x] AI innovation documented: TFLite, embedded NMS, warmup, AGCWD, anti-flash, dataset expansion and 100-epoch training.
- [x] Code-derived values extracted into `TEST_LOG_AUTO.md`.
- [x] Physical testing entered in `TEST_LOG.md`: runtime, FPS, distance, angle, pickup, deposit, ramp, seesaw, flashlight, colored walls and regression fix.
- [x] Rail voltages documented: MP1584 servo rail measured at 6.1 V, XL4016 Raspberry Pi + Teensy rail measured at 5.0 V, normal firmware sequence uses 1-2 servos per phase.
- [x] Gantt image exists physically in `docs/tdp/assets/project-gantt-2026.png`.
- [x] Teensy pinout and sensor placement map added as Table 6b.
- [x] Final CAD envelope added to the TDP: 157.189 mm length x 176.913 mm width x 176.239 mm height.
- [x] Dimensioned CAD-envelope drawing added as Figure 4a, covering top/front/side inspection dimensions.
- [x] Final robot mass added to the TDP: 1404 g.
- [x] AI evidence records dataset expansion, YOLOv8n training, 100 epochs, 256 x 256 px, augmentation strategy, validation metrics, TFLite deployment and regression re-test.
- [x] Final full-course exit retest recorded in T-008 with video evidence.

## Must fix or prove for a realistic 100%

- [x] **Evacuation exit search / full course.**
  - Previous evidence: full course was 0/5 because exit search from rescue was not navigating correctly.
  - Current evidence: T-008 closes the blocker with a complete recorded run showing line + rescue + deposit + exit.
  - Optional next step: repeat 3-5 full courses if the team wants a statistical completion rate instead of single-video proof.

- [ ] **Final PDF export check.**
  - Use the official RoboCupJunior TDP template.
  - Confirm every figure renders in the PDF.
  - Confirm no local file paths appear.
  - Confirm figure numbers do not conflict.
  - Confirm the PDF is concise and readable.

- [x] **Mechanical mass and final labeled robot figure.**
  - [x] Add final robot length x width x height.
  - [x] Add dimensioned envelope drawing for the CAD assembly.
  - [x] Add final robot mass.
  - [x] Add CAD/real comparison and labeled claw/mechanism figures.

- [x] **AI training and inference diagram.**
  - Main process and AI evidence show data collection, YOLOv8n training, TFLite deployment, anti-flash, AGCWD, thresholds and tracker behavior.
  - Dataset and T-004 document the iteration loop from false positives to retraining/retest.

- [x] **3D printing parameters.**
  - Table 4b records PLA, infill, layer height, wall count, nozzle size, print orientation and repair strategy.

## High-value evidence to add if the robot is available

- [x] **Sensor placement evidence.**
  - Table 6b now documents the pinout and physical use.
  - Figure 2 and Figure 3 provide the visual hardware/integration overview; a dedicated labeled top-view remains optional polish.

- [ ] **Servo rail sag measurement during motion.**
  - Static MP1584 servo rail measurement is already recorded as 6.1 V.
  - Measure MP1584 servo rail during normal pickup.
  - Measure MP1584 servo rail during the hardest safe servo sequence.
  - Expected TDP value: `6.1 V static, minimum measured X.XX V during pickup`.

- [x] **5 V logic/compute rail measurement.**
  - XL4016 rail measured at 5.0 V for Raspberry Pi/Teensy.
- [x] **5 V logic/compute rail under integrated load.**
  - XL4016 rail is reported at 5.0 V and no RPi resets were observed after the XL4016 compute-rail change.
  - Optional precision upgrade: record minimum voltage during camera + TFLite + Teensy active with a multimeter.

- [ ] **Pickup/deposit larger sample.**
  - Current: pickup 8/10, deposit 10/10.
  - Better: pickup 16/20 or higher, deposit 20/20 or close.
  - Note if failures are caused by non-representative reflective tape instead of real victims.

- [ ] **Lateral ramp retest or limitation.**
  - Current: 0/10.
  - Best: tune and retest.
  - If not fixed, keep it as an honest stress-test limitation, not as normal ramp performance.

## TDP wording checks

- [x] Do not claim the robot completed full course until a retest proves it.
- [x] Keep the previous full-course 0/5 limitation isolated to evacuation exit search, then close it with T-008.
- [x] Keep the servo current calculation as conservative design analysis, not measured current.
- [x] State that SER0056 servos include clutch protection and 5 s blockage shutoff.
- [x] State that pickup/deposit firmware normally moves only 1-2 mechanism servos per phase.
- [x] Keep all numbers tied to sources: code, TEST_LOG, component specs, or measured tests.

## Final score risk assessment

The main technical blockers are now closed in the TDP evidence: a dimensioned CAD envelope, mass, print parameters, rails, dataset/model evidence, physical tests, and a recorded full-course exit retest are all documented.

The only required item left for the final submission workflow is the PDF/template export check. Optional confidence upgrades are larger pickup/deposit samples, repeated full-course statistics and servo-rail sag measurements during pickup.
