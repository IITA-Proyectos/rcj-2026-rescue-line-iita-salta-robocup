# HW-01 — Auditoría de Hardware: BOM, Planos/Esquemáticos/CAD y Documentación de Evolución

> **Dominio:** Documentación de hardware (no código). Auditoría integral 2026-05-18.
> **Auditor:** subagente HW-01 (solo lectura sobre el checkout `feature/initialize-testing-log`, contenido espejado en `main`).
> **Repo:** `C:\Users\violl\rcj-2026-rescue-line-iita-salta-robocup`
> **Alcance:** ¿Existe BOM? ¿Está completa y coincide con el código/pines? ¿Hay planos / esquemáticos / PCB / CAD / STL? ¿Hay documentación de evolución (cambios_de_hardware, power tree)? ¿Decisiones de diseño documentadas? Inventario crítico vs. lo que falta, con paths concretos e impacto en el TDP (Engineering Journal — Electronics / Mechanical).
> **Regla de findings:** cada hallazgo se presenta como **TEMA A ANALIZAR** con *riesgo de no-corregir*, *riesgo de corregir* y *tiempo estimado*. No son "bugs a fixear" sino decisiones para que el coach y los alumnos prioricen.

---

## 0. TL;DR ejecutivo

La documentación de hardware del repo está **mejor que la media de un equipo junior**: hay un BOM tabulado, un esquemático 2026 redibujado, un power-tree con star-ground y datasheets resumidas, y un documento de evolución (`cambios_de_hardware.md`) con 4 propuestas de mejora muy bien argumentadas contra el reglamento 2026. **Eso es material valioso y puntúa.**

Pero hay un problema estructural grave para un TDP de mundial: **las tres representaciones del hardware no coinciden entre sí ni con la realidad del robot.**

1. **Robot real + firmware** (`main.cpp`): IMU **BNO055**, relé en **pin 0**, sin ESP32 / sin finales de carrera / sin pin de conductividad.
2. **Esquemático PDF 2026** (`ROBOCUP.SHEET.pdf`, fechado 2026-03-08): BNO055 **+ ESP32-MINI + 2×LED-12V + relé KY019A** → dibuja el estado **futuro/propuesto**, no el actual.
3. **PCB editable** (`PCB.json`): es **byte-equivalente al board de Roboliga 2024**, todavía con **MPU6050** y sin ninguna de las mejoras. No se puede re-fabricar el board real desde el repo.

Y el **BOM oficial** (`hardware/electronics/PCB_Main/README.md`) **omite componentes que el robot sí tiene** (driver de motores, relé, regulador RPi, conector de potencia de motores) y **lista cosas que no están en el board** (INA219, según el power-tree).

Además: **`hardware/bom/` está vacío** (solo `.gitkeep`) — el BOM real vive escondido dentro de `electronics/PCB_Main/`. Y **no existe ningún archivo CAD/STL/STEP 2026**: todo el mecánico está en `_legacy/` (Roboliga 2024) sin documentación de qué piezas siguen vigentes.

**Veredicto:** el contenido existe pero está **desincronizado y mal indexado**. Para un jurado de RoboCup esto se lee como *"el equipo no tiene un único source-of-truth de su hardware"*, que es exactamente lo que el TDP debe demostrar que sí tiene. La mayoría de los arreglos son de **bajo riesgo y alto retorno de puntaje** (editar markdown, no tocar el robot).

---

## 1. Inventario de lo que EXISTE (con paths)

### 1.1. BOM (lista de materiales)

| Archivo | Estado | Observación |
|---|---|---|
| `hardware/bom/` | **VACÍO** (`.gitkeep` solamente) | La carpeta canónica para el BOM no tiene BOM. |
| `hardware/electronics/PCB_Main/README.md` | **BOM real, vigente** | 7 componentes electrónicos + 4 mecánicos + 4 de potencia, con uso/cantidad/proveedor/link. Es el BOM "bueno". |
| `hardware/electronics/_legacy/ELECTRONICA/Lista de materiales y link de compra.md` | Legacy 2024 | Versión vieja del mismo BOM. LiPo distinta (1500mAh 80C vs. 2200mAh actual). |
| `hardware/electronics/_legacy/ELECTRONICA/Archivo_EASY_EDA/BOM EASYEDA.csv` | Legacy 2024 (UTF-16) | BOM exportado de EasyEDA del board real → **acá aparece el MPU6050 y los drivers XH-5A/XH-D-5A** que el BOM bueno no menciona. |
| `hardware/electronics/power-tree/README.md` §2 | "BOM de Potencia" paralelo | Lista XL4016 / VNH5019 / INA219 / XL4015 — **contradice** al BOM real (ver §3). |

### 1.2. Esquemáticos / PCB / Gerbers

| Archivo | Estado | Observación |
|---|---|---|
| `hardware/electronics/PCB_Main/ROBOCUP.SHEET.pdf` | **Esquemático 2026** (CreationDate 2026-03-08) | Muestra BNO055, APDS9960, VL53L0X×2, Teensy 4.1, **ESP32-MINI, 2×LED-12V, relé KY019A, MP1584 5V/6V, motores DFROBOT**. Es el esquemático más actualizado pero refleja el **estado propuesto** (ESP32/LEDs aún no en firmware). |
| `hardware/electronics/PCB_Main/pcb-preview.pdf` | Render de PCB | Rasterizado (sin texto extraíble). Imagen del board. |
| `hardware/electronics/PCB_Main/PCB.json` | **PCB editable EasyEDA** | **Equivale al board legacy 2024** (mismo tamaño de archivo, diff = solo `editorVersion` 6.5.40→6.5.51 y una línea en blanco). **Contiene 5 referencias a MPU6050 y 0 a BNO055.** Es el board viejo re-guardado. |
| `hardware/electronics/PCB_Main/README.md` | Doble función (BOM, ver arriba) | No documenta que el `.json` es el board viejo. |
| `hardware/electronics/_legacy/ELECTRONICA/PDFS_DIAGRAMA_Y_PCB/Diagrama_Esquematico.pdf` | Legacy 2024 | Esquemático viejo (MPU6050). |
| `hardware/electronics/_legacy/ELECTRONICA/PDFS_DIAGRAMA_Y_PCB/PCB.pdf` | Legacy 2024 | Layout viejo. |
| `hardware/electronics/_legacy/ELECTRONICA/PRODUCCION_PCB/GERBER PCB V2.zip` | Legacy 2024 | **Únicos Gerbers del repo** → son del board 2024 (MPU6050). No hay Gerbers del diseño 2026. |
| `hardware/electronics/_legacy/ELECTRONICA/AUTOCAD_PCB/BOCETO DE PCB.dxf` | Legacy 2024 | Boceto DXF. |
| `hardware/electronics/_legacy/ELECTRONICA/creacion pcb.md` | Legacy 2024 | **Tabla de pinout** (motores, servos, ultrasonidos, ToF, serial). Sigue siendo la **única fuente textual de asignación de pines** del repo. |
| `hardware/electronics/_legacy/ELECTRONICA/imagenes/*` (11 PNG) | Legacy 2024 | Capturas de esquemático/PCB viejos. |

### 1.3. CAD / mecánica / STL

| Archivo | Estado | Observación |
|---|---|---|
| `hardware/mechanical/` | **VACÍO** (`.gitkeep` + `_legacy/`) | No hay CAD/STL 2026. |
| `hardware/mechanical/_legacy/CAD/Robot_F3D_Editable/Rescue3D.f3d` | Legacy 2024 (Fusion 360) | **Único CAD editable.** Es el diseño Roboliga 2024. |
| `hardware/mechanical/_legacy/CAD/STLS/*.stl` (24 STL) | Legacy 2024 | Piezas: base, soportes de motor, carcasa RPi, soporte cámara, brazos de servo, agarra-batería, aletas, ultrasonidos, etc. **Ninguna marcada como vigente/obsoleta.** |
| `hardware/mechanical/_legacy/CAD/Imagenes/*.png` (7 vistas) | Legacy 2024 | Render 6 vistas + Rescuebot. |
| `hardware/mechanical/_legacy/CAD/Readme.md` | Legacy 2024 | **Tabla de piezas + tornillería** (66 tornillos, tamaños). Buen documento, pero del diseño viejo. |
| `hardware/mechanics/traction-optimization/README.md` | 2026 (IA Gemini, 2026-02-23) | **Documento de I+D mecánico** (ruedas de silicona Shore A, CG dinámico, suspensión rocker-bogie, traction control). Es teoría/benchmark, no diseño concreto del robot. |

> ⚠️ Nota de naming: existen **dos** carpetas mecánicas hermanas — `hardware/mechanical/` (CAD legacy) y `hardware/mechanics/` (documento de tracción). Inconsistencia de nombres que confunde la navegación.

### 1.4. Documentación de evolución / decisiones de diseño

| Archivo | Estado | Calidad |
|---|---|---|
| `hardware/cambios_de_hardware.md` | **2026, 716 líneas** (Benjamin Villagran, commit `789cd7d`, 2026-04-28) | **Excelente.** 4 mejoras documentadas con problema → opciones evaluadas → solución → pros/contras, **citando el reglamento 2026** (§3.9 luces LED, §3.10 víctimas falsas, §6.3 SuperTeam comm). Ver §4. |
| `hardware/electronics/power-tree/README.md` | 2026 (IA Gemini) | Star-ground, fusible 15A, filtrado de motores 0.1µF, aislamiento RPi 20AWG. Buen documento de **best-practices**, pero con BOM que no matchea (§3). |
| `hardware/electronics/datasheets/README.md` | 2026 (IITA Salta) | Resumen de parámetros críticos: XL4016, **VNH5019**, **INA219**, LiPo 3S. Útil, pero documenta componentes que **no están en el BOM real**. |

---

## 2. Cruce CRÍTICO: documentación vs. firmware (`main.cpp`)

Crucé `software/teensy/firmware/src/main.cpp` (1278 líneas) contra `creacion pcb.md` (pinout) y el BOM. Resultado:

### 2.1. Lo que SÍ coincide (✅ — esto es bueno, hay que decirlo)

| Ítem | Firmware (`main.cpp`) | Doc (`creacion pcb.md`) | Match |
|---|---|---|---|
| Motor BL (pwm/dir/enc) | `Moto bl(29,28,27)` :40 | 29 / 28 / 27 | ✅ |
| Motor FL | `Moto fl(7,6,5)` :41 | 7 / 6 / 5 | ✅ |
| Motor BR | `Moto br(36,37,38)` :42 | 36 / 37 / 38 | ✅ |
| Motor FR | `Moto fr(4,3,2)` :43 | 4 / 3 / 2 | ✅ |
| Ultrasonido Right | `NewPing(8,9)` :259 | trig 8 / echo 9 | ✅ |
| Ultrasonido Left | `NewPing(11,10)` :260 | trig 11 / echo 10 | ✅ |
| Ultrasonido Front | `NewPing(39,33)` :261 | trig 39 / echo 33 | ✅ |
| ISR encoders | pins 27/5/38/2 :743-746 | encoders 27/5/38/2 | ✅ |
| ToF buses I2C | `Wire1`(17/16) / `Wire2`(25/24) :777-781 | SDA17/SCL16, SDA25/SCL24 | ✅ (los pines doc = buses Wire1/Wire2 de Teensy) |
| Switch | `SWITCH 32` INPUT_PULLUP :33,747 | pin 32 INPUT Pullup | ✅ |
| Serial RPi↔Teensy | `Serial5.begin(115200)` :753 | RX5/TX5 | ✅ |

> **Esto vale la pena destacarlo en el TDP:** el pinout de motores, encoders y sensores **está bien documentado y es fiel al firmware**. Es la parte fuerte.

### 2.2. Lo que NO coincide (❌ — temas a analizar)

| Ítem | Firmware (`main.cpp`) | Doc | Problema |
|---|---|---|---|
| **Servo LIFT** | `lift(22,...)` :23 | `creacion pcb.md`: Lift = **12** | Pin invertido en doc. |
| **Servo DEPOSIT** | `deposit(12,...)` :24 | `creacion pcb.md`: Deposit = **23** | Pin invertido en doc. |
| **Servo SORT** | `sort(23,...)` :20 | doc **no lista** servo "sort" | El 5º servo (sort) no está en la tabla de pines; doc asigna 23 a deposit. |
| **IMU** | **BNO055** `0x28` :38 | `PCB.json`: **MPU6050** (×5 refs); EasyEDA BOM: MPU6050 | El board editable tiene el sensor viejo. |
| **Relé** | `RELAY 0` :30, usado 14× | **No documentado en ningún pinout** | El relé (que enciende el LED 12V / mecanismo) está en **pin 0** y **no figura** en `creacion pcb.md` ni en el BOM. Pin 0 = RX1 de Teensy (posible conflicto si se usa Serial1; ver nota). |
| **BUZZER / LED_ROJO** | `BUZZER 31` / `LED_ROJO 30` :31-32 | `creacion pcb.md` no lista; `cambios_de_hardware.md` dice "antes 35/34 → después 31/30" | El firmware **ya aplicó** el remap que el doc ESP32 propone como "después", **pero la ESP32 no está conectada** (ver §4). Doc y firmware quedan en estados distintos → confuso. |

> **Nota sobre `RELAY 0`:** es un hallazgo de correctitud de firmware (fuera de mi dominio de documentación) pero **emerge del cruce de docs**: ningún plano ni BOM documenta el relé ni su pin, y el pin elegido (0 = RX1) es sensible. Lo dejo señalado para el auditor de firmware; desde documentación, el tema es que **un componente activo del robot (relé + lo que conmuta) es invisible en el BOM y en el pinout.**

### 2.3. Estado de implementación de las 4 mejoras de `cambios_de_hardware.md`

Verifiqué en `main.cpp` si las propuestas están implementadas:

| Mejora propuesta | Pines propuestos | ¿En firmware? | Estado real |
|---|---|---|---|
| LED 12V + APDS9960 reflectancia (evacuación) | relé existente | `get_color()` existe (:331), **pero el flujo de reflectancia C/PDATA/ganancia 1X del doc NO** (firmware usa `apds.begin()` por defecto :766) | **Parcial / propuesto.** El doc describe ganancia 1X y canal Clear; el firmware sigue con la inicialización default que el propio doc critica. |
| ESP32 Super Mini (SuperTeam) | Serial8 pines 34/35 | **NO** (`Serial8` no aparece) | **No implementado.** BUZZER/LED_ROJO ya se movieron a 31/30 (liberando 34/35), pero la ESP32 no está cableada ni en código. |
| Finales de carrera (alineación pared) | FC 40/41 | **NO** (`FC_IZQUIERDO`/`FC_DERECHO` no existen) | **No implementado.** |
| Pin de conductividad (víctima falsa) | pin 26 INPUT_PULLUP | **NO** (`CONDUCTIVIDAD` no existe) | **No implementado.** |

> **Lectura clave para el TDP:** `cambios_de_hardware.md` no es un *changelog de cambios hechos* sino un **documento de propuestas/diseño futuro**. El esquemático PDF 2026 ya dibuja esas mejoras (ESP32, LEDs) como si existieran. El robot real no las tiene. **Esta es la desincronización más peligrosa para un jurado:** la documentación "se adelanta" al robot, y no hay marca de "PROPUESTO vs. IMPLEMENTADO".

---

## 3. Cruce CRÍTICO: BOM vs. PCB real vs. power-tree vs. datasheets

Hay **tres listas de componentes de potencia que se contradicen**:

| Componente | BOM oficial (`PCB_Main/README.md`) | EasyEDA BOM real (`PCB.json` / `BOM EASYEDA.csv`) | Power-tree (`power-tree/README.md`) | Datasheets (`datasheets/README.md`) |
|---|---|---|---|---|
| **Driver de motores** | ❌ **NO LISTADO** | **XH-5A / XH-D-5A** (módulos H-bridge baratos) | **VNH5019** (30A) | **VNH5019** (30A) |
| **Regulador RPi** | "Regulador variable XL4016" | (RPi por header) | **XL4016** 5.1V/8A | **XL4016** |
| **Regulador Teensy/sensores** | "Regulador ajustable mini" ×2 (MP1584) | **MP1584 5V + MP1584 6V** | **XL4015** (Teensy) + **LM2596** (servos) | — |
| **Telemetría batería** | ❌ no | ❌ no (no está en el board) | **INA219** (I2C) | **INA219** |
| **Relé / LED 12V** | ❌ no | ❌ no (board viejo) | ❌ no | ❌ no |
| **Fusible / switch** | ❌ no fusible; XT60 sí | Switch DPDT + slide; sin fusible | "Fusible 15A" | — |
| **IMU** | BNO055 ✅ | **MPU6050** ❌ | (BNO055 implícito) | — |
| **LiPo** | 2200mAh 3S 30-60C ✅ | (board no define batería) | 35C | 35C |

**Conclusiones del cruce:**

1. **El driver de motores —componente de potencia más crítico del robot— no está en el BOM oficial.** El board real usa módulos **XH-5A/XH-D-5A**; el power-tree y las datasheets hablan de **VNH5019** (que es un driver de gama muy superior). O bien el equipo migró a VNH5019 y no actualizó el BOM/PCB, o bien el power-tree/datasheets describen un driver que el robot **no tiene**. **Hay que resolver cuál es la verdad.**
2. El **INA219** (telemetría de batería) aparece en power-tree y datasheets como si fuera parte del diseño, pero **no está en el BOM ni en el board**. Riesgo: el TDP afirma capacidad de monitoreo de batería que el robot no tiene.
3. El power-tree menciona **XL4015 / LM2596** para Teensy/servos, pero el board real usa **MP1584** (5V y 6V). Reguladores distintos.
4. El power-tree y las datasheets están **firmados por "Ai Gemini"** y son claramente **plantillas genéricas de best-practices** (star-ground, fusible, filtrado) que **no fueron reconciliadas con el board real del equipo**. Son buenos como guía, pero **no como documentación del robot**.

> **Para el TDP esto es delicado:** un jurado que cruce el power-tree (VNH5019 + INA219 + fusible 15A) con el board físico (XH-5A, sin INA219, sin fusible) detecta que **la documentación describe un robot que no es el que está en la mesa.** En RoboCup, la coherencia documentación↔robot es justamente lo que se evalúa en la interview.

---

## 4. Calidad de las decisiones de diseño documentadas (lo bueno)

`hardware/cambios_de_hardware.md` (716 líneas) es, con diferencia, el **mejor documento de hardware del repo** y un activo real para el Engineering Journal del TDP. Documenta 4 decisiones con rigor:

1. **LED 12V + APDS9960 como sensor de reflectancia** para detectar la línea negra de salida de evacuación sin depender de la cámara. Justifica contra el **reglamento 2026 §3.9** (luces LED intermitentes en las paredes) y explica física de reflectancia (canal Clear, IR difuso vs. especular blanco/plateado, ganancia 1X vs. 4X). **Nivel de análisis muy alto.**
2. **ESP32 Super Mini** para el SuperTeam Challenge (**§6.3**), con análisis comparativo descartando HC-05/HC-06 (problema de MAC address y roles fijos) a favor de BLE broadcast. **Excelente razonamiento de trade-offs.**
3. **Finales de carrera** para alineación física contra la pared en el depósito (reemplaza retroceso por tiempo fijo), con opción A (pitch BNO055) evaluada y descartada. **Buen método.**
4. **Pin de conductividad** en la garra para distinguir víctimas plateadas reales de falsas (**§3.10**: vivas = conductivas), incluyendo el problema de fatiga del cable y recomendación de cable siliconado/jumper. **Detalle de ingeniería real.**

`power-tree/README.md` y `mechanics/traction-optimization/README.md` también suman como documentos de I+D (star-ground, control de tracción, CG dinámico, Shore A).

> **Esto puntúa en el TDP** siempre que se aclare qué está **implementado** vs. **propuesto**. Hoy no se aclara, y el esquemático ya dibuja lo propuesto como real → el valor se diluye en confusión.

---

## 5. Lo que FALTA (gaps de documentación)

| Gap | Impacto |
|---|---|
| **`hardware/bom/` vacío** | El BOM canónico no existe donde se lo busca; vive escondido en `electronics/PCB_Main/README.md`. Un jurado no lo encuentra. |
| **BOM sin driver de motores, sin relé, sin LED 12V, sin fusible, sin cableado/AWG** | BOM incompleto: faltan componentes activos y de potencia. No es un BOM "de fabricación". |
| **BOM sin números de parte / sin costos / sin revisión** | No hay versión del BOM ni fecha; imposible saber qué edición es. |
| **PCB editable (`.json`) = board 2024 con MPU6050** | **No se puede re-fabricar ni editar el board real desde el repo.** Si se quema la placa, no hay archivo fuente del board 2026. |
| **Sin Gerbers 2026** | Los únicos Gerbers (`GERBER PCB V2.zip`) son del board 2024. |
| **Sin CAD/STL 2026** | Todo el mecánico es `_legacy/`; no hay diseño 2026 ni marca de qué piezas siguen vigentes. La garra/soportes actuales no tienen STL trazable. |
| **Sin `power tree` reconciliado con el board real** | El power-tree es plantilla genérica (VNH5019/INA219) que no matchea el hardware. |
| **`cambios_de_hardware.md` sin estado por mejora** | No distingue PROPUESTO / EN PRUEBA / IMPLEMENTADO ni fecha por cambio (la regla de oro 6 del `CLAUDE.md` pide "fecha y razón" por cambio físico; el doc agrupa todo sin fechas individuales). |
| **Pinout (`creacion pcb.md`) en `_legacy/` y desactualizado** | El único pinout textual está marcado como legacy y tiene servos invertidos + sin relé/sort/ESP32. Debería ser un doc vivo en la raíz de `electronics/`. |
| **Sin soportes 3D para las 4 mejoras** | El propio `cambios_de_hardware.md` reconoce que LED 12V, ESP32, finales de carrera y electrodos de garra **requieren soportes 3D que aún no existen** (ni STL ni mención en mecánica). |
| **Sin power budget numérico** | No hay tabla de consumo (corriente por riel, autonomía estimada de la LiPo 2200mAh). El power-tree describe topología pero no presupuesto energético. |
| **Naming `mechanical` vs `mechanics`** | Dos carpetas hermanas confunden la navegación. |
| **Sin OS-backup de la SD de RPi** | El `AUDIT-ACTION-PLAN.md` §3 ya lo sugería (`hardware/raspberry/os-backups/`) y no existe. |

---

## 6. Relación con auditorías previas (no se repite, se cita)

- **CORRECTITUD #120-#128:** los bugs **#B1 (PID invertido), #B4 (leer_yaw), #B10 (encoder sin calibrar)** son de firmware. Esta auditoría de documentación **no los re-reporta**; solo agrega que **el encoder sin calibrar (#B10) tampoco tiene documentado en hardware** ningún dato de pulsos/vuelta del motor DFRobot 159RPM ni diámetro de rueda (58mm omni) en el BOM → la calibración no tiene fuente documental.
- **RESILIENCIA #53/#27/#57-#119:** heartbeat/WDT/timeouts son de firmware/comms. Agrego que el **relé en pin 0 (RX1)** y la **ausencia de fusible en el board real** (el power-tree lo recomienda pero el board no lo tiene) son temas de hardware **no cubiertos** por esas auditorías.
- **`AUDIT-ACTION-PLAN.md`:** su §3 ya pedía OS-backups y testing matrix; sigue sin haber `hardware/raspberry/os-backups/`.

---

## 7. TEMAS A ANALIZAR (findings con riesgo-no-fix / riesgo-fix / tiempo)

> Ninguno toca el robot ni el firmware salvo donde se aclara. La mayoría es **edición de markdown** → riesgo de romper el robot = nulo.

### HW-01-A — `hardware/bom/` vacío; BOM real escondido e incompleto
- **Qué:** mover/centralizar el BOM a `hardware/bom/`, completarlo con driver de motores (XH-5A/VNH5019, según se confirme), relé KY019A, LED 12V, fusible, cableado AWG, números de parte, costo y **revisión + fecha**.
- **Riesgo de NO corregir:** el jurado no encuentra el BOM; el BOM incompleto sugiere que el equipo no conoce su propio robot. **Pérdida directa en TDP Electronics.**
- **Riesgo de corregir:** ninguno técnico; solo trabajo de relevamiento (alguien tiene que mirar el robot y anotar el driver real).
- **Tiempo:** 2-3 h (incluye confirmar driver físico con los chicos).

### HW-01-B — Las 3 representaciones del hardware no coinciden (firmware ↔ esquemático PDF ↔ PCB.json)
- **Qué:** decidir cuál es el source-of-truth. **Como mínimo**, regenerar el **PCB editable 2026** (con BNO055, no MPU6050) o documentar explícitamente que `PCB.json` es el board 2024 y que el board físico actual difiere. Idealmente exportar Gerbers 2026.
- **Riesgo de NO corregir:** si se quema la placa, **no hay archivo fuente para re-fabricar el board real**. Y el jurado detecta MPU6050 en el archivo editable mientras el robot usa BNO055.
- **Riesgo de corregir:** rehacer el layout en EasyEDA es trabajo de PCB real; si se hace mal, el board nuevo podría no coincidir. **Mitigación:** primero documentar la divergencia (riesgo 0), después rehacer el board con calma post-mundial.
- **Tiempo:** documentar divergencia 1 h; regenerar PCB editable + Gerbers 2026: 6-10 h (tarea de PCB, no de docs).

### HW-01-C — `cambios_de_hardware.md` no marca PROPUESTO vs. IMPLEMENTADO; el esquemático ya dibuja lo propuesto
- **Qué:** agregar a cada una de las 4 mejoras un estado (`PROPUESTO` / `EN BANCO` / `IMPLEMENTADO`) + fecha, y una nota en el esquemático PDF aclarando que ESP32/LED-12V/finales/conductividad son **diseño futuro** aún no montado.
- **Riesgo de NO corregir:** el jurado cree que el robot tiene ESP32+LEDs+finales (porque el esquemático los dibuja) y al verlos ausentes, **pierde credibilidad todo el TDP**. Confusión interna del equipo sobre qué está hecho.
- **Riesgo de corregir:** ninguno (markdown + nota en PDF).
- **Tiempo:** 1-2 h.

### HW-01-D — Power-tree y datasheets describen componentes que el robot no tiene (VNH5019, INA219, fusible, XL4015/LM2596)
- **Qué:** reconciliar `power-tree/README.md` y `datasheets/README.md` con el hardware real (MP1584 5V/6V, driver real, sin INA219). Si se quiere INA219/fusible, marcarlos como **mejora propuesta**, no como estado actual.
- **Riesgo de NO corregir:** documentación describe un robot ficticio; el cruce físico delata la incoherencia. **Riesgo eléctrico real:** el power-tree afirma "fusible 15A" → si alguien asume que está y no está, no hay protección.
- **Riesgo de corregir:** ninguno documental. Si se decide **agregar** fusible/INA219 al robot, eso sí toca hardware (otro finding).
- **Tiempo:** 2-3 h de reconciliación documental.

### HW-01-E — Pinout (`creacion pcb.md`) desactualizado y en `_legacy/`
- **Qué:** crear un `hardware/electronics/pinout.md` vivo, derivado del firmware actual: corregir LIFT=22 / DEPOSIT=12 / agregar SORT=23, agregar RELAY=0, BUZZER=31, LED_ROJO=30, y los pines libres reservados (26, 40, 41 según las mejoras).
- **Riesgo de NO corregir:** quien arme/repare el robot usa pines invertidos de servos → daño mecánico (un servo movido al pin equivocado puede forzar la garra). El relé invisible (pin 0/RX1) puede colisionar si alguien activa Serial1.
- **Riesgo de corregir:** ninguno (es doc derivada del código, fuente de verdad = firmware).
- **Tiempo:** 1-2 h.

### HW-01-F — Sin CAD/STL 2026 ni trazabilidad de piezas vigentes; faltan soportes 3D de las mejoras
- **Qué:** marcar en `mechanical/_legacy/CAD/Readme.md` qué piezas siguen vigentes vs. obsoletas; exportar/commitear el `.f3d` y STL actuales del robot 2026; diseñar los soportes 3D que las 4 mejoras requieren. Unificar `mechanical`/`mechanics`.
- **Riesgo de NO corregir:** si se rompe una pieza en Incheon, **no hay STL trazable para reimprimir**. TDP Mechanical débil. Las mejoras propuestas no se pueden montar sin soportes.
- **Riesgo de corregir:** ninguno documental; diseñar soportes sí es trabajo de CAD.
- **Tiempo:** relevar/marcar vigencia 1-2 h; exportar STL actuales 1 h; soportes 3D nuevos: 4-8 h cada uno (mecánico).

### HW-01-G — Sin power budget numérico ni datos de calibración del encoder en el BOM
- **Qué:** agregar tabla de consumo por riel + autonomía estimada de la LiPo 2200mAh; documentar pulsos/vuelta del motor DFRobot y diámetro/circunferencia de rueda (58mm) para dar **fuente documental a la calibración del encoder (#B10)**.
- **Riesgo de NO corregir:** no se sabe cuánto dura la batería en pista (riesgo de quedarse sin energía a mitad de corrida); la calibración del encoder no tiene base trazable.
- **Riesgo de corregir:** ninguno.
- **Tiempo:** 2-3 h.

---

## 8. Impacto estimado en el TDP (Engineering Journal — Electronics / Mechanical)

> El TDP de RoboCup Junior Rescue evalúa, entre otros, **Electronics** y **Mechanical Design** dentro del Engineering Journal, premiando: BOM claro, esquemáticos legibles, **coherencia documentación↔robot**, y **proceso de iteración documentado**.

**Estado actual estimado (cualitativo):**

| Subsección TDP | Hoy | Techo alcanzable con los fixes documentales |
|---|---|---|
| **BOM / lista de componentes** | **Bajo-medio** — existe pero incompleto, escondido y sin driver de motores | **Alto** — con HW-01-A/E (relevamiento + centralización). |
| **Esquemáticos / PCB** | **Medio** — esquemático 2026 lindo, pero PCB editable es el board 2024 (MPU6050) y dibuja mejoras inexistentes | **Medio-alto** — con HW-01-B/C (regenerar board o documentar divergencia + marcar propuesto). |
| **Power / distribución** | **Medio** — buen documento conceptual pero describe componentes ausentes (VNH5019/INA219/fusible) | **Alto** — con HW-01-D/G (reconciliar + power budget). |
| **Mechanical design** | **Bajo-medio** — solo CAD 2024 legacy, sin trazabilidad ni STL 2026 | **Medio-alto** — con HW-01-F. |
| **Iteración / decisiones de diseño** | **Alto** — `cambios_de_hardware.md` es excelente | **Muy alto** — con HW-01-C (estado por mejora) brilla sin ambigüedad. |

**Lectura para el coach:** el **contenido ya está casi todo** y la **capacidad de análisis del equipo es evidente** (el doc de cambios y los de I+D lo demuestran). Lo que baja el puntaje no es falta de trabajo sino **desincronización y mala indexación**: tres listas de componentes que se contradicen, un BOM donde no se lo busca, un PCB editable viejo, y mejoras dibujadas como si existieran. **La mayor parte del retorno de puntaje se consigue con ~10-15 h de trabajo documental de bajo riesgo (editar markdown, relevar el robot físico), sin tocar firmware ni el robot.** Las tareas de PCB/CAD reales (regenerar board 2026, soportes 3D) son de mayor esfuerzo y conviene planificarlas, pero el primer salto de puntaje es barato.

---

*Informe HW-01 — auditoría de documentación de hardware. Solo lectura. No se modificó código ni archivos de `software/**` ni `hardware/**`. Todos los hallazgos se presentan como temas a analizar, no como cambios mandados.*
