# Análisis de flexibilidad para Technical Challenges y SuperTeams — 2026-05-10

> **Pregunta del coach:** ¿qué tan preparado está el código para ejecutar tareas distintas como las que aparecen en los **Technical Challenges** o **SuperTeams** del RoboCup Junior Rescue Line? ¿Qué cambios harían más simple plug-and-play de ejercicios nuevos?
>
> **Forma del análisis:** mismo framing que el documento de comms — todos los hallazgos son **TEMAS A ANALIZAR**, no directivas de fix. Cada uno con riesgo-de-no-cambiar, riesgo-de-cambiar y tiempo realista.
>
> **Asignados de seguimiento:** @enzzo19 + @benjaminvillagran. Coach: @gviollaz.

---

## 1. Resumen ejecutivo

El código actual está optimizado **para una única corrida tipo "campeonato Roboliga / RCJ international clásico"**: línea → rescate de pelotas → depósito → fin. Funciona, pero es **rígido**: probar un Technical Challenge aislado (e.g. "solo seesaw" o "solo gap recovery") requiere reflashear y editar `main.cpp`. Para SuperTeam **no hay infraestructura** — falta canal de comms entre robots y abstracción de "rol" (líder, seguidor, observador).

**Diagnóstico en una línea:** la arquitectura es **monolítica por task**, no **componible por skill**. La diferencia importa cuando aparece un challenge nuevo en pista a 24 hs de competencia.

**Recomendación táctica:** **no reescribir** antes del mundial. Aplicar 3-4 cambios incrementales que abren la puerta a "modos" sin tocar la lógica base: `mode` flag en RPi al boot, "skill registry" mínimo en Teensy, archivo `tasks.yaml` con secuencias. Eso da 80 % de la flexibilidad con riesgo bajo de regresión.

---

## 2. Tipos de tareas en RCJ Rescue Line

Esta sección es contexto — qué tipo de ejercicios suelen pedirse y qué habilidades demandan.

### 2.1 Run estándar (lo que el código hoy resuelve)

Una corrida completa con todos los elementos en secuencia:
- Seguir línea negra.
- Detectar y reaccionar a marcadores verdes (giro izquierda, derecha, doble verde = U-turn).
- Pasar gaps (línea cortada).
- Pasar speed bumps (lomos pequeños).
- Cruzar puente / túnel.
- Subir/bajar rampa (≤ 25°).
- Esquivar obstáculo (bloque sobre la línea).
- Cruzar seesaw (sube-y-baja).
- Detectar línea plateada → entrar a zona de evacuación.
- Identificar víctimas (negro = muerto, plateado = vivo) y depositar en zona correcta (rojo / verde).

**Puntaje típico (RCJ International / Roboliga):** 10 pts/gap, 10 pts/intersección, 10 pts/rampa, 20 pts/seesaw, 20 pts/obstáculo, +bonus por víctimas y zona.

### 2.2 Technical Challenges

Son **mini-pruebas aisladas** que testean una habilidad específica. El comité los anuncia 24-48 hs antes (a veces el día) y suelen ser:

- **"Solo seesaw"** — el robot atraviesa un seesaw aislado.
- **"Solo gap"** — recuperación de línea tras gap.
- **"Solo recolección"** — pinza en zona de evacuación con N víctimas en posiciones fijas.
- **"Sólo zona"** — entrar a la zona de evacuación, identificar víctima y depositar.
- **"Línea con luz variable"** — línea sin verdes, pero con un LED dentro de la zona de evacuación cambiando ángulo (cambio 2026, ver §1.1 de las reglas oficiales 2026).
- **"Detección de víctimas falsas"** — distinguir víctimas reales de "fake victims" (cambio 2026, ver §2 de las reglas oficiales).
- **"Pista invertida"** — fin del recorrido al revés (raro pero ocurrió).
- **"Run con sensor inhabilitado"** — desconectar IMU o ToF y completar igual.

**Lo común:** el robot debe **arrancar desde cualquier punto de la pista**, no solo desde el `start tile` clásico, y a veces saltar partes (e.g. "no hay zona de rescate, solo termina al final").

### 2.3 SuperTeam Challenge

Dos o más robots de **equipos distintos** colaboran en una pista común. Puede ser:

- **Relevo** — un robot recorre la primera mitad, otro la segunda.
- **División de tareas** — uno se ocupa de la línea, otro del rescate.
- **Asistencia** — uno empuja víctimas hacia el otro.
- **Observador / coach** — un robot se queda quieto en un punto y avisa al otro vía Bluetooth/ZigBee.

**Reglas comunes:** comunicación inalámbrica entre robots permitida (Bluetooth class 2/3 o ZigBee), no entre robot y exterior. Punto de sincronización suele ser un evento físico (cruzar línea, detectar marker).

**Lo común:** los robots **no estaban diseñados para coordinarse** — el ejercicio mide adaptabilidad de software más que mecánica.

---

## 3. Estado actual del código — mapeo task → cobertura

> Inspección de [`software/teensy/firmware/src/main.cpp`](../../software/teensy/firmware/src/main.cpp) y [`software/raspberry/final_rpi/Main.py`](../../software/raspberry/final_rpi/Main.py) al 2026-05-10.

| Task | ¿Cubierto hoy? | Dónde vive | Plug-and-play |
|---|---|---|---|
| Seguir línea | ✅ | `Main.py:577-689` (linea), `main.cpp:1062-1077` (case 7) | No — entremezclado |
| Verde izq/der/doble | ✅ | `Main.py:609-639`, `main.cpp:935-1061` (case 1, 5, 6, 14) | No |
| Gap (línea cortada) | ⚠️ Parcial | implícito en linetrack | No — sin recovery dedicado |
| Speed bump | ⚠️ Implícito | el robot pasa por encima sin lógica | N/A |
| Rampa | ✅ Adaptación de velocidad | `main.cpp:628-641` (`ajustarVelocidadPorPendiente`) | No |
| Obstáculo | ✅ | `main.cpp:937-973` (case 1) | No |
| Seesaw | ❌ No | — | — |
| Bridge / túnel | ⚠️ Sin lógica específica | confía en linetrack | N/A |
| Línea plateada → zona | ✅ | `Main.py:644-672`, `main.cpp:975-1045` (case 2) | No |
| Recolección víctima | ✅ | `Main.py:485-525`, `main.cpp:1129-1186` | No |
| Depósito por color | ✅ | `Main.py:493`, `main.cpp:1196-1220` | No |
| LED estadio (regla 2026) | ❌ No | — | — |
| Víctimas falsas (regla 2026) | ❌ No | YOLO entrenado solo con clases reales | — |
| Comms inter-robot (BT/ZigBee) | ❌ No | — | — |
| Rol "líder/seguidor" | ❌ No | — | — |
| Mode override en boot | ❌ No | hardcoded `estado='esperando'` | — |
| Tests parametrizados aislados | ❌ No | sketches sueltos en `test/` | — |

**Conclusión rápida:** el robot **resuelve la corrida estándar bien**. Pero no hay forma simple de aislar habilidades, ni de reaccionar a tasks nuevos del comité.

---

## 4. ¿Por qué es rígido? — patrones que veo en el código

### 4.1 Acciones del Teensy hardcoded en switch case

[`main.cpp:935-1125`](../../software/teensy/firmware/src/main.cpp#L935-L1125) tiene un `switch (action)` con 7 cases (1, 2, 5, 6, 7, 12, 14). Cada case es un bloque imperativo con `runTime/runAngle/runDistance` mezclado con lógica de transición. Para agregar una acción nueva (e.g. "modo seesaw"):

1. Agregar nuevo `green_state` en RPi.
2. Mapear a nuevo `action` en `main.cpp:900-934`.
3. Agregar nuevo `case N:` con lógica imperativa.
4. Reflashear, probar, debug.

No hay "tabla de comportamientos" parametrizable.

### 4.2 Estado distribuido y global

El estado vive **en cuatro lugares** que tienen que mantenerse sincronizados:
- `estado` en `Main.py:32` (global Python).
- `rutina` en `main.cpp:64` (global C++ string).
- `action` en `main.cpp:58` (global C++ int).
- `green_state` (canal serial compartido).

Coordinar cambios de estado nuevos es frágil — un branch que solo modifica uno de los cuatro deja al sistema en estado inconsistente.

### 4.3 `green_state` mezcla detección con comando

El campo `green_state` lleva a veces:
- "Lo que la Pi DETECTA" (verde izq, plata, etc.).
- "Lo que la Pi LE ORDENA AL Teensy" (recolectar, depositar, ...).

Conceptualmente son dos canales distintos. Tenerlos mezclados hace que `green_state == 7` signifique "recolectar pelota plateada" pero también puede significar "se acercó la cámara a una plateada". El Teensy infiere la intención por el modo (`rutina == "rescate"` vs `"linea"`). Si quisiéramos un Technical Challenge donde la Pi ordene "ahora hacé seesaw aunque no detectaste plateado", no tenemos código limpio para hacerlo sin pisar lógica existente.

### 4.4 Sin entrada de configuración runtime

El robot arranca con `estado='esperando'` y `rutina='linea'`. **No hay forma** de decirle al boot:
- "Hoy probamos solo seesaw, ignorá visión".
- "Hoy probamos solo recolección, salteá línea".
- "Hoy sos robot B en SuperTeam, esperá señal del robot A".

Para cambiar eso, hay que editar `Main.py` o `main.cpp` y reflashear.

### 4.5 Sin abstracción de "skill" reutilizable

`runDistance`, `runAngle`, `runTime` son primitivas. Pero **no hay** funciones componibles tipo:
- `seguir_linea(timeout=5000) -> done/timeout/error`
- `escalar_rampa() -> done/error`
- `pasar_seesaw() -> done/timeout`
- `recoger_pelota(color) -> done/no_encontrada`
- `cruzar_gap() -> done/perdido`

Cada vez que se necesita una de esas habilidades en un contexto nuevo, se escribe inline.

### 4.6 RPi sin canal inter-robot

El código de Pi **no usa Bluetooth ni ZigBee**. La RPi 4B tiene Bluetooth class 2 hardware-disponible, pero no hay módulo Python que lo use. Para SuperTeam, hay que armar todo desde cero.

### 4.7 Calibración hardcoded

Umbrales HSV en `Main.py:36-43` están hardcoded. Cambio de luz del estadio = cambio de código + reflashear. No hay archivo `calibration.json` ni rutina de calibración persistente. (Esto está parcialmente cubierto por issue de visión, pero impacta tasks: si un challenge tiene luz distinta, el robot puede fallar.)

---

## 5. Temas a analizar — propuestas

> Cada tema con riesgo-de-no-cambiar (¿qué pasa si no lo hago?), riesgo-de-cambiar (¿qué se rompe?), tiempo realista (incluye banco + pista, no solo typing) y pregunta concreta.

### TEMA 1 — Boot mode flag en RPi (`--mode <linea|seesaw|rescate|superteam>`)

**Qué observamos.** `Main.py` arranca siempre en `estado='esperando'` y `rutina='linea'`. No acepta argumentos ni lee configuración.

**Por qué lo flagueamos.** Cualquier Technical Challenge que requiera arrancar en otro modo pide editar el script. En 24 hs antes de competencia, eso es presión innecesaria.

**Riesgo de NO cambiar.** Medio. Si cae un challenge raro (e.g. "solo seesaw"), perdemos tiempo de bench haciendo edits manuales. Probabilidad alta porque casi siempre cae al menos un Technical Challenge en RCJ international.

**Riesgo de cambiar.** Bajo. Es agregar `argparse` o leer `config.json` al inicio y mapear a un dict de estados iniciales. No toca lógica existente; el modo default sigue siendo el actual.

**Fix propuesto.**
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--mode", default="run_completo",
                    choices=["run_completo", "linea_solo", "rescate_solo", "seesaw", "superteam_a", "superteam_b"])
args = parser.parse_args()

if args.mode == "linea_solo":
    estado = 'linea'   # arranca en linea, no esperando
elif args.mode == "rescate_solo":
    estado = 'rescate'
# etc.
```

**Estimación de tiempo.**
- Diseño + escritura: 30 min.
- Test en banco (cada modo arranca correcto): 30 min.
- Test en pista parcial (modo `run_completo` no se rompió): 30 min.
- Anotar en TEST_LOG.md: 5 min.
- **Total: ~90 min**.

**Pregunta para el equipo.** ¿Conviene atacarlo ahora antes del próximo ensayo (es el de mayor ROI), o esperar a que caiga un Technical Challenge concreto?

---

### TEMA 2 — "Skill registry" mínimo en Teensy

**Qué observamos.** El switch `case` en `main.cpp:935-1125` mezcla acciones puntuales con transiciones de estado. Cada `action` nueva requiere editar el switch.

**Por qué lo flagueamos.** Si el Technical Challenge pide combinar habilidades en orden distinto (e.g. "rampa → recolección → rampa"), hay que escribir un nuevo case con la secuencia.

**Riesgo de NO cambiar.** Bajo-Medio. La cantidad de combinaciones posibles es grande, pero los Technical Challenges suelen ser pruebas aisladas, no combinaciones complejas. Vivible si el equipo tiene tiempo de hackear.

**Riesgo de cambiar.** Medio. Tocar el switch es tocar el corazón del robot. Si el refactor se hace mal, se pierde la lógica de la corrida estándar. Plan de rollback: revertir commit + reflashear firmware previo.

**Fix propuesto.** Un primer paso muy chico — extraer cada `case` a una función `void skill_xxx()`:

```cpp
// skills.h
void skill_linetrack();
void skill_obstaculo_random();
void skill_giro_verde_izq();
void skill_giro_verde_der();
void skill_giro_180_doble_verde();
void skill_zona_rescate_init();
// ... etc

// main.cpp loop:
switch (action) {
  case 1:  skill_obstaculo_random(); break;
  case 5:  skill_giro_verde_der(); break;
  case 6:  skill_giro_verde_izq(); break;
  case 7:  skill_linetrack(); break;
  // ... etc
}
```

Sin cambiar comportamiento, queda preparado para Fase 2 (registry pluggable).

**Estimación de tiempo.**
- Refactor mecánico (extraer 7 funciones): 1 h.
- Verificar compila + diff de comportamiento (debe ser cero): 30 min.
- Test en banco — corrida completa para confirmar no regresión: 1 h.
- Test en pista — 2 corridas validando no regresión: 1 h.
- Anotar TEST_LOG.md: 10 min.
- **Total: ~3 h 40 min**.

**Pregunta para el equipo.** ¿Es buen momento para este refactor? Es de mayor riesgo que TEMA 1. Conviene hacerlo SOLO si hay 2-3 días de pista disponibles para validar que nada se rompió.

---

### TEMA 3 — Archivo `tasks.yaml` con secuencias parametrizables

**Qué observamos.** Las secuencias largas (e.g. la rutina de `case 2` para entrar a zona de rescate, líneas 975-1045) están hardcoded en C++ con valores literales (`runTime(20,FORWARD,0,1500)`, `runAngle(30,FORWARD,45)`, etc.).

**Por qué lo flagueamos.** Si el comité cambia distancias (e.g. "la zona empieza 30 cm antes este año"), hay que recompilar.

**Riesgo de NO cambiar.** Bajo. Hoy las distancias funcionan. Cambia si el comité modifica geometría.

**Riesgo de cambiar.** Medio. Parser YAML en Teensy es factible pero suma código. Alternativa más barata: mantener constantes en un header `parametros.h` que sí esté fácil de tunear sin tocar lógica.

**Fix propuesto (versión barata).** Mover todos los magic numbers de secuencias a un header:

```cpp
// parametros.h
namespace Rescate {
    constexpr int AVANCE_PRE_PARED_MS = 1500;
    constexpr int RETROCESO_POST_PARED_MS = 1000;
    constexpr int GIRO_INICIAL_DEG = 45;
    constexpr int AVANCE_POS_GIRO_MS = 3000;
}

// main.cpp
runTime(20, FORWARD, 0, Rescate::AVANCE_PRE_PARED_MS);
```

YAML pluggable es una versión más ambiciosa, **no antes del mundial**.

**Estimación de tiempo (versión barata).**
- Identificar todos los magic numbers de secuencias: 30 min.
- Mover a header y reemplazar callsites: 45 min.
- Compilar + diff de binario (debe ser idéntico salvo nombres): 15 min.
- Test corrida completa: 1 h.
- TEST_LOG: 10 min.
- **Total: ~2 h 40 min**.

**Pregunta para el equipo.** ¿El parámetro que más cambian entre ensayos es alguno específico (e.g. el ángulo inicial)? Si sí, podemos partir solo ese y dejar el resto.

---

### TEMA 4 — Soporte SuperTeam: comms inter-robot vía Bluetooth class 2

**Qué observamos.** No hay código de Bluetooth, ZigBee ni ningún canal inter-robot en el repo.

**Por qué lo flagueamos.** Si en mundial cae un SuperTeam Challenge, **partimos de cero**. Mínimo 4-6 horas de scaffolding.

**Riesgo de NO cambiar.** Medio. SuperTeam suele caer en mundial; perderlo es perder puntaje y aprendizaje.

**Riesgo de cambiar.** Medio. Bluetooth en RPi 4B es estable pero requiere `pybluez` o `bleak`. Hay que diseñar protocolo, manejar timeouts, debug en banco con dos Pi.

**Fix propuesto.** Stub mínimo:

```python
# software/raspberry/final_rpi/superteam.py
import bleak  # o pybluez
class SuperTeamChannel:
    def __init__(self, role: str):  # 'leader' | 'follower'
        self.role = role
    async def announce_state(self, state_dict): ...
    async def wait_for_signal(self, signal_name, timeout=5.0): ...
```

Sin protocolo todavía cerrado — solo "andamio" para que el día del challenge sea integrar, no diseñar.

**Estimación de tiempo (stub + test inter-Pi).**
- Investigar libs: 30 min.
- Stub y test ping-pong entre dos Pi: 2 h.
- Integrar como módulo opcional en `Main.py` (no cambia comportamiento si no se usa): 1 h.
- Test que el robot solo (sin BT) sigue funcionando: 30 min.
- **Total: ~4 h**.

**Pregunta para el equipo.** ¿Vale la pena armar el stub aunque no sepamos qué pedirá el challenge? La alternativa es esperar y armar todo el día del torneo (alta presión). Mi opinión: stub vale la pena.

---

### TEMA 5 — Detección de víctimas falsas (regla 2026)

**Qué observamos.** [Reglas RCJ 2026 §2](https://junior.robocup.org/wp-content/uploads/2026/02/RCJRescueLine2026-final.pdf) introducen "víctimas falsas" en zona de evacuación. El YOLO actual del repo (`software/raspberry/AI/`) parece entrenado solo con clases reales (negro, plata, rojo, verde alto).

**Por qué lo flagueamos.** En mundial puede aparecer una pelota similar a la víctima pero distinta (color levemente diferente, peso, conductividad). Si el modelo no la distingue, **el robot recoge falsas y pierde tiempo** (no hay penalización pero tampoco puntos).

**Riesgo de NO cambiar.** Medio-Alto. Probabilidad razonable de que aparezca; impacto: pérdida de puntos.

**Riesgo de cambiar.** Medio. Reentrenar modelo requiere dataset (que no tenemos) o dataset sintético. Alternativa: validación posterior por sensor de color o ToF dentro de la pinza.

**Fix propuesto.** Doble validación post-recolección. Antes de cerrar la pinza:
1. YOLO confirma clase.
2. Sensor de color (APDS9960) ya existente lee y compara con perfil esperado de la víctima real.
3. Si no matchea → soltar y marcar como falsa.

**Estimación de tiempo.**
- Diseño de protocolo de validación: 30 min.
- Implementar lectura de color en pinza (sensor ya existe en el robot): 1 h.
- Test con 4 pelotas (2 reales, 2 falsas pintadas levemente distintas): 2 h.
- Integrar y verificar no regresión en víctimas reales: 1 h.
- TEST_LOG: 15 min.
- **Total: ~4 h 45 min**.

**Pregunta para el equipo.** ¿Tenemos pelotas para simular falsas en banco? Si no, conseguirlas es prerequisito.

---

### TEMA 6 — Detección de LED en pared de zona de evacuación (regla 2026)

**Qué observamos.** [Reglas RCJ 2026 §1.1](https://junior.robocup.org/wp-content/uploads/2026/02/RCJRescueLine2026-final.pdf) agregan un LED blanco en pared de zona de evacuación a 10 cm de altura. La posición se calibra in-situ sin aviso previo.

**Por qué lo flagueamos.** El sistema de visión actual no busca LED — busca contornos de víctimas y zonas. La luz puntual puede saturar localmente la cámara y romper la detección de víctimas cercanas.

**Riesgo de NO cambiar.** Medio. Saturación local impacta la calidad de detección YOLO en esa zona.

**Riesgo de cambiar.** Bajo (mitigación). Bastaría con auto-exposure compensation o un filtro CLAHE local.

**Fix propuesto.**
1. Ejercer auto-exposure (`cv2.CAP_PROP_AUTO_EXPOSURE = 1`).
2. Aplicar CLAHE selectivo en la zona donde el promedio de luminancia supera umbral.
3. (Opcional) Detectar la posición del LED y enmascararlo en pre-proceso.

**Estimación de tiempo.**
- Probar auto-exposure (config 5 min) y medir efecto en YOLO: 1 h.
- Implementar CLAHE selectivo si lo anterior no alcanza: 2 h.
- Test con LED real en la pista: 2 h.
- **Total: ~5 h** (la mitad si auto-exposure alcanza).

**Pregunta para el equipo.** ¿Tenemos LED blanco y batería para simular este escenario? ¿Cómo era en Roboliga 2025 — sufrió el robot con luces del estadio?

---

### TEMA 7 — Modos de "test aislado" como sketch suelto

**Qué observamos.** [`software/teensy/firmware/test/`](../../software/teensy/firmware/test/) tiene archivos sueltos (`blink.cpp`, `motors_move.cpp`, `clawLibTest.cpp`, etc.) pero NO son tests `pio test` formales — son sketches manuales que reemplazan `main.cpp` cuando se compilan solos.

**Por qué lo flagueamos.** Para Technical Challenges donde queremos probar un solo subsistema, los sketches sirven, pero son **archivos espejados** del firmware principal — fácil que diverjan (e.g. `motors_move.cpp` use ya un pinout viejo).

**Riesgo de NO cambiar.** Bajo. Son herramientas de bring-up, no de competencia. Pero pueden engañar al equipo si los pines de un sketch no coinciden con los de producción.

**Riesgo de cambiar.** Bajo. Centralizar definiciones de pines en un header `pinout.h` que tanto `main.cpp` como los sketches incluyan.

**Fix propuesto.**
```cpp
// software/teensy/firmware/include/pinout.h
namespace Pin {
    constexpr int MOTOR_BL_PWM = 29;
    constexpr int MOTOR_BL_DIR = 28;
    // ... todos los pines
    constexpr int SWITCH = 32;
    constexpr int BUZZER = 31;
}
```

`main.cpp` y todos los sketches incluyen este header.

**Estimación de tiempo.**
- Identificar todos los `#define` y literales de pin en main.cpp + sketches: 30 min.
- Crear header y reemplazar: 45 min.
- Compilar todos los sketches y main: 30 min.
- Test corrida completa: 1 h.
- **Total: ~2 h 45 min**.

**Pregunta para el equipo.** ¿Hay sketches del directorio `test/` que el equipo usa frecuentemente? Si sí, hacerlo cuanto antes evita el bug "el sketch funciona pero el robot no" por divergencia de pines.

---

## 6. Propuesta de arquitectura "task-pluggable" (incremental)

> No es un rewrite. Es un camino para llegar gradualmente a un sistema más flexible sin tocar lo que funciona.

### Fase A — Capa de configuración runtime (TEMAS 1, 3 versión barata, 7)

Permite **arrancar el robot en distintos modos** sin reflashear:

```
┌─────────────────────────────────────┐
│  RPi: Main.py --mode <X>            │
│  → estado inicial configurable      │
│  → archivo tasks.yaml opcional      │
└──────────────┬──────────────────────┘
               │ serial existente, sin cambios
               ▼
┌─────────────────────────────────────┐
│  Teensy: parametros.h centralizado  │
│  + pinout.h centralizado            │
│  + tests/ alineados al firmware     │
└─────────────────────────────────────┘
```

**Tiempo total estimado Fase A:** ~7-8 horas.

### Fase B — Skills componibles (TEMA 2)

Refactor del switch en main.cpp para que cada acción sea una función nombrada. Sin cambiar comportamiento, queda terreno preparado.

**Tiempo total estimado Fase B:** ~4 horas.

### Fase C — SuperTeam channel (TEMA 4)

Stub Bluetooth para que el día del challenge sea integrar, no diseñar.

**Tiempo total estimado Fase C:** ~4 horas.

### Fase D — Adaptación a reglas 2026 (TEMAS 5, 6)

Falsas víctimas + LED en pared. Estos son específicos de las reglas nuevas.

**Tiempo total estimado Fase D:** ~10 horas.

### Fase E (post-mundial) — Registry dinámico, YAML, BT protocol cerrado

Si Fases A-D son suficientes, no se hace antes del mundial. Riesgo de regresión es alto en una semana de competencia.

---

## 7. Plan de migración recomendado

**Antes del próximo ensayo:** TEMAS 1 (mode flag) y 7 (pinout central). Bajo riesgo, ROI alto.

**Antes de mundial:** TEMAS 5 (falsas víctimas) y 6 (LED). Son obligatorios si se aplican las reglas 2026.

**Si hay tiempo extra:** TEMA 4 (SuperTeam stub) — vale el seguro aunque no se use.

**Post-mundial:** TEMAS 2 (skill registry) y 3 (YAML pluggable). Refactor más sano sin presión de fechas.

---

## 8. Issues nuevos a abrir

| ID propuesto | TEMA | Riesgo no cambiar | Riesgo cambiar | Tiempo estimado |
|---|---|---|---|---|
| §5 TEMA 1 | Boot mode flag en RPi | Medio | Bajo | ~90 min |
| §5 TEMA 2 | Skill registry mínimo en Teensy | Bajo-Medio | Medio | ~3 h 40 min |
| §5 TEMA 3 | Magic numbers a `parametros.h` | Bajo | Medio | ~2 h 40 min |
| §5 TEMA 4 | SuperTeam channel (BT stub) | Medio | Medio | ~4 h |
| §5 TEMA 5 | Validación de víctimas falsas | Medio-Alto | Medio | ~4 h 45 min |
| §5 TEMA 6 | Auto-exposure + CLAHE para LED | Medio | Bajo | ~5 h |
| §5 TEMA 7 | `pinout.h` central | Bajo | Bajo | ~2 h 45 min |

Más un **meta-issue** que linkee a todos.

---

## 9. Referencias

- [RCJ Rescue Line 2026 final rules](https://junior.robocup.org/wp-content/uploads/2026/02/RCJRescueLine2026-final.pdf) — reglas oficiales (PDF).
- [Forum: 2026 Rescue Line Rule Changes](https://junior.forum.robocup.org/t/2026-rcj-rescue-line-rule-changes/5011) — discusión de cambios vs 2025.
- [RCJ Rescue Line 2025 final](https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf) — reglas previas para comparar.
- [`docs/es/comunicacion-rpi-teensy.md`](comunicacion-rpi-teensy.md) — descripción base del protocolo.
- [`docs/es/analisis-integral-comunicacion-2026-05-10.md`](analisis-integral-comunicacion-2026-05-10.md) — análisis previo de comms.
- [`research/completed/2026-02-23-analisis-campeones-mundiales-rescue-line.md`](../../research/completed/2026-02-23-analisis-campeones-mundiales-rescue-line.md) — investigación de equipos top.

---

*Análisis dirigido por @gviollaz, asistido por Claude Code (Opus 4.7). Fecha: 2026-05-10. Marco: TEMAS A ANALIZAR — cada finding tiene riesgo-no-cambiar, riesgo-cambiar y tiempo realista. El equipo decide caso por caso.*
