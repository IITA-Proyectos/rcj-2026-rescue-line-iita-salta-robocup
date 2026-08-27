# PLAN DEL SÁBADO 2026-08-29 — el codo de 90°

**Para Benjamín. ~3 h 30 de robot. Un cambio por vez. Punto de corte a T+150.**

Los tiempos van en `T+minutos` desde que el robot está sobre la pista con batería cargada. Si arrancás 09:00, el punto de corte es 11:30.

---

## Resumen en cuatro renglones

Lo único que rompió el techo de 55° en todo el dataset es **LINE_CODO=1**: dos disparos en `2026-08-26_codo_1.csv`, de −57,0° y −108,5° netos, con ratio abs/neto = 1,00 los dos. La base limpia es **0 de 291 episodios ≥80°** en las 8 corridas sin el flag (p50 7,2°, p99 40,1°, máximo 50,0°). El sábado se va a **encender ese flag tal cual está** y, si se corta corto, a tapar la única razón medida por la que se corta: un frame en el que la Pi dice "no veo la línea" y el firmware lo lee como "estoy centrado".

Todo lo demás queda afuera y abajo digo por qué.

---

## BLOQUE 0 — VIERNES, SIN ROBOT (no gasta ventana)

Cuatro cosas que si no están hechas el viernes, se comen el sábado.

### 0.1 — Tres campos en la cabecera del CSV, más la guarda

Hoy la cabecera imprime `codo=`, `codo_ent=`, `codo_min=`, `codo_max=` pero **NO** imprime `LINE_CODO_ENTRA_MS`, `SALE_MS` ni `VEL`. Dos corridas con 300 y con 250 ms son hoy **indistinguibles en el archivo**. Después de `software/teensy/firmware/src/main.cpp:1349` (la línea de `codo_max=`):

```cpp
DIAG_OUT.print(" codo_ent_ms="); DIAG_OUT.print(LINE_CODO_ENTRA_MS);
DIAG_OUT.print(" codo_sale_ms="); DIAG_OUT.print(LINE_CODO_SALE_MS);
DIAG_OUT.print(" codo_vel="); DIAG_OUT.print(LINE_CODO_VEL);
DIAG_OUT.print(" codo_ciego="); DIAG_OUT.print(LINE_CODO_CIEGO);
```

**Y en la misma pasada subí la guarda de `main.cpp:1362` de 420 a 520.** La procedencia hoy son ~378 bytes; estos cuatro campos suman ~58 y la escritura completa pasa de 420. Si no la subís, la cabecera periódica deja de emitirse en silencio y perdés la procedencia a mitad de corrida.

### 0.2 — El guard de frame ciego, escrito y compilado, APAGADO

Define nuevo, al lado de `main.cpp:413`:

```cpp
#ifndef LINE_CODO_CIEGO
#define LINE_CODO_CIEGO 0
#endif
```

Y en `main.cpp:4524-4535`, reemplazá el cuerpo de la salida por centrado:

```cpp
else if (girado >= LINE_CODO_MIN_GRADOS)
{
#if LINE_CODO_CIEGO
    // g_rx_steer == 0.0 EXACTO es la Pi diciendo "no veo la linea"
    // (EN_EL_ROBOT/main.py:1132-1133, min_line_size=1 -> CERO pixeles
    // negros), no "estoy centrado". Un frame sin informacion no termina
    // la maniobra y TAMPOCO reinicia el contador: no dice nada, ni a
    // favor ni en contra.
    if (g_rx_steer != 0.0)
#endif
    {
        if (absSteer <= LINE_PIVOTE_SALE)
        {
            if (s_codo_cen == 0) s_codo_cen = millis();
            if (millis() - s_codo_cen >= LINE_CODO_SALE_MS)
                terminar = true;
        }
        else
            s_codo_cen = 0;
    }
}
```

Dos detalles que no son opcionales:

- **Usá `g_rx_steer`, no `steer`.** `steer` es una global (`main.cpp:834`) que otras partes del firmware pisan (2540, 2570, 2718, 2737, 2743). `g_rx_steer` (`main.cpp:2189`) es la copia que el propio código documenta como "nadie más la toca".
- **El frame ciego NO va al `else`.** La versión ingenua (`if (steer != 0.0 && absSteer <= SALE)`) manda el cero al `else` y reinicia el contador: eso, medido sobre las 9 corridas, mata 11 de 29 salidas tempranas (38%). La salida temprana es la válvula de seguridad de la maniobra — es lo que hace que un falso positivo cueste 25-30° en vez de 110°. Esta versión mata las 9 ventanas 100% ciegas y no rompe ninguna de las otras 20.

Con `LINE_CODO_CIEGO=0` el binario queda **idéntico** al de hoy.

### 0.3 — Compilá los dos binarios el viernes y dejalos hechos

```powershell
cd C:\Users\villa\rcj-2026-rescue-line-iita-salta-robocup-priority-fixes\software\teensy\firmware
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_CODO=1"
pio run -e diagnostico_fix
pio run -e competencia_fix
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
```

Verificado: `PLATFORMIO_BUILD_FLAGS` **se agrega**, no reemplaza. Sobreviven `MODO_DIAGNOSTICO=1`, `TELEMETRIA=0`, `FIX_LAZO_MOTOR=1`, `FIX_CURVA_CONTINUA=1`.

**Trampa de PowerShell:** `$env:PLATFORMIO_BUILD_FLAGS` **queda puesta en la terminal**. Si no la borrás, la corrida siguiente sale con flags que creés que no puso nadie. Borrala con `Remove-Item Env:PLATFORMIO_BUILD_FLAGS` después de cada bloque, y **verificá siempre en la cabecera del CSV, no en lo que escribiste**.

**Trampa de anidamiento:** todo el bloque `#if LINE_CODO` (`main.cpp:4476`) vive dentro de `#if FIX_CURVA_CONTINUA` (`main.cpp:4098`). Sobre `teensy_hid_device` pelado el flag del codo **no compila nada** y la corrida parecería "el codo no sirve". `diagnostico_fix` y `competencia_fix` los dos traen `FIX_CURVA_CONTINUA=1`. No uses otro entorno.

### 0.4 — Papel

Imprimí la planilla (una fila por pasada):

| Pasada | Binario/flags | Seg. de cada disparo | ¿Se salió en el codo? | Curvas tomadas | Curvas cortadas | LoP | Batería |
|---|---|---|---|---|---|---|---|

**Esto no es burocracia: es el único dato que decide.** El CSV no sabe si el robot se salió de la pista ni si cortó una curva. Sin la planilla, el sábado no produce una conclusión.

Y pegá en la notebook el **rollback nombrado**:

```powershell
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
pio run -e competencia_fix --target upload
```

(`default_envs = competencia_fix`, así que un `pio run --target upload` **pelado** reflashea justo el binario del que te querés ir, pero **sin** los flags del codo. El rollback hay que nombrarlo.)

---

## BLOQUE 1 — BANCO DE IMU (T+0 a T+15, sin pista)

Todo lo que sigue corta por grados de yaw de la BNO055, que arranca en **NDOF** (`bno.begin()` sin argumento, `main.cpp:2699` y `3282`), o sea con el magnetómetro al lado de cuatro motores. De ese yaw cuelgan tanto el titular de 108,5° como la condición de salida de la maniobra. Si el instrumento miente, el sábado entero no se puede leer.

**Qué hacer:** marca en el piso, robot alineado, pivotear 90° con motores andando, 5 veces, alternando sentido. Comparar el Δyaw del CSV contra la marca.

**Falsador:** |error| ≤ 5° en 4 de 5. 
**Si falla:** se corre igual, pero se anota en la planilla que **los grados netos del CSV no valen** y la decisión del día pasa a ser por observación (se salió / no se salió), no por número. No se cancela nada por esto.

Cuesta 15 minutos y evita construir el día sobre un número inventado.

---

## BLOQUE 2 — BASE DEL DÍA (T+15 a T+35, 3 pasadas)

```powershell
Remove-Item Env:PLATFORMIO_BUILD_FLAGS -ErrorAction SilentlyContinue
pio run -e diagnostico_fix --target upload
python tools\registrar_diagnostico.py COM7 2026-08-29_base_1.csv --nota "base del dia, codo=0, pasada 1"
```

(el COM real sale de `pio device list`.)

**Por qué gastar 20 minutos en esto:** los CSV del 26-ago son de otra luz, otra cinta, otro estado de batería y otro día. Comparar el codo del sábado contra ellos no está definido (regla 4). Además esto valida de punta a punta que el CSV se graba, que la Pi manda y que el cable no arruina la pasada antes de que importe.

**Control positivo:** la cabecera dice `codo=0 ... gain=1.35`, y hay filas con `ram != -1` y alguna rueda con `rpm > 1`.

**Qué se anota (esta es la base contra la que se mide todo el día):**
- de 3 pasadas, en cuántas se sale en el codo (esperado: 3 de 3);
- giro neto máximo por episodio de comando de un solo signo;
- frames con `rxsteer == 0` exacto por minuto de robot andando;
- FPS de la Pi (esperado ~51,7).

**Definiciones, fijadas ACÁ y no después:**
- **Minuto de robot andando** = suma de muestras con alguna rueda `rpm > 1` o `set > 1`, contando sólo muestras con `dt ≤ 0,5 s`. Los logs son casi todos robot quieto: `codo_1` tiene 78,3 s de archivo y 20,9 s de motores comandados. Un número "por minuto" sobre el archivo entero está mal por 4x.
- **Episodio de codo** = filas con `ram = 8`, **fusionando huecos ≤60 ms**. `g_line_branch` se pisa con la rama de telemetría, así que sin fusionar los 2 episodios reales de `codo_1` aparecen como 85 fragmentos. El cooldown propio (`LINE_CODO_COOLDOWN_MS=600`) garantiza que fusionar no puede pegar dos disparos distintos.
- **Grados netos de un disparo** = `yaw` de la primera fila con `ram=8` contra `yaw` **1,0 s después** de la última fila con `ram=8`. **`yaw` está en DECIGRADOS y envuelve en 3600.** Leerlo como grados da 150° en 670 ms, que es físicamente imposible.

---

## BLOQUE 3 — LINE_CODO=1 TAL CUAL (T+35 a T+75, 5 pasadas) ← **el bloque que importa**

```powershell
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_CODO=1"
pio run -e diagnostico_fix --target upload
python tools\registrar_diagnostico.py COM7 2026-08-29_codoA_1.csv --nota "LINE_CODO=1 tal cual, 0.45/300/25/110, pasada 1"
```

**Sin ningún otro `-D`.** Ni `MIN_GRADOS`, ni `MAX_GRADOS`, ni `VEL`, ni `ENTRA_MS`. Un solo grado de libertad, y es la configuración exacta que produjo la única evidencia que existe.

**Control positivo (si no dice esto, la corrida no vale):** la cabecera tiene que decir
`codo=1 codo_ent=0.45 codo_min=25 codo_max=110 codo_ent_ms=300 codo_sale_ms=120 codo_vel=55 codo_ciego=0`
y tiene que aparecer `ram = 8` en la ventana de cada disparo. Ojo: `ram=8` aparece con huecos, en el 64-66% de las filas de la maniobra. **Agrupá con tolerancia de 60 ms o el control positivo se lee como fallo.**

### Falsador, preregistrado, en números

**PRIMARIO (eventos únicos, regla 3):** **≥2 de 5 pasadas** con al menos un episodio de **≥80° netos**.
Base limpia: **0 de 291 episodios** en las 8 corridas sin el flag (p50 7,2°, p99 40,1°, máximo 50,0°). Rangos sin solape con lo que dio `codo_1` (53 episodios, máximo 125,5°, 3 por encima de 80°).

**EXPOSICIÓN (no es el resultado, es cuántas veces se expuso):** tasa de disparo entre **4 y 30 por minuto de robot andando**. Tasa base: **5,7/min** en `codo_1` (2 disparos en 20,87 s de motores comandados). Con n=2 el intervalo de Poisson al 95% va de ~0,7 a ~20/min: esta tasa **no acota nada** y hay que decirlo.

**COSTO (esto es lo que protege la corrida y es lo que nadie midió nunca):**
- cuántos disparos terminan **por visión**, cuántos por **MAX_GRADOS** (`girado ≥ 110`) y cuántos por **MAX_MS** (duración ≥1,5 s);
- de la planilla: cuántas curvas que hoy toma bien quedaron cortadas.

**SE APAGA si:**
1. se sale de pista en un tramo donde en el Bloque 2 **no** se salía, en ≥2 de 5 pasadas;
2. queda girando en el lugar de forma repetida (Lack of Progress delante del árbitro);
3. después de un disparo `rxsteer` queda en 0 exacto por más de **800 ms** (eso es línea perdida de verdad);
4. hay **más disparos que codos** en el recorrido.

**Advertencia sobre el cable, preregistrada:** `diagnostico_fix` saca el CSV por USB, o sea que el robot corre atado a 3 m de cable, y el propio `platformio.ini` avisa que ese cable "tira del chasis, que es justo la mecánica que se está midiendo" en curva cerrada. Contra el Bloque 2 está emparejado (mismo cable), así que el A/B es honesto. Pero **si aparece "cortó una curva", hay que reproducirlo sin cable antes de apagar el flag por esa razón.**

### Qué se hace con el resultado

| Lo que salió | Siguiente paso |
|---|---|
| ≥2 de 5 con ≥80° netos, sin salidas nuevas, tasa en banda | **ADOPTADO.** No gastes más ventana afinando. Saltá directo al **Bloque 6** (confirmación en el binario que compite). |
| Dispara, pero los disparos terminan cortos (<70° netos) y adentro de la ventana hay rachas de `rxsteer == 0` | **Bloque 4** (guard de frame ciego). Es exactamente la explicación medida. |
| Tasa **< 4/min** andando (casi no dispara) | **Bloque 5** (`ENTRA_MS=250`). |
| Tasa **> 30/min**, o se sale más que en el Bloque 2 | **Apagar el codo.** Ir al punto de corte anticipado (abajo). |

---

## BLOQUE 4 — GUARD DE FRAME CIEGO (T+75 a T+100, 4 pasadas) — condicional

```powershell
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_CODO=1 -D LINE_CODO_CIEGO=1"
pio run -e diagnostico_fix --target upload
python tools\registrar_diagnostico.py COM7 2026-08-29_codoB_1.csv --nota "LINE_CODO=1 + CIEGO=1, pasada 1"
```

**El mecanismo, reconstruido al milisegundo sobre `codo_1`:** el disparo 1 arranca en t=62,500 (yaw 75,7). En t=62,780 la visión cambia de signo y el signo congelado la ignora — la maniobra está haciendo su trabajo. En t=63,050 `rxsteer` pasa a **0 exacto** con `girado = 44,4°`, y se queda en 0 exacto **19 frames seguidos, 430 ms**. Exactamente **120 ms** después (= `LINE_CODO_SALE_MS`, la constante del `#define` apareciendo sola en el log) la maniobra sale con **57,0°**, `rot` cae a 0 y el robot sigue derecho. El contragiro posterior le devuelve +42,9° y el neto queda en −14,1°.

El disparo 2 también tuvo dos frames en cero, pero cayeron con `girado = 24,9°`, un pelo por debajo de `LINE_CODO_MIN_GRADOS = 25,0`, y la racha se cortó a los 20 ms. Corrió hasta el tope: **108,5° netos, ratio 1,00**.

**La diferencia entre 57° y 108,5° es exactamente si apareció o no una racha ciega de ≥120 ms después del grado 25.**

Y el cero es real, no una interpretación: en `codo_1` hay 136 frames en 0 exacto contra 3 en ±11 y 2 en ±22. Los ceros no son la cola de una distribución alrededor del centrado, son un pico de asignación dura. Además, **de las 6 ventanas de salida de ≥120 ms que hay en `codo_1`, las 6 son 100% ceros**: cero ventanas con un solo frame informativo.

**Control positivo:** cabecera con `codo=1 codo_ciego=1`.

**Falsador:**
- **CONTROL (aserción de código, no falsador):** ningún disparo puede terminar con una racha de `rxsteer == 0` de ≥120 ms inmediatamente antes.
- **PRIMARIO:** ≥1 episodio de **≥80° netos** en **≥2 de 4** pasadas, y la mediana de grados netos por disparo sube respecto del Bloque 3.
- **FALSADOR DEL COSTO — este es el que decide si va a la pista:** si **cero** disparos terminan por visión, la maniobra dejó de ser realimentada y se convirtió en un giro a lazo abierto de 110° o 1,5 s. **Eso no es este fix: es otra política.** Se apaga y se anota (regla 7).
- **SE APAGA** si aparece un giro de 60°+ en un tramo donde la pista dobla poco.

**Honestidad sobre la base:** la tasa base de este modo de falla es **1 de 2 disparos**, n=2. Los episodios ciegos de ≥120 ms fuera de `codo_1` son 3 en 154,6 s = **1,2/min**, no 7/min. Y de los 6 largos de `codo_1`, dos ocurren con `ram = -1`, o sea con el case 7 sin el volante, donde la puerta ni existe. Puede ser que el pivote ciego a 90-100°/s sea lo que se saca la línea del ROI (y entonces el peligro vuelve cada vez que `LINE_CODO=1`), o puede ser que `codo_1` fuera una corrida con peor luz. **No lo sé, y n=1 no lo puede decidir.**

**Si el guard no cambia nada:** apagalo (`codo_ciego=0`) y quedate con la configuración del Bloque 3. No lo lleves a competencia "por las dudas": un flag que no mejoró nada medible es superficie de falla gratis.

---

## BLOQUE 5 — SUBIR LA EXPOSICIÓN (T+100 a T+120, 3 pasadas) — sólo si la tasa quedó <4/min

```powershell
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_CODO=1 -D LINE_CODO_ENTRA_MS=250UL"   # + CIEGO=1 si sobrevivió
pio run -e diagnostico_fix --target upload
```

**250, no 200.** La tabla del propio diseño (`main.cpp:355-362`) da 17,4 disparos/min a 0,45/250 ms y 30,2/min a 0,45/150 ms, que ya había descartado por caliente. Proyectando 200 ms sobre las corridas base **en minutos de robot andando** (que es la unidad del diseño) dan 28,8 / 42,3 / 94,8 ventanas de armado por minuto: **200 ms cae encima o arriba del techo de aborto.** 250 ms es el escalón intermedio y es el único que queda dentro de la banda.

**Control positivo:** cabecera con `codo_ent_ms=250`.

**Falsador:** tasa en [4, 30]/min andando **y** el criterio que decide sigue siendo grados netos por episodio. **Se descarta si sube la tasa y baja el neto por episodio: eso es exactamente un detector con más falsos positivos.**

**No toques `LINE_CODO_ENTRA` (0,45), ni `MIN_GRADOS` (25), ni `MAX_GRADOS` (110), ni `VEL` (55).** Un grado de libertad.

**Reserva, sólo si 250 ms tampoco levanta la tasa y sobra ventana:** `-D LINE_CODO_ENTRA=0.30 -D LINE_CODO_ENTRA_MS=400`. Simulado sobre las 9 corridas cubre 7 de 9 contra 5 de 9 de 0,45/300 con tasa parecida (7,14 vs 5,95/min), y hay plateau: con ENTRA=0,30 la cobertura se queda en 7-8 de 9 para 200, 250, 300 y 400 ms. La lógica es buena (400 ms del mismo signo es más de un período y medio del ciclo límite de relé de 250 ms que oscila el comando, así que la oscilación no lo puede fabricar y un codo real sí). **Pero cambia dos variables a la vez y no está medido en pista.** Va último, y si sale bien hay que anotar que no se puede atribuir a ninguna de las dos.

---

## BLOQUE 6 — CONFIRMACIÓN EN EL BINARIO QUE COMPITE (T+120 a T+145, 2 pasadas)

**Este es el agujero real del plan y hay que taparlo sí o sí:** `competencia_fix` **nunca corrió con `LINE_CODO=1`**, y es el binario que va a la pista.

```powershell
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_CODO=1"   # + los flags que hayan sobrevivido, EXACTAMENTE los mismos
pio run -e competencia_fix --target upload
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
```

Este binario **no graba CSV**. El control es de observación:
- **Regla de oro 3 primero:** el robot enciende, los motores responden, no hay watchdog reset.
- 2 pasadas completas: contar a mano disparos y codos tomados, y que el comportamiento **se parezca** al de `diagnostico_fix` (ahora sin el cable de 3 m tirando, así que si algo mejora acá, es el cable).
- Verificar que el verde, el rojo y el plateado siguen funcionando. Nada de esto se probó con el codo encendido.

**Si el comportamiento no se parece:** se compite **sin** el codo. No se lleva a la pista un binario que se comporta distinto del que se midió.

---

## PUNTO DE CORTE — T+150, sin excepciones

**A T+150, pase lo que pase, se para de experimentar.** Con o sin resultado:

1. Flashear el binario que compite:
   - **si el Bloque 6 pasó:** `competencia_fix` con exactamente los mismos flags que se midieron;
   - **si no pasó, o si hay cualquier duda:** `Remove-Item Env:PLATFORMIO_BUILD_FLAGS` + `pio run -e competencia_fix --target upload`, o sea el firmware de hoy, tal cual.
2. **Una vuelta completa de verificación** con ese binario: enciende, motores, sin watchdog reset, toma las curvas que hoy toma, hace el verde y el plateado.
3. Guardar **todos** los CSV y fotografiar la planilla de papel.
4. Cargar la entrada en `testing/TEST_LOG.md` (hoy no hay ninguna con "codo" — regla de oro 3).

**Regla dura: nada de compilar un flag nuevo después del punto de corte.** Un flag que no se midió en la pista el sábado no compite. Los últimos 30 minutos son para dejar el robot en un estado conocido, no para una idea más.

### Corte anticipado

Si a **T+120** llevás ~9 pasadas con el codo encendido y **cero** episodios de ≥80° netos, el codo no va a salir hoy. Apagalo y usá el tiempo que queda en dos cosas baratas que desbloquean la semana que viene:

1. **`GRABAR=/home/iita/codos.avi python3 main.py`** con el robot **andando** en la pista de hoy, 3 pasadas. Etiquetar los codos después, sobre el video, pudiendo retroceder. Es el dataset que hoy no existe: el marcado a mano del commit `4a56859` sólo tiene escalares (`t,frame,ang,npts,res_c,res_l,dispara,marca_humana`), no hay frames, y encima se tomó con el robot paseado a mano con la cinta ocupando media pantalla. Sin este video, cualquier detector nuevo es indefendible.
2. Repetir la base para confirmar que nada quedó peor de como empezó el día.

---

## LO QUE **NO** HAY QUE HACER, Y POR QUÉ

1. **NO barrer `K_CERCA`/`K_LEJOS` en la Pi.** El hallazgo de que con 40/40 la ley colapsa a posición pura de la banda lejana es **real** y merece Issue — pero el escalón recomendado (`K_LEJOS=90`) cae **dentro de la zona que su propio autor prohibió**: con la fórmula corregida el nulo cae en `K_LEJOS` 85-106, y en el nulo el robot rueda **paralelo a la línea a cualquier distancia** hasta que la pierde. Eso es regla 9 sobre lo único que hoy funciona (la recta). Y el mecanismo no puede funcionar ni en principio: el corrimiento parásito de la cámara y el error lateral real **son la misma señal**; anular uno anula el otro. Encima la premisa está falsada por el propio log: `LINE_CODO_ENTRA` es **0,45**, no 0,60, y `codo_1` corrió con `codo_ent=0.45` y disparó dos veces. El codo no es inalcanzable por aritmética.
2. **NO el detector de borde lateral de los campeones.** La regla real es **AND** (la línea toca los dos bordes a la vez), no OR. Medido sobre los videos que ya están en el repo: con OR dispara **29,9 eventos/min fuera de los codos** contra el límite de 6 que la propia propuesta fijó — peor que los detectores de curvatura que se hundieron con 16,2 y 17,0. Con AND baja a 10,2/min, mejor pero todavía arriba. Y en el 10-67% de los frames dentro de un codo la cinta toca **los dos bordes**, o sea que el lado queda indefinido justo donde dispara. Elegir mal el lado + saturar a |steer|=1 + congelarlo 600 ms + entregárselo a una maniobra que congela ese signo hasta 110° = salirse de la pista garantizado. Candidato para **después** de que exista el video etiquetado del corte anticipado.
3. **NO subir `LINE_CODO_VEL`.** Con `fl_set = fr_set = 55` el `fl_pwm` ya trepa a 176-192 sobre 255 mientras el `fr_pwm` queda en 119-135: a la delantera izquierda le quedan ~60/255 de margen. Subir la velocidad la satura primero a ella, el pivote se vuelve asimétrico y el robot traslada en vez de girar. Y el banco de 110 rpm **se contradice a sí mismo**: en la segunda pasada del mismo archivo, con las ruedas girando a 69,7 / 89,3 / 108,2 rpm medidos, el yaw **no se mueve** (clavado en −1045 ± 6 durante los tres segmentos). "El giro no satura" se apoya en la mitad de los datos.
4. **NO bajar `LINE_CODO_MAX_GRADOS` a 100 ni a 90.** Es el parámetro con el que se produjo el **único** giro ≥90° del dataset (108,5°): bajarlo a 100 lo habría cortado. Además la devolución real después de la maniobra no es 18° sino **~29,7°** (y ya había −18,3° de pre-giro antes del disparo, swing total ~127° en la esquina), así que ni 100 ni 90 son el número correcto. **El sábado se MIDE la devolución con MAX=110 y se decide la semana que viene.**
5. **NO subir `LINE_CODO_MIN_GRADOS` de 25.** Es lo único que acota el daño de un falso positivo (`main.cpp:377-380`, explícito: "un mínimo alto convertiría cada falso positivo en un giro de 45 grados en medio de una recta"). Subirlo a 60 **en la misma corrida** en que se multiplica la tasa de disparo es exactamente la combinación que el diseño está construido para evitar.
6. **NO `runAngle(±90)` este sábado.** Es la idea más limpia del lote: lazo cerrado por IMU a ±1°, sordo a la cámara, corrige el sobregiro, y deja el robot frenado al salir. Pero **bloquea ~950 ms** sin `get_color_fast()`, sin watchdog de comunicación, sin contador de verdes y sin drenar Serial5 (`kFixIssue63KeepSerialDuringMotions = false`): el buffer de 64 B se desborda. Un plateado o un rojo perdido cuesta más que el codo. Semana que viene, con el drenaje de Serial5 resuelto antes.
7. **NO `LINE_LEY_SUMA`, `LINE_FRENO_DELANTERO`, `LINE_FRENO_ROT_MULT`, `steerRadius`, `LINE_RECTA_FACTOR`, `LINE_ROT_EXP`, `LINE_STEER_GAIN`, ni el mapeo.** Todas son palancas de **radio**, y el álgebra dice que `vel` se cancela en `R = b_eff*(1-rot)/(2*rot)`. Ya se barrieron ~15 configuraciones el 26-ago sin mover el codo. Y el freno delantero probablemente tiene **el signo al revés**: el centro de giro se aleja del eje que pierde agarre lateral, así que frenar la rueda delantera lo corre hacia **atrás**. El banco concluyó lo contrario leyendo que esa rueda recorrió 0,1 cm — pero ese encoder mide la rotación de una rueda **consignada a 0 rpm**: lee 0 porque el PID hizo su trabajo, no porque el centro se haya movido.
8. **NO los fixes ya enterrados:** `kFixMapeoRot`, `kFixPivoteAvanza`, `kFixPivoteMemoria`, `kFixGapSueltaPivote`, `LINE_DWELL_GLOBAL`, `LINE_PIVOTE_CONFIRMA_MS`. Ya los mató la evidencia del 26-ago (dwell 5,6x, pivote sostenido con 79,7% de avance cero).
9. **NO término derivativo.** Airborne lo tiene (KP=1,8 KD=2,0), pero una realimentación en velocidad angular cambia el **amortiguamiento**, no el punto de equilibrio; el techo queda intacto. Y con lag comando→giro de 60-70 ms y encoders de 1 canal con signo inferido, mete ruido justo donde el lazo ya se cancela solo.
10. **NO `ROI=auto`, NO `PLANNER`, NO `RETROCEDER`, NO tocar `AREA_MIN`, NO `RECUP=1` el mismo día que el codo.** `RECUP=1` es genuinamente interesante — es el único mecanismo de signo congelado que ya existe del lado de la Pi — pero mezcla dos cambios y hoy **ninguna corrida "CTRL=lineal" es lineal pura**: en `lineal_1` el **60,3%** de las muestras salieron del `atan2` crudo por el fall-through de `main.py:1042-1045`, sin una sola línea de log que lo diga. Hasta que exista el contador de rama, cualquier A/B del lado de la Pi es ininterpretable.
11. **NO cambiar dos cosas en una corrida.** Nunca. Ni "de paso porque ya estoy compilando".
12. **NO `pio run --target upload` pelado.** Reflashea `competencia_fix` **sin** los flags. El rollback hay que nombrarlo.

---

## LO QUE HAY QUE HACER IGUAL, se adopte o no el codo

- **Arreglar el comentario de `main.cpp:4248-4260`.** Está razonando sobre `final_rpi/Main.py:987`, que **no corre en el robot**, y concluye que "la Pi no ve nada NO llega como steer 0". Es falso para el binario que corre: `EN_EL_ROBOT/main.py` no tiene `line_lost_search_angle` ni `last_line_search_dir`, y `rxspeed` en las 9 corridas vale **0 o 40, nunca 12**. Cualquiera que lea ese comentario va a descartar el modo de falla del Bloque 4.
- **Anotar la tensión con `kFixGapSueltaPivote`** (`main.cpp:4275-4277`): usa `steer == 0.0` con la **polaridad opuesta** — lee el cero como "gap, andá derecho, soltá el pivote". No pueden ser los dos correctos sobre qué significa el byte 90. Con la evidencia nueva la lectura del Bloque 4 está mejor sostenida, pero el repo ya tomó una decisión en el otro sentido y hay que decirlo.
- **Issue P1 por el colapso 40/40** en `EN_EL_ROBOT/main.py:30-31`: con los defaults el coeficiente de `e_pos` es **cero** y la "ley con término de rumbo" es posición pura de la banda lejana. El docstring de `main.py:140-143` advierte que el bug de la primera versión era tener "UNO SOLO" de los dos términos — y con los defaults tiene uno solo otra vez.
- **Loguear la rama por frame del lado de la Pi** (`_quien` ya existe, `main.py:1174`, pero sólo se pinta en el overlay del video). Convierte "el cero vino del branch ciego" de inferencia a observación directa y cuesta una columna. Si lo hacés el viernes, verificá en banco que los FPS quedan ≥45.

---

## HONESTIDAD SOBRE LA INCERTIDUMBRE

No te voy a prometer que el sábado el robot tome el codo.

- **Todo esto descansa sobre n=2 disparos de un solo archivo.** Con 2 eventos, el intervalo de Poisson al 95% para la tasa va de ~0,7 a ~20/min. No acota nada.
- **Uno de esos 2 disparos fue un pivote de 57° seguido de 40° de contragiro, neto −22°.** O sea que el costo real de un falso positivo **no** es "casi nada" como promete el comentario de `main.cpp:377`. Es la misma objeción con la que el propio repo mató el diseño LATCH en `EL-CODO-2026-08-26.md §3`.
- **Que la maniobra complete 90° no demuestra que el robot tome el codo.** En los dos disparos hubo contragiro inmediato. El fix hace que la maniobra no se suicide; que la maniobra **alcance** es una apuesta separada, y el sábado hay que medir las dos por separado.
- **Los CSV de base perdieron entre 48% y 98% de las muestras** (`drop`). Cualquier métrica acumulativa medida sobre ellos (giro absoluto, ratio abs/neto) está subestimada. **No compares el ratio abs/neto entre archivos distintos.**
- **La maniobra pivota con avance exactamente cero** (`rot = 1 ⇒ v_centro = 0`, y en las 242 filas de `ram=8` la consigna es `ls=55 rs=55 rot=1000`). Eso es exposición directa a Lack of Progress. La mitiga que el 63,8% de avance cero de `codo_1` está **dentro** de la banda base (54,3 / 40,6 / 67,1% en las tres corridas base) y que la rama 8 aporta sólo 5,8 puntos: la exposición a LoP ya la crea la ley base, no el flag. Pero mirá al árbitro imaginario en cada pasada.
- **El desenlace más probable a mi juicio no es "resuelto" sino "mejor pero no confiable".** Si el sábado termina con "el codo dispara, gira 90°, y el robot igual se va", **eso también es un resultado y hay que anotarlo**: significa que el problema no es el giro sino el re-enganche a la rama nueva de la L, y la próxima palanca es el sesgo direccional del lado de la Pi — con el video etiquetado del corte anticipado, no antes.

**Lo único que el 26-ago dejó demostrado es esto: el signo congelado es lo único que rompió el techo de 55°.** El sábado va a decir si eso repite o si fue suerte con n=2. Cualquiera de las dos respuestas vale la ventana.