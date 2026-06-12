# Verified component specifications for TDP evidence

Generated from the links listed in `hardware/electronics/PCB_Main/README.md`, plus official datasheets/product pages when the marketplace link did not expose enough technical data.

Do not treat derived values as measured performance. They are engineering estimates for planning tests and must be validated on the robot.

## Source map

| Component in BOM | README source | Verification source used | Status |
|---|---|---|---|
| USB Wide Camera 140 deg | Amazon ASIN B0DR7XXJL1 | https://tiendamia.com/ar/p/amz/b0dr7xxjl1/yosoo-health-gear-2-million-pixels-140-wide-angle-lens | Amazon page was not fetchable; Tiendamia mirrors the same ASIN. Verify locally with `v4l2-ctl --list-formats-ext`. |
| BNO055 IMU | https://www.adafruit.com/product/2472 | Same Adafruit product page | Official vendor page. |
| VL53L0X ToF | MercadoLibre GY-53/VL53L0X link | https://www.st.com/en/imaging-and-photonics-solutions/vl53l0x | Marketplace page was not reliably fetchable; ST page verifies sensor IC/module capability. |
| HC-SR04 ultrasonic | MercadoLibre HC-SR04 link | https://www.sparkfun.com/ultrasonic-distance-sensor-hc-sr04.html | Marketplace page was not reliably fetchable; SparkFun page verifies common module specs. |
| APDS9960 | MercadoLibre GY-9960 link | https://cdn.sparkfun.com/datasheets/Sensors/Proximity/apds9960.pdf | Datasheet verifies APDS-9960 IC. |
| Raspberry Pi 4 8GB | MercadoLibre Raspberry Pi 4 link | https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/ | Official Raspberry Pi specs. |
| Teensy 4.1 | https://www.pjrc.com/store/teensy41.html | Same PJRC page | Official Teensy page. |
| DFRobot 12V 159RPM motor | https://www.dfrobot.com/product-1364.html | Same DFRobot page | Official product page. |
| DFRobot 2kg 300 deg clutch servo | https://www.dfrobot.com/product-2126.html | Same DFRobot page | Official product page. |
| 58mm omniwheel | eBay item in README | eBay equivalent listings: https://www.ebay.com/itm/365966796692 and https://www.ebay.com/itm/163818034083 | Original item ID was not directly found in search, but equivalent listings match 58mm / 12kg description. Treat as marketplace evidence only. |
| Pololu fixed wheels | https://www.pololu.com/product/1420 | Same Pololu product page | Official product page. |
| LiPo 11.1V 3S 2200mAh 30-60C | MercadoLibre CNHL link | https://chinahobbyline.com/collections/us-warehouse/products/cnhl-black-series-2200mah-11-1v-3s-30c-lipo-battery-with-xt60-plug | Official CNHL page confirms the 2200mAh 3S 11.1V 30C XT60 pack listing. Verify exact burst rating, dimensions, and weight physically from your pack/label before submission. |
| XL4016 regulator | MercadoLibre XL4016 link | https://envistiamall.com/es/blogs/learn/xl4016-8a-step-down-buck-converter-voltmeter-user-guide | Technical guide for common XL4016 module. |
| MP1584 mini regulator | MercadoLibre MP1584 link | https://www.mouser.com/catalog/specsheets/Soldered_109023%20step%20down%20module%20mp1584%203a.pdf | Datasheet for MP1584 3A module. |
| XT60 connector | MercadoLibre XT60 link | https://components101.com/connectors/xt60-connector | General connector reference; use only for connector-level evidence. |

## Verified specs

### Camera

| Field | Value | Source |
|---|---:|---|
| ASIN | B0DR7XXJL1 | README / Tiendamia mirror |
| Listed model text | Yosoo Health Gear USB Camera Module / HBV-1716WA | Tiendamia mirror |
| Sensor resolution | 2 million pixels | Tiendamia mirror |
| Video mode | Full HD 1080P at 60 fps | Tiendamia mirror |
| Lens field of view | 140 deg | README / Tiendamia mirror |
| USB standard | USB2.0, UVC plug-and-play | Tiendamia mirror |

TDP use: mention the robot uses a 140 deg wide-angle UVC USB camera, but measured camera mode must come from the Raspberry Pi runtime because the code currently configures 160 x 120 px and does not actively set FPS.

### Controllers

| Field | Raspberry Pi 4 Model B 8GB | Teensy 4.1 |
|---|---:|---:|
| CPU | Broadcom BCM2711, quad-core Cortex-A72 64-bit at 1.8GHz | ARM Cortex-M7 at 600MHz |
| Memory | 8GB LPDDR4-3200 variant | 1024K RAM, 7936K Flash, 4K emulated EEPROM |
| GPIO / IO | 40-pin Raspberry Pi GPIO header | 55 total digital IO, 42 breadboard IO |
| PWM | Not specified in BOM page | 35 PWM pins |
| Serial | USB/Ethernet/Wi-Fi available | 8 serial ports |
| I2C | Available through GPIO | 3 I2C ports |
| Power | 5V DC, minimum 3A | 3.3V logic; pins are not 5V tolerant |

TDP use: this supports the dual-computer architecture: Raspberry Pi for vision and Teensy for deterministic real-time control.

### Sensors

| Sensor | Verified specs | Source |
|---|---|---|
| BNO055 | 9-DOF fusion sensor; Euler/quaternion/orientation outputs at 100Hz; magnetic field at 20Hz; temperature at 1Hz; I2C address 0x28 default or 0x29; 20 x 27 x 4 mm; 3 g | Adafruit product page |
| VL53L0X | Time-of-Flight ranging; absolute distance up to 2 m; 940 nm VCSEL; Class 1 laser; I2C interface; programmable I2C address; 4.4 x 2.4 x 1.0 mm | ST product page |
| HC-SR04 | 5V DC, 15mA, 15 deg measuring angle, 2 cm to 4 m range, accuracy up to 3 mm | SparkFun product page |
| APDS-9960 | Gesture, proximity, ambient light, and RGBC color sensing; 16-bit RGBC data; I2C fast mode up to 400 kHz; 3.94 x 2.36 x 1.35 mm package | APDS-9960 datasheet |

Important electrical risk: HC-SR04 is a 5V module, while Teensy 4.1 IO is not 5V tolerant. The schematic/PCB must show level shifting or a voltage divider on Echo lines, or this should be added before competition.

### Actuators and wheels

| Component | Verified specs | Source |
|---|---|---|
| DFRobot FIT0441 motor | 12V; stall current 0.7A; motor rated speed 7100-7300 rpm before reduction; output speed about 159 rpm; 45:1 reduction; blocking torque 2.4 kg*cm; signal cycle pulse number 6*45; PWM speed, direction, feedback pulse output | DFRobot product page |
| DFRobot SER0056 servo | 4.8-6V DC; static current <=8mA at 6V; no-load current <=110mA at 4.8V and <=120mA at 6V; stall current <=700mA at 4.8V and <=800mA at 6V; rated torque >=0.45 kgf*cm at 4.8V and >=0.55 kgf*cm at 6V; stall torque >=1.6 kgf*cm at 4.8V and >=2.0 kgf*cm at 6V; 300 deg +/-10 deg; PWM; 500-2500 us pulse width; shuts power after 5 s blockage | DFRobot product page |
| 58mm omniwheel | 58 mm wheel diameter; 12 kg load capacity; 13 mm roller diameter; aluminum alloy rollers; marketplace evidence only | eBay equivalent listing |
| Pololu 1420 fixed wheel | 60 mm diameter, 8 mm width, silicone tires, pair of wheels, press-fit for 3 mm D shafts | Pololu product page |

### Power

| Component | Verified specs | Source |
|---|---|---|
| LiPo battery | 3S / 11.1V / 2200mAh / 30C continuous / XT60 from CNHL listing; 60C burst appears in your BOM and must be confirmed on the physical pack/label | README, CNHL |
| XL4016 buck module | Input 4-38V; adjustable output 1.25-36V; up to 5A continuous / 8A peak; up to 94% efficiency; set output before connecting load | Envistia guide |
| MP1584 buck module | Input 4.5-28V; output 0.8-20V; max output current 3A; peak 4A; up to 96% efficiency; 22 x 17 x 4 mm; no reverse-polarity protection diode | Mouser/Soldered datasheet |
| XT60 connector | 2-pin polarized power connector; POWER and GND; up to 30A and 500V in this reference; fireproof nylon exterior; 0.55 mohm contact resistance | Components101 |

## Derived values for test planning

| Derived metric | Formula | Value | Confidence |
|---|---|---:|---|
| Battery nominal energy | 11.1 V x 2.2 Ah | 24.42 Wh | derived |
| Battery continuous current from 30C | 2.2 Ah x 30 | 66 A | derived |
| Battery burst current from 60C | 2.2 Ah x 60 | 132 A | derived |
| Total motor stall current | 4 motors x 0.7 A | 2.8 A | derived from motor spec |
| Total servo stall current | 5 servos x 0.8 A | 4.0 A | derived from servo spec |
| 58 mm wheel circumference | pi x 5.8 cm | 18.22 cm | derived |
| 60 mm wheel circumference | pi x 6.0 cm | 18.85 cm | derived |
| No-load speed with 58 mm wheel | 159 rpm x 18.22 cm / 60 | 48.3 cm/s | derived, ideal |
| No-load speed with 60 mm wheel | 159 rpm x 18.85 cm / 60 | 49.9 cm/s | derived, ideal |
| Motor feedback cycles per output revolution | 6 x 45 | 270 cycles/rev | derived from DFRobot spec |
| Encoder cycles per cm with 58 mm wheel | 270 / 18.22 | 14.8 cycles/cm | derived, depends on feedback interpretation |
| Encoder cycles per cm with 60 mm wheel | 270 / 18.85 | 14.3 cycles/cm | derived, depends on feedback interpretation |
| Team kinematic tick size | pi x 60 mm / 540 ticks | 0.3491 mm/tick | derived from team calibration model |
| Team theoretical encoder scale | 10 mm / 0.3491 mm/tick | 28.65 ticks/cm | derived from team calibration model |
| Code distance scale | `encoder = 25 * Distance` | 25 counts/cm | exact in code |

Encoder calibration note: the team kinematic model uses a 60 mm wheel and 540 ticks/rev, giving 0.3491 mm/tick and 28.65 ticks/cm. The final firmware uses 25 counts/cm because the drivetrain was calibrated on the physical robot. In the TDP, present this as model-to-field calibration: theoretical scale = 28.65 ticks/cm, field-calibrated command scale = 25 counts/cm. This is a strong quality-assurance point if paired with a short calibration table from 10 cm / 25 cm / 50 cm trials.

Servo calibration warning: the DFRobot SER0056 nominal range is 500-2500 us for 300 deg, while the code configures 540-2390 us over 274 deg. That is a deliberately narrower software range and should be described as a safety/calibration limit, not the full physical servo capability.

## TDP-safe claims

- The robot uses four 12V DFRobot brushless DC motors with integrated driver/encoder, PWM speed control, direction control, and feedback pulse output.
- The robot uses five DFRobot SER0056 2kg 300 deg clutch servos; their electronic protection shuts power after a 5 s blockage.
- The Raspberry Pi 4 Model B 8GB provides high-level image processing, while the Teensy 4.1 provides real-time motor/sensor/servo control with 8 serial ports, 35 PWM pins, and 3 I2C buses.
- The sensing stack includes BNO055 IMU, VL53L0X ToF sensors, HC-SR04 ultrasonic sensors, APDS-9960 color/proximity sensor, and a 140 deg UVC USB camera.
- The power system is based on an 11.1V 3S 2200mAh LiPo battery, stepped down through XL4016 and MP1584 buck regulators for logic and actuator rails.

## Must-validate before TDP submission

- Measure real camera FPS and actual supported modes on the robot with `v4l2-ctl --list-formats-ext`.
- Confirm HC-SR04 Echo lines are level-shifted or divided before Teensy inputs.
- Measure 5V Raspberry rail under vision load; Raspberry Pi 4 expects 5V with up to 3A supply capability.
- Measure servo rail voltage while all five servos move or stall briefly.
- Count actual encoder transitions per wheel revolution and per 10 cm travel.
- Measure real max speed over a 1 m straight run; use the 48-50 cm/s value only as no-load theory.
- Weigh the exact battery pack and record measured charged voltage, nominal voltage, and voltage sag during pickup/deposit.
