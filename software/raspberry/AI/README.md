# AI model evolution — RescueBot IITA 2026

This folder documents the **evolution of our rescue-zone detector**, from the first national-championship baseline (2025) to the final model deployed at RoboCup 2026 Incheon. Each subfolder contains the trained model and the dataset version used at that step, so other teams can trace exactly what changed and why.

## Quick map

| # | Folder | Date | Format | Dataset size (train / val / test) | Classes | Why we changed it |
|---|---|---|---|---|---|---|
| 01 | `01-roboliga-baseline-2025-09/` | 2025-09-09 | YOLOv8 `.pt` + `.onnx` | 1009 / 55 / 39 | 4 (`boxgreen`, `boxred`, `negro`, `plateado`) | First baseline. Detected balls + **low** deposit boxes used in the Argentinian *Roboliga* rules. |
| 02 | `02-deposito-alto-first-2025-11/` | 2025-11-20 | YOLOv8 `.onnx` | 1463 / 55 / 39 | 4 (current set: `negro`, `plateado`, `verde_alto`, `rojo_alto`) | RoboCup 2026 rules introduced **elevated colored deposit zones**. We replaced the low boxes with the high ones — the four current classes start here. |
| 03 | `03-zonas-completo-2025-11/` | 2025-11-23 | YOLOv8 `.onnx` | 1763 / 224 / 222 | 4 | False positives in the previous version + weak ball detection in some zones. **We also learned how to use train/val/test splits properly** — this is where the model started to behave well in simple scenarios. |
| 04 | `04-tflite-migration-2026-03/` | 2026-03-20 | TFLite (NMS embedded) + NCNN experiment + Zero-DCE int8 | (same training as 03) | 4 | **Runtime migration experiment — Innovation #2 of the TDP.** Same weights, exported to TFLite with `nms=True` so post-processing runs inside the model. Measured +157 % FPS on the Pi 4B (~7 → ~18 FPS). The NCNN folder is a parallel runtime experiment; `dcenet_int8.tflite` is a Zero-DCE illumination model used in the rescue intermediate frames on the Pi 5 path. |
| 05 | `05-final-2026-incheon/` | 2026-04-06 | **YOLOv8n TFLite** (NMS embedded) | 6256 / 224 / 222 (+ flashlight-stress and colored-wall annotations) | 4 | **Deployed model for the world final.** 100 epochs at 256×256, anti-flash + AGCWD compatible, robust against orange/yellow/brown/white/gray walls and LED flashlight stress (Rule 3.9.12). Validation: P 0.971 · R 0.929 · mAP50 0.932. |

## Iteration #1 — Roboliga baseline (2025-09-09)

The first detector was trained for the **Argentinian national championship (*Roboliga*)**, whose 2025 rules used **low colored boxes** as deposit zones (not the elevated triangles of the RoboCup 2026 rules).

- Files: `roboliga.pt` (PyTorch checkpoint), `roboliga.onnx` (exported for the on-robot runtime), `dataset-v5-rescate.zip` (Roboflow YOLOv8 export).
- Classes: `boxgreen`, `boxred`, `negro`, `plateado`.
- Dataset: 1009 train / 55 val / 39 test.
- Result: worked well at the national event but could not be reused for RoboCup once the rules changed to elevated zones.

## Iteration #2 — First elevated-zone detector (2025-11-20)

When the RoboCup 2026 rules removed the low boxes and introduced **elevated red/green deposit zones**, we trained the first detector for that new layout.

- File: `depositoalto.onnx`. Dataset: `dataset-v12-zonas-alta.zip` (1463 / 55 / 39).
- **This is the first time we used the four current classes** (`negro`, `plateado`, `verde_alto`, `rojo_alto`) — they have been kept ever since.
- Result: detected elevated zones for the first time, but the small validation split made it hard to tell how reliable the model really was.

## Iteration #3 — Bigger dataset and proper splits (2025-11-23)

- File: `zonasdepositoalta.onnx`. Dataset: `dataset-v15-sinboxes-bajas.zip` (1763 / 224 / 222).
- We grew the validation and test sets (55 → 224 val, 39 → 222 test) so the reported metrics actually meant something. **This is when we learned to use train/val/test splits properly.**
- Result: clearly better than #2. False-positive cases that broke #2 were fixed, and ball detection in tricky zones became reliable. From here on the model behaved well in simple scenarios; the remaining work was robustness under stressed lighting and unfamiliar wall colors.

## Iteration #4 — Runtime migration experiment (2026-03-20) — Innovation #2 of the TDP

We discovered that the ONNX runtime on the Raspberry Pi 4B was the **rescue-mode bottleneck**. To remove it, we re-exported the same weights to **TFLite with NMS embedded inside the model** (`nms=True`), using the XNNPack/NEON delegate.

- `yolov8n_256x256_tflite-NMS.tflite` — same weights as the ONNX models, exported to TFLite with embedded NMS.
- `dcenet_int8.tflite` — Zero-DCE illumination model used in the Pi 5 path on intermediate rescue frames (lighter alternative to AGCWD when the platform allows).
- `best_ncnn_model_experiment/` — parallel runtime experiment with NCNN (we did not deploy it; TFLite + XNNPack was faster on our Pi 4B).
- Measured improvement on the Pi 4B: ~7 FPS (ONNX + ultralytics) → ~18 FPS (TFLite + NMS). **+157 % FPS on the same hardware**, without any AI accelerator.

This is the experiment that justifies **Innovation #2** in the TDP.

## Iteration #5 — Final model for RoboCup 2026 Incheon (2026-04-06)

The deployed model for the world final. **This is the model that runs on the robot today.**

- File: `yolov8n_rescuebot_2026.tflite`.
- SHA256: `c6ee9629a80bfb8e978e6ab6c2d5762a7516ee8b55dda847d1849cd3b2ced11a`.
- Size: 12,167,144 bytes (11.60 MB).
- Input: `1 × 256 × 256 × 3` float32.
- Output: `1 × 300 × 6` float32 (300 detections × `[x, y, w, h, score, class_id]`, NMS embedded).
- Architecture: YOLOv8n, 491 tensors.
- Classes (unchanged since iteration #2): `negro`, `plateado`, `verde_alto`, `rojo_alto`.
- Training: 100 epochs at 256 × 256 from `yolov8n.pt`, AMP enabled, aggressive saturation/brightness augmentation, low hue shift (so red and green are not swapped). Anti-flash + AGCWD compatible.
- Dataset: **6256 train / 224 val / 222 test**, with white / light-brown / orange / yellow / gray wall conditions and flashlight-stress cases annotated, to handle the 2026 LED-wall rule (3.9.12).
- Kaggle validation: **P 0.971 · R 0.929 · mAP50 0.932 · mAP50-95 0.767**.
- Per-class mAP50: `negro` 0.995 · `plateado` 0.904 · `rojo_alto` 0.929 · `verde_alto` 0.898.

## How to verify any model in this folder

The repository includes `inspect_tflite.py`, a small inspector that prints the input/output shapes, the SHA256 hash and the number of tensors of a TFLite model. Run it with no arguments to inspect every `.tflite` under this folder:

```bash
python inspect_tflite.py
```

Two models with the same SHA256 are the same file under different names.

## Why we keep older iterations

We chose to keep the older models in this repository — instead of only shipping the final one — because the **path from iteration #1 to iteration #5 is the actual engineering work**. Each step has a specific reason: a rule change, a class redefinition, a split correction, a runtime migration, a dataset expansion. We hope this is useful to teams starting from scratch or trying to reproduce our results.
