# Protocolo del sábado — guion, no sesión de desarrollo

Quedan **como máximo dos sábados** con el robot. Este documento existe para que
el sábado se ejecute como un guion: orden fijo, criterio GO/STOP escrito antes,
un solo parámetro tocable por fase, y vuelta al baseline en un comando.

**Regla que gobierna todo:** si una fase da STOP, no se improvisa la siguiente.
Se anota, se vuelve al baseline y se pasa a la fase que no dependa de la que
falló.

---

## Lo primero: qué se puede ejecutar y qué no

**Actualizado 2026-08-24.** Estado por fase:

| fases | estado |
|---|---|
| **0 a 3** | listas. Preflight, runtime, cámara real y geometría `d_eje` |
| **4** | **desbloqueada** — [`shadow_pi.py`](shadow_pi.py) existe (commit `a327560`) |
| **5 a 8** | **bloqueadas**: lazo cerrado con la candidata manejando |

Lo que falta para 5–8, y por qué:

- [`Main.py`](Main.py) corre la visión **vieja** (centroide + `atan2`), no
  `SinBranch`. No hay bandera para elegir.
- [`telemetria_vision.py`](telemetria_vision.py) está cableado y funciona, pero
  sus 18 campos son los de la visión vieja. **Ni un campo de la candidata**:
  nada de `target_raw` / `cap` / `low_proj` / `final`, ni `reason` del spatial.
- **Una sola cámara no la abren dos procesos**, así que un shadow «en paralelo a
  producción» no se resuelve con un script aparte: hay que compartir el frame
  dentro del mismo loop.

Decir esto ahora vale una sesión física. Descubrirlo el sábado a las 9 de la
mañana la quema entera.

---

## Antes de salir de casa

```bash
git -C ~/rcj-2026-rescue-line-iita-salta-robocup fetch origin && git -C ~/rcj-2026-rescue-line-iita-salta-robocup checkout collab/nuevo-code && git -C ~/rcj-2026-rescue-line-iita-salta-robocup pull --ff-only
```

Llevar: **hoja grande de papel** (A3 o cartulina), **cinta de papel**, **lápiz**,
**regla o cinta métrica**, **cinta negra** de la de la pista, plomada
improvisada (hilo + tuerca) y el cargador de la Pi.

---

## FASE 0 — Preflight · 10 min · el robot NO se toca

```bash
cd ~/rcj-2026-rescue-line-iita-salta-robocup/software/raspberry/final_rpi && python3 preflight_sabado.py
```

Chequea rama/SHA/árbol limpio, dependencias (**`scikit-image`: sin eso la
candidata no corre**), modelo de Pi, `vcgencmd get_throttled` bit por bit,
temperatura de arranque, disco, reloj, si el servicio tiene la cámara tomada,
fps real de cámara, puerto de la Teensy, y que la candidata levante y procese
frames.

| | |
|---|---|
| **GO** | ningún bloqueante (código de salida 0) |
| **STOP** | cualquier bloqueante. Se resuelve antes de gastar tiempo de robot |
| **parámetro tocable** | ninguno |
| **anotar** | el SHA que imprime, en la primera línea del log del día |

Si dice under-voltage **actual**: cambiar fuente antes de seguir. Todo número
medido bajo under-voltage es basura.

---

## FASE 1 — Runtime sostenido · 12 min · robot quieto, motores apagados

Esto va **antes** de mover el robot. Es el P0 que quedó pendiente.

```bash
python3 bench_runtime.py --modo sostenido --minutos 10 --json bench_runtime_pi.json --csv bench_runtime_pi.csv 2>&1 | tee bench_runtime_pi.txt
```

Ver [`BENCH_RUNTIME.md`](BENCH_RUNTIME.md) para el detalle. El veredicto está
fijado en el código y gobierna **sólo** `T_algorithm`.

| veredicto | qué se hace |
|---|---|
| **VERDE** | congelar. No optimizar por deporte. Seguir a FASE 2 |
| **AMARILLO** | seguir a FASE 2, pero anotar. Primera palanca, y es gratis: sacar `poi_component` (6,3–6,7 %, sólo lo lee `draw_panel`) |
| **ROJO** | **STOP de la línea candidata.** El sábado se convierte en sesión de perfilado. NO se optimiza a ciegas: se mira la tabla por etapa **del JSON de la Pi** y se ataca la etapa dominante *ahí* |

| | |
|---|---|
| **parámetro tocable** | ninguno |
| **anotar** | veredicto, p50/p95/p99, % > 30 ms, temperatura final, `get_throttled` final |

Si aparece throttling térmico a los 10 minutos, eso **es** el resultado: en
competencia la corrida dura menos, pero la Pi ya viene caliente de las pruebas.

---

## FASE 2 — Cámara real: fps, edad de frame y `seq` · 5 min · robot quieto

```bash
sudo systemctl stop iita-robot
python3 bench_runtime.py --videos hist.avi --warmup 100 --camara 900 --camara-wh 160x120 --json bench_runtime_pi_camara.json
```

Da los tres números separados: `T_algorithm`, `T_frame_age`, `T_observed`, más
frames reprocesados y `seq` saltados, en los dos patrones (último disponible /
esperar frame nuevo).

| | |
|---|---|
| **GO** | fps real ≥ 25, 0 frames nulos |
| **STOP** | fps < 25, o frames nulos, o `seq` saltados > 0 de forma sostenida → es problema de cámara/USB/V4L2, no de algoritmo. No tiene sentido ir a pista con esto |
| **parámetro tocable** | resolución pedida (`--camara-wh`), sólo para diagnosticar |
| **anotar** | fps real, `T_frame_age` p50/p95 en modo `nuevo`, % reprocesados en modo `libre` |

> Si `T_algorithm` sale VERDE pero `T_frame_age` sale alto, el problema es la
> captura y **no** el skeleton. Optimizar el algoritmo en ese caso sería un error.

---

## FASE 3 — Geometría: medir `d_eje` · 20 min · el robot pivotea en el lugar

Es el dato que tiene suspendido a **T4** desde hace semanas, y el único que no
se puede sacar de ningún video ni de la telemetría (`steer` correlaciona con
`gz` por construcción: es circular). Procedimiento completo en el encabezado de
[`medir_eje.py`](medir_eje.py).

**Paso 0 — encontrar el eje de rotación REAL.** Con 4 ruedas fijas el centro de
rotación no es el centro geométrico: se corre hacia el eje delantero y depende
de la superficie.

1. Hoja de papel bajo el robot, pegada al piso con cinta.
2. Marcar en el papel **dos** puntos del chasis (plomada sobre el centro del
   paragolpes y sobre el centro trasero).
3. Pivotear en el lugar ~90°.
4. Marcar los **mismos dos** puntos en la nueva pose.
5. Unir cada punto con su nueva posición → dos segmentos. Trazar la **mediatriz**
   de cada uno. Se cruzan en el centro de rotación.
6. Repetir pivoteando al otro lado y promediar.

> Si los dos cruces difieren más de ~1 cm, **anotarlo**: el centro de rotación
> no es estable, y eso es un hallazgo en sí mismo sobre el skid steer.

**Paso 1 — foto longitudinal** (cinta negra a lo largo del eje de avance):

```bash
python3 medir_eje.py --capturar --tipo longitudinal --ancho-cinta-cm 1.9
```

**Paso 2 — travesaños** (cinta negra perpendicular; la regla mide del centro de
rotación al borde **más cercano** de la cinta). Elegir distancias que caigan
repartidas entre la fila 119 y la fila 40:

```bash
python3 medir_eje.py --capturar --tipo travesano --dist-cm 25
python3 medir_eje.py --capturar --tipo travesano --dist-cm 35
python3 medir_eje.py --capturar --tipo travesano --dist-cm 50
python3 medir_eje.py --capturar --tipo travesano --dist-cm 70
```

**Paso 3 — ajustar:**

```bash
python3 medir_eje.py --ajustar
```

El ajuste es una recta: `D = k·(1/(v−v_h)) + d_eje`, y **la ordenada al origen
es `d_eje`**. La matemática ya está validada offline (`--simular`): con 2,5 mm
de error de regla recupera `d_eje` con < 0,32 cm de error.

| | |
|---|---|
| **GO** | R² ≥ 0,98, `d_eje` > 0, n ≥ 3 travesaños |
| **STOP** | R² < 0,98 → el piso no es plano, o la regla no midió desde el centro de rotación, o las filas no son del mismo borde. Repetir, no forzar |
| **parámetro tocable** | las distancias de los travesaños |
| **anotar** | `d_eje`, `k`, `v_h` medido vs el `+9,0` de `birdeye`, R², RMS |

Guardar las fotos `eje_*.png` y `eje_*_anotada.png`: son la evidencia.

---

## FASE 4 — Shadow log-only sobre cámara viva · DESBLOQUEADA

**Qué sería:** empujar el robot a mano sobre la línea, con la candidata
corriendo sobre frames en vivo y registrando, **sin mandar nada a la Teensy**.
Contesta si la candidata se comporta igual sobre la cámara de hoy (luz, foco,
exposición de la sede) que sobre los videos de agosto.

**Ya existe el runner:** [`shadow_pi.py`](shadow_pi.py) (commit `a327560`). No
abre el puerto serie y ni siquiera importa `pyserial`, así que no puede mandar un
comando ni por error. Registra las cinco etapas más `seq`/`frame_age_ms`.

```bash
sudo systemctl stop iita-robot
python3 shadow_pi.py --seg 90 --grabar shadow_pi_$(date +%H%M).avi
```

Validado contra el baseline: sobre `hist.avi` da huecos 47 y saltos 37, que es
exactamente lo que reporta el A/B.

**GO/STOP cuando exista:** GO si la disponibilidad de target sobre cámara viva
queda dentro de ±3 puntos de la de replay. STOP si la máscara se degrada — eso
sería calibración de color/luz, no arquitectura, y se ataca con
[`calibrador_verde.py`](calibrador_verde.py) / `medir_camara.py`, no tocando el
skeleton.

---

## ⛔ FASES 5 a 8 — Lazo cerrado · BLOQUEADAS

Especificación completa, para que estén listas apenas exista el runner. **No se
tocan cinco cosas a la vez: una fase, un parámetro, un log.**

### FASE 5 — Recta
Arrancar en recta larga. **GO:** completa sin pérdida y sin inversiones de steer
con banda muerta de 10°. **STOP:** cualquier inversión en recta → es percepción
o `d_eje`, no control.
**Parámetro tocable:** velocidad base, y sólo ella.

### FASE 6 — Curva positiva ya conocida
El equivalente físico de `lineal` f818–830, la que el robot **sí** completó.
Control positivo: si esto se rompe, se rompió algo que funcionaba.
**GO:** la completa. **STOP:** no la completa → vuelta inmediata al baseline.
**Parámetro tocable:** ninguno. Es control, no experimento.

> Recordatorio del traspaso: en `lineal` f~824 el target quedó en (2,95) con
> steer ~+87° y **estuvo bien**. Steer extremo no es automáticamente un error.
> No limitar magnitud «porque parece mucho».

### FASE 7 — Curva cerrada histórica
La que motivó todo (`hist` f1398–1417). **GO:** la completa, o falla de un modo
**distinto** al histórico. **STOP:** falla igual → clasificar antes de tocar
nada.
**Parámetro tocable:** ninguno en la primera pasada. Primero se mira el log.

### FASE 8 — Pérdida y recuperación
Provocar pérdida deliberada (tapar la línea, arrancar fuera). **GO:** recupera
sin quedar girando. **STOP:** se queda girando → es el `SpatialTargetGuard`
devolviendo `REACQ_PENDING` sin salida; se anota, no se parchea en la pista.
**Parámetro tocable:** `max_step` del spatial guard (24/30 px), uno solo.

### Clasificación obligatoria de cada falla

Antes de tocar nada, cada falla se etiqueta con **una** de estas:

`PERCEPTION` · `PATH/TRACKING` · `TARGET→STEER` · `TIMING` · `RECOVERY` ·
`MECHANICS`

Sin etiqueta no se toca código. Es lo que evita arreglar el síntoma equivocado.

---

## Logs mínimos por frame

Lo que ya existe: [`telemetria_vision.py`](telemetria_vision.py), encendido con
`TLM_VISION=/ruta/corrida.csv`, se une con el CSV del Teensy por `i` == `rxf`.
Nunca lanza excepción hacia el lazo de visión y está apagado por defecto.

**Estado al 25-ago, tarde:** las cinco etapas **ya están**. El CSV pasó de 18 a
**42 columnas**, todas agregadas al final para que un registro viejo se siga
leyendo y la clave `i` == `rxf` no se mueva.

| campo | por qué | estado |
|---|---|---|
| `t_mono_ns` | cruzar con el Teensy sin ambigüedad | **falta** — hoy hay `t_ms`, monotónico pero relativo al arranque del registro |
| `seq`, `frame_age_ms` | distinguir CPU lenta de frame viejo (FASE 2) | **falta** — salen de la cámara, no de la visión |
| `raw_x/y` | salida de `path_target` | ✅ |
| `cap_x/y` | después del cap de continuidad | ✅ |
| `geo_x/y` | después de low projection (`target_geometric` de V4) | ✅ |
| `bra_x/y` | después del guard de rama | ✅ |
| `tg_x/y` | después de `SpatialTargetGuard` | ✅ |
| `guard_sp` | `ACCEPT` / `SPATIAL_LIMIT` / `REACQ_*` / `NO_SKELETON` | ✅ |
| `vl_estado` | HIGH / MEDIUM / LOW / LOW_FORWARD / SIN_CERCA / PERDIDA | ✅ |
| `ang_env` | lo que realmente se mandó | ✅ (ya existía) |
| `gyro_z`, `yaw`, `motor_set`, `rpm` | del lado Teensy | fuera de este archivo |

Son **las cinco etapas** del traspaso (`raw` → `cap` → `geo` → `bra` → `tg`), no
cuatro. Sin ellas un log no sirve para clasificar la falla.

> **Ojo con `geo_x/y`.** `target_geometric` de V4 **no** es el geométrico crudo:
> ya viene con el cap de continuidad y la proyección LOW aplicados. El
> geométrico de verdad es `raw_x/y`. Con el nombre viejo, un log habría dicho
> "el planificador eligió esto" cuando en realidad eran dos guards.

Y hay dos banderas más, `razon` y `razon_fl`, que dicen qué guard **corrió**,
que no es lo mismo que qué guard **movió** el target: medido en `hist.avi`, el
cap corrió y movió 294 veces (coinciden), pero `low_proj` corrió 71 veces y sólo
movió el punto en 58. Las otras 13 eligió el mismo punto que ya había.

### Además, la ley de steer

Si se corre con `LEY_STEER=stanley`, el CSV graba también `e_pos`, `psi`,
`t_pos`, `t_psi` y —el que más importa— **`ang_viejo`**, que es lo que la ley de
hoy habría mandado en ese mismo frame.

**Eso hace que el A/B de las dos leyes salga de una sola corrida en lazo
cerrado**, sin correr el robot dos veces y sin comparar dos trayectorias
distintas. Ver la sección 14 del traspaso.

---

## Vuelta al baseline — un comando

El baseline es lo que hay hoy en `main` y es lo que compite si nada mejora.

```bash
sudo systemctl stop iita-robot && git -C ~/rcj-2026-rescue-line-iita-salta-robocup checkout main && sudo systemctl start iita-robot
```

**Cuándo se ejecuta, sin discutir:** si FASE 6 (el control positivo) se rompe, o
si se pierden más de 20 minutos en una sola fase, o si el robot hace algo que no
se entiende dos veces seguidas.

Volver al baseline **no** es abandonar la candidata: es proteger el resto de la
sesión. La candidata se sigue evaluando con los logs que ya se juntaron.

---

## Lo que hay que construir antes

Para desbloquear las fases 4 a 8, en este orden:

1. ~~**`shadow_pi.py`**~~ — **HECHO**, commit `a327560`. FASE 4 desbloqueada.
2. **Campos de candidata en `telemetria_vision.py`** — agregar las columnas de
   arriba manteniendo la promesa de no lanzar excepciones y de estar apagado por
   defecto.
3. **Integración de `SinBranch` en el loop de `Main.py`** detrás de una bandera
   de entorno, para que el frame se comparta (una sola cámara) y se pueda elegir
   visión vieja o candidata sin editar código en la pista. Esto es lo que
   desbloquea las fases 5 a 8, y es lo más delicado: toca producción.

El punto 1 es barato y de riesgo nulo. El punto 3 es la decisión real y conviene
tomarla con el número de FASE 1 en la mano: **si el runtime sale ROJO, integrar
la candidata no tiene sentido todavía.**

---

## Segundo sábado

Debe ser repetición, stress, regresión, distintos arranques, curvas, pérdidas y
recién después verde/T. **Si el segundo sábado seguimos inventando arquitectura
base, llegamos tarde.**

---

*Herramientas de este protocolo: [`preflight_sabado.py`](preflight_sabado.py) ·
[`bench_runtime.py`](bench_runtime.py) · [`medir_eje.py`](medir_eje.py). Ninguna
toca la candidata, el firmware ni el hardware.*
