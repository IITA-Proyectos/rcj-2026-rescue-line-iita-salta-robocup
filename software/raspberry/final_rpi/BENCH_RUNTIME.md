# BENCH RUNTIME — ¿la candidata entra en 30 ms en la Raspberry Pi?

**Estado: banco construido y validado. LA MEDICIÓN EN LA PI ESTÁ PENDIENTE.**
La Pi no estaba accesible cuando se escribió esto (2026-08-23, sin host SSH en
la LAN 192.168.0.0/24). No hay ningún número de Pi en este documento y no debe
inventarse ninguno.

---

## Por qué es P0

La candidata **NUEVO CODE V1 RC** (`SinBranch` = V2 + `SpatialTargetGuard`, sin
el branch guard de V3, ver [`arquitectura_minima.py`](arquitectura_minima.py))
usa `skeletonize` + construcción de grafo + Dijkstra en Python puro por frame.

Los diez videos autónomos corresponden a **100/3 = 33,333 fps** reales del loop,
o sea un presupuesto de **30,00 ms por frame**.

Nunca medimos eso en la Pi. Quedan como máximo **dos sábados** con el robot.
Descubrir el sábado que el loop tarda 45–80 ms/frame inutiliza la candidata
entera y quema una de las dos sesiones físicas. Por eso se mide antes.

---

## El único comando que hay que correr en la Pi

Con la Pi encendida y en red, por SSH:

```bash
cd ~/rcj-2026-rescue-line-iita-salta-robocup && git fetch origin && git checkout collab/nuevo-code && git pull --ff-only && cd software/raspberry/final_rpi && python3 bench_runtime.py --modo sostenido --minutos 10 --json bench_runtime_pi.json --csv bench_runtime_pi.csv 2>&1 | tee bench_runtime_pi.txt
```

Si la ruta del clon en la Pi es otra, lo único que cambia es el primer `cd`.
Los diez `.avi` autónomos están versionados en el repo, así que después de
`git pull` la Pi ya tiene el material: no hay que copiar nada por scp.

Después traer los tres archivos:

```bash
scp pi@<ip-de-la-pi>:~/rcj-2026-rescue-line-iita-salta-robocup/software/raspberry/final_rpi/bench_runtime_pi.{json,csv,txt} .
```

### Segundo comando: cámara real (sólo con la cámara conectada y libre)

Da los dos números que el replay no puede dar: latencia de **captura** sola y
latencia **extremo a extremo** cámara→comando.

```bash
python3 bench_runtime.py --videos hist.avi --warmup 100 --camara 900 --camara-wh 160x120 --json bench_runtime_pi_camara.json
```

### Si falta la dependencia

El banco aborta con código 3 y el comando exacto si no encuentra
`scikit-image`. La candidata **no corre sin él**:

```bash
sudo apt install python3-skimage
```

---

## Qué mide y qué NO mide

* **`algoritmo` = `frame_pi` + `SinBranch.step`.** Es el número que decide: lo
  que paga el robot por frame *una vez que el hilo de cámara le entregó la
  imagen*.
* **El decode del `.avi` se mide aparte y NO cuenta.** En el robot el frame lo
  trae `camthreader.WebcamVideoStream`, no un decoder MJPG. Meterlo en el total
  sería inflar el costo con algo que en competencia no existe.
* **No modifica ningún archivo de la candidata.** Instrumenta con espías
  reversibles (monkeypatch dentro del proceso del banco).
* **Verifica que no cambia lo que mide.** Antes de medir corre 900 frames de
  `hist.avi` con y sin instrumentación y compara la serie de targets. Si no son
  idénticos, **aborta con código 4**. También reporta el overhead del propio
  perfilador.
* **No prueba nada físico.** Es replay open-loop: mide costo computacional, no
  trayectoria.

### Las diecinueve etapas

Tiempo **exclusivo** (con contabilidad de pila, sin doble conteo por anidado):

| # | etapa | qué es |
|---|---|---|
| — | `decode` | lectura del `.avi` — **no cuenta** |
| 1 | `frame_pi` | preprocess a 160×120 |
| 2 | `mask_linea` | threshold + recorte de esquinas + morph close |
| 2b | `cc_candidates` | connected components + stats |
| 3 | `choose_component` | selección de componente (exclusivo) |
| 3b | `component_distance` | distancia componente ↔ referencia |
| — | `fill_contornos` | relleno de huecos internos (`findContours`+`drawContours`) |
| — | `state` | HIGH / MEDIUM / LOW / SIN_CERCA |
| 4 | `skeletonize` | scikit-image |
| 5 | `graph_from_skeleton` | grafo desde el esqueleto |
| 6 | `dijkstra` | Dijkstra en Python puro |
| 6b | `reconstruct` | reconstrucción del path |
| — | `runs_1d` | corridas 1D (en `path_target` y en `poi_component`) |
| 7 | `path_target` | shell geodésica + score (exclusivo) |
| 8 | `percepcion_resto` | **cap de continuidad + low_proj** + bookkeeping |
| 9 | `spatial_guard` | `SpatialTargetGuard` |
| — | `ctrl` | preview de control (slew) |
| — | `poi_component` | POI T/B/L/R — **sólo diagnóstico visual** |
| 10 | `v4_resto` | pegamento de `NuevoCodeV4.step` (exclusivo) |

Metodología: `time.perf_counter_ns()`, warmup de 150 frames por video, sin
`print` dentro de la región medida, telemetría térmica tomada **fuera** del
tramo cronometrado y descontada del wall clock.

---

## Regla del veredicto — fijada ANTES de medir

Está en el código (`V_VERDE_*` / `V_ROJO_*`) y se imprime en cada corrida para
que no se pueda mover después de ver el resultado.

```
ROJO      si p50 >= 30 ms   o   frames>30ms >= 10 %
VERDE     si p95 < 30 ms    y   p99 < 35 ms   y   frames>30ms < 1 %
AMARILLO  cualquier otro caso
```

No alcanza con «p50 < 30 entonces pasa»: un loop con media 22 ms y p99 60 ms
pierde frames justo en las curvas, que es donde el esqueleto se complica.

---

## Qué registrar junto al número

El JSON ya guarda todo esto solo; está listado acá para poder auditarlo:

modelo de Pi · CPU · frecuencias min/max · governor · memoria · versión de
Python / OpenCV / NumPy / scikit-image / SciPy · hilos de OpenCV · SHA de git y
si el árbol estaba sucio · temperatura inicial/final/máxima · frecuencia mínima
observada · `vcgencmd get_throttled` decodificado bit por bit
(under-voltage, capado de frecuencia, throttling, límite blando de temperatura)
· frames medidos · p50/p90/p95/p99/max/media por etapa · % de frames sobre
30/35/40 ms · fps efectivo y fps garantizado por p95 · por video.

El modo `--modo sostenido --minutos 10` repite el dataset varias veces
justamente para que aparezca el throttling térmico si existe: 100 frames no
alcanzan.

---

## Si sale ROJO

**No optimizar a ciegas.** El orden es: mirar la tabla por etapa del JSON de la
Pi, identificar la etapa dominante *ahí* (no la de la PC), y recién entonces
tocar esa etapa.

Dos cosas ya sabidas que conviene tener a mano:

1. **`poi_component` es gratis de eliminar.** Se verificó que `r["poi"]` sólo lo
   lee `draw_panel` ([`nuevo_code_v3.py:394`](nuevo_code_v3.py#L394),
   [`nuevo_code_v4.py:207`](nuevo_code_v4.py#L207)), o sea el overlay de
   diagnóstico. En el robot headless es peso muerto. En el ensayo de PC pesaba
   **6,3–6,7 %** del frame.
2. **El costo está repartido, no concentrado.** Ver la sección siguiente.

Toda optimización tiene que volver a pasar los cuatro controles de siempre:
`hist_exito` 100/100, `lineal_positivo` 73/73, `hist_falla`, y los 10 autónomos
sin regresión en las cinco métricas.

## Si sale VERDE

No seguir optimizando por deporte. Congelar y pasar a preparar el sábado.

---

## Ensayo en PC — NO ES PRUEBA DE NADA

Se corrió en la notebook sólo para validar que el banco funciona. **Una PC x86
no dice nada sobre una Pi.** Se deja registrado porque la *forma* del perfil sí
es información útil.

Máquina: Windows 11, x86-64, Python 3.11.9, OpenCV 5.0.0, NumPy 2.4.6,
scikit-image 0.26.0. 12.400 frames sobre los 10 autónomos.
Evidencia: [`bench_runtime_PC_ensayo.json`](bench_runtime_PC_ensayo.json) (por
defecto, 24 hilos de OpenCV) y
[`bench_runtime_PC_1hilo.json`](bench_runtime_PC_1hilo.json) (`--hilos 1`).

| | `algoritmo` p50 | p95 | p99 |
|---|---|---|---|
| 24 hilos | 1,090 ms | 1,388 ms | 1,849 ms |
| 1 hilo | 1,093 ms | 1,322 ms | 1,496 ms |

Equivalencia instrumentado vs limpio: **900/900 targets idénticos**.
Overhead del perfilador: **+3,6 %** (+0,038 ms sobre un p50 de 1,058 ms).

### Lo que sí se aprende del ensayo

1. **El perfil es PLANO.** Ninguna etapa pasa del ~21 %. Top 5 con `--hilos 1`:
   `skeletonize` 21,2 % · `cc_candidates` 16,2 % · `graph_from_skeleton` 13,2 %
   · `path_target` 11,5 % · `mask_linea` 9,6 %. Si en la Pi diera ROJO, **no hay
   un único cuello de botella para atacar**: habría que sacar varias cosas o
   cambiar de arquitectura. Esto cambia el plan y por eso conviene saberlo antes.
2. **Dijkstra en Python puro NO es el problema.** Era el sospechoso número uno
   del traspaso y pesa **2,8 %**. El grafo del esqueleto es chico. Reescribirlo
   en C/Cython/scipy sería trabajo tirado.
3. **Los hilos de OpenCV no aportan.** 1,090 vs 1,093 ms de p50. A 160×120 el
   paralelismo no compra nada, así que los 4 núcleos de la Pi contra los 24
   hilos de la PC no distorsionan *esta* comparación en particular.
4. **~32 % del frame es intérprete de Python** (`graph_from_skeleton` +
   `path_target` + `runs_1d` + `dijkstra` + `reconstruct` + `choose_component`)
   contra ~68 % en código compilado. **Hipótesis, no resultado:** en ARM sin las
   mismas extensiones SIMD, esa fracción interpretada podría crecer y cambiar el
   ranking. Se confirma o cae con el JSON de la Pi, no acá.

---

*Herramienta: [`bench_runtime.py`](bench_runtime.py). No toca la candidata, no
toca el hardware, no infiere closed-loop desde replay.*
