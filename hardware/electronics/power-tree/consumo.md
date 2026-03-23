# Consumo eléctrico y autonomía del robot

## 🔋 Batería utilizada
- Tipo: LiPo 3S
- Voltaje nominal: 11.1V
- Capacidad: 2200 mAh (2.2 Ah)
- Energía total:

E = V × Ah  
E = 11.1 × 2.2 = **24.42 Wh**

---

# Componentes electrónicos

| Componente | Voltaje | Consumo típico | Consumo máx | Cant | Datasheet |
|------------|---------|---------------|-------------|------|-----------|
| USB Wide Camera 140° | 5V | 200 mA | 300 mA | 1 | https://www.usb.org/document-library/video-class-v15-document-set |
| BNO055 IMU | 3.3–5V | 12 mA | 20 mA | 1 | https://cdn-shop.adafruit.com/datasheets/BST_BNO055_DS000_12.pdf |
| VL53L0X ToF | 3.3–5V | 19 mA | 40 mA | 2 | https://www.st.com/resource/en/datasheet/vl53l0x.pdf |
| HC-SR04 | 5V | 15 mA | 30 mA | 3 | https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf |
| APDS9960 | 3.3–5V | 5 mA | 16 mA | 1 | https://cdn.sparkfun.com/assets/learn_tutorials/3/2/1/Avago-APDS-9960-datasheet.pdf |
| Raspberry Pi 5 (8GB) | 5V | 1.2 A | 5 A | 1 | https://pip.raspberrypi.com/documents/RP-008348-DS-raspberry-pi-5-product-brief.pdf |
| Teensy 4.1 | 5V | 100 mA | 250 mA | 1 | https://www.pjrc.com/teensy/techspecs.html |

### Subtotal electrónica (máx)
≈ **5.65 A @ 5V**

---

# Componentes mecánicos

| Componente | Voltaje | Consumo típico | Consumo máx | Cant | Datasheet |
|------------|---------|---------------|-------------|------|-----------|
| Motor DC con encoder 12V | 12V | 800 mA | 3 A | 4 | https://www.dfrobot.com/wiki/index.php/DC_Gear_Motor |
| Servo Clutch 2kg 300° | 6V | 200 mA | 700 mA | 5 | https://wiki.dfrobot.com/Servo |
| Omniwheel 58mm | — | — | — | 2 | (pasivo) |

### Subtotal mecánico (máx)
≈ **15.5 A**

---

# Reguladores

| Componente | Entrada | Salida | Datasheet |
|------------|---------|--------|-----------|
| XL4016 Step Down | 11.1V | 5V | https://datasheet.lcsc.com/lcsc/1811141611_XLSEMI-XL4016E1_C51545.pdf |
| Regulador ajustable mini | 11.1V | 5–6V | https://www.ti.com/lit/ds/symlink/lm2596.pdf |

---

# ⚡ Consumo total estimado

| Sistema | Corriente |
|---------|-----------|
| Electrónica | 5.65 A |
| Motores + servos | 15.5 A |
| **TOTAL MÁXIMO** | **≈ 21.15 A** |

---

# 🔋 Estimación de autonomía

La autonomía real se calcula con consumo **promedio**, no máximo.

En RoboCup Rescue típicamente:

- Motores NO están en stall constante
- Servos funcionan intermitente
- CPU con carga media

👉 Consumo promedio estimado: **8–10 A**

---

## Cálculo

Capacidad batería = 2.2 Ah

### Caso realista (9A promedio):

Tiempo = Ah / A  

Tiempo = 2.2 / 9 = **0.24 h**

Tiempo ≈ **14 minutos**

---

## Resultado final

| Escenario | Duración estimada |
|-----------|------------------|
| Máxima carga continua | ~6 min |
| Competencia real (promedio) | **12–15 min** |
| Uso liviano / pruebas | 18–22 min |

---

# 🧠 Notas técnicas

- Raspberry Pi 5 puede requerir hasta **5A por USB-C** bajo carga completa. :contentReference[oaicite:0]{index=0}
- El sensor VL53L0X consume aproximadamente **19 mA durante medición activa**. :contentReference[oaicite:1]{index=1}
- El HC-SR04 opera típicamente a **15 mA**. :contentReference[oaicite:2]{index=2}
- El APDS9960 reduce consumo mediante modos de bajo consumo configurables. :contentReference[oaicite:3]{index=3}

---

# ✅ Recomendación RoboCup

Se recomienda:

- batería ≥ 2200 mAh ✔️
- margen de seguridad ≥ 30%
- regulador 5V ≥ 8A para Raspberry Pi 5