# Roboflow dataset status - 2026-05-23

Source: team-provided Roboflow dataset snapshot and annotation status.

Purpose: evidence for the TDP claim that the rescue detector is being adapted to the 2026 evacuation-zone wall color variability.

## Competition-driven dataset risk

RoboCupJunior Rescue Line 2026 allows evacuation-zone walls to use colors beyond the neutral wall colors used by many previous fields. The team observed that a fluorescent orange wall could be confused with the red deposit zone, causing incorrect behavior when depositing black victims. This is treated as a dataset distribution problem, not a firmware bug: the previous model had not learned enough examples where deposit-zone colors and wall colors must be separated.

## Wall color coverage

| Wall color / scenario | Recorded | Annotated | Status |
|---|---|---|---|
| White | yes | yes | complete |
| Light brown | yes | yes | complete |
| Orange | yes | yes | complete |
| Yellow | yes | yes | complete |
| Gray | yes | yes | complete |
| Green zone with black victims inside | yes | in progress | needs completion before final training |
| Dark blue | no | no | optional expansion |
| Dark violet | no | no | optional expansion |

## Current Roboflow dataset metrics

| Metric | Value |
|---|---:|
| Total images | 6256 |
| Missing annotations | 0 |
| Null examples | 711 |
| Total annotations | 9521 |
| Average annotations per image | 1.5 |
| Number of classes | 4 |
| Average image size | 0.31 MP |
| Image size range | 0.31 MP to 0.69 MP |
| Median image ratio | 640 x 480 wide |

## Class distribution

| Class | Annotations |
|---|---:|
| plateado | 3029 |
| negro | 2488 |
| verde_alto | 2147 |
| rojo_alto | 1857 |

## Training configuration used for robustness

Source: team-provided Kaggle/Ultralytics training script.

| Parameter | Value | Purpose |
|---|---:|---|
| Base model | `yolov8n.pt` | Small model suitable for Raspberry Pi deployment. |
| Epochs | 100 | Full training run for the expanded dataset. |
| Image size | 256 | Matches the deployed rescue inference size. |
| AMP | true | Faster/more efficient training. |
| `hsv_h` | 0.015 | Low hue shift to avoid confusing red/green semantic classes. |
| `hsv_s` | 0.7 | Strong saturation variation to simulate washed or saturated LED-lit colors. |
| `hsv_v` | 0.8 | Strong brightness variation to simulate light pools and backlight. |
| `degrees` | 8.0 | Slight camera/robot rotation variation. |
| `translate` | 0.1 | Position variation inside the frame. |
| `scale` | 0.5 | Object size variation for approach distance changes. |
| `shear` | 2.0 | Perspective/mechanical alignment variation. |
| `perspective` | 0.0 | Disabled to avoid unrealistic geometry. |
| `flipud` | 0.0 | Disabled because vertical flips are unrealistic for the arena. |
| `fliplr` | 0.5 | Horizontal mirroring for left/right arena variation. |
| `mosaic` | 1.0 | Mixed scenes to reduce background false positives. |
| `mixup` | 0.1 | Mild image blending for robustness. |
| `copy_paste` | 0.1 | Object copy/paste augmentation for class exposure. |
| `erasing` | 0.4 | Cutout-style occlusion to make detections robust to partial visibility. |

Observed team result: with this training configuration, black and silver victims remained distinguishable under strong flashlight-style illumination, and the high red/green deposit-zone classes were detected correctly on the recorded wall-color scenarios.

## Kaggle validation result

Source: team-provided Ultralytics validation output from `/kaggle/working/runs/detect/train2/weights/best.pt`.

Training completed 100 epochs in 0.831 hours on Kaggle with Ultralytics 8.4.35, Python 3.12.12, PyTorch 2.10.0+cu128, CUDA Tesla T4 14913 MiB. The fused model has 73 layers, 3,006,428 parameters, 0 gradients, and 8.1 GFLOPs. The stripped `best.pt` and `last.pt` weights are each 6.2 MB.

| Split / metric | Value |
|---|---:|
| Validation images | 224 |
| Validation instances | 427 |
| Overall precision Box(P) | 0.971 |
| Overall recall R | 0.929 |
| Overall mAP50 | 0.932 |
| Overall mAP50-95 | 0.767 |
| Preprocess speed | 0.0 ms/image |
| Inference speed | 0.5 ms/image |
| Postprocess speed | 3.9 ms/image |
| Fitness | 0.767 |

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 224 | 427 | 0.971 | 0.929 | 0.932 | 0.767 |
| negro | 29 | 29 | 1.000 | 0.994 | 0.995 | 0.807 |
| plateado | 122 | 214 | 0.933 | 0.939 | 0.904 | 0.654 |
| rojo_alto | 73 | 80 | 0.994 | 0.887 | 0.929 | 0.833 |
| verde_alto | 97 | 104 | 0.956 | 0.894 | 0.898 | 0.773 |

Interpretation for the TDP: the validation result supports the claim that the retrained detector separates black and silver victims and still detects high red/green deposit-zone classes after adding wall-color and lighting robustness data. Physical robot validation is still required because Kaggle validation speed is measured on a Tesla T4, not on the Raspberry Pi 4B.

## Required post-training validation

After the model branch is trained and integrated into code, validate explicitly:

- Orange wall with black victims: the model must not confuse the wall with `rojo_alto`.
- Yellow, gray, white and light-brown walls: deposit-zone detections must remain stable.
- Green zone with black victims inside: black victim detections must remain separate from the green deposit zone.
- Null examples: confirm that background-only images reduce false positives rather than hiding real detections.

## TDP-safe claim

The dataset was expanded from a narrow neutral-wall distribution to a 6256-image Roboflow dataset with 9521 annotations across the four deployed classes. The team added annotated examples for white, light-brown, orange, yellow and gray wall conditions because the 2026 rules allow non-neutral evacuation-zone walls. This directly targets a real failure case observed on a fluorescent orange wall.
