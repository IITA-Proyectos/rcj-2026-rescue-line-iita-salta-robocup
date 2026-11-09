# CRESTA-BAJADA + PLATEADO (1 y 2-nov-2026): verde en la cresta, bajada-sin-recup en el plano y entrada al plateado

Base: el `main.py` que está en la Pi desde el 1-nov a las 14:09 (sha256 `df73beb1…`, con RAMPA-TRANSICION-2). El
instalador también acepta el `main.py` de este mismo paquete sin el plateado (`eb60f7a2…`) y el de este paquete con
el umbral viejo de 1740 (`e9186911…`, instalado el 7-nov a las 18:17). Son tres cambios, solo en la Pi, y cada uno
se apaga con una variable.

| Archivo | sha256 |
|---|---|
| `main.py` | `9da00beb31af7af6fdd39785b9b2ff886be002c3e6ec108bb60dfb819099d578` |
| `verde_cresta.py` (nuevo) | `5d93c15671ed37993f63e25db257f2cb741c6e3da5fbb681f08ac44203612737` |
| `plateado_entrada.py` (nuevo) | `9abbfe476ffdaa1540da3805466a77a35b313eb07fc89f802bd66144f33ce517` |
| `calibrar_plateado.py` (nuevo, herramienta para la sede) | `f825fe52834a1c68529103c37a5fc3fd2b29b32dcf88bacca529515835eb0797` |
| `rampa_transicion.py` (el mismo de la Pi) | `642df9735e4f96de031cffb5d71e0f3b31f980b9036049d873e780e7a6af203c` |

## 1. Verde en la cresta: `VERDE_CRESTA=1`

Es el mismo de `cambios/verde_cresta_20261101` (ver su `RESULTADO.md`). Con un verde simple que aparece con la
Teensy en SUBE:
- No se repite el verde durante 5 s.
- Esos 5 s se usa la ley del piso: sin corte de cresta, `cresta-recto`, recta ni transición.
- Desde 1,4 s, la Pi pivotea (±85) hacia el lado del verde hasta tener la rama conectada y apuntando bien
  durante 4 cuadros. Tope de 0,7 s.
- El piso no se toca: 0 cuadros distintos en 42 verdes.

## 2. Bajada: `BAJADA_POST_LADO_ANG=60`

En 19:17 de las 12:49, abajo de la rampa lateral derecha, la cinta dobló cerrado y la Pi venía mandando −82. La
cinta salió por el costado 2,6 s después del LLANO, y `bajada-sin-recup` (`BAJADA_POST_S=4`) lo mandó derecho
1,75 s fuera de la pista. Ahí tenía que recuperar.

Ya en el plano, con la Teensy sin decir BAJA, sigue derecho solo si:
- hubo un verde hace menos de 2,5 s (la maniobra de la Teensy y la rotonda de abajo); **o**
- la cinta se perdió al frente: |último ángulo| < 60°. Es el borde de la segunda bajada, la razón por la que
  `BAJADA_POST_S` vale 4.

Si se perdió por un costado y sin verde reciente, hace lo de siempre: recuperación. La decisión se toma al perder
la cinta y vale hasta que vuelve. Mientras la Teensy dice BAJA no cambia nada. Si la cinta se perdió bajando,
sigue derecho como siempre aunque la Teensy pase a LLANO: la primera versión no lo hacía, y en el simulador
cambiaba una pasada del 31-oct (21:03, 5:15.95).

## 3. Entrada al plateado: `PLATEADO_RECTA=1`

En la entrada, la cinta llega oblicua a la banda, se pierde y salta la recuperación. En las 11 corridas del 31-oct
y el 1-nov hubo 13 entradas:
- **Las que la recuperación mandó derecho (GAP) entraron.** El sensor de color confirma unos 2 s después.
- **Las 8 que decidieron CURVA a la izquierda (+39..+66)** quedaron mirando la pared de la zona, sin cinta, y la
  Pi las frenó.

Con este cambio, si la recuperación decide CURVA a la izquierda **y** la banda se ve al llegar (los 6 cuadros antes
de perder la cinta) **y** después del retroceso (hasta la decisión), va derecho como las que entraron (GS18, la
misma búsqueda recta del GAP, con el sensor de color vigilando). Cualquier otra decisión no cambia.

**Cómo se mide la banda:** se cuentan los píxeles grises con textura de la fila 40 para abajo, en el cuadro de
160×120. Gris: S < 60 y 110 < V < 225. Textura: desvío local de V > 7, en 5×5. Se toma la mediana de la llegada y
la de después del retroceso, y las dos tienen que dar ≥ 1790.

| Recuperaciones que decidieron CURVA a la izquierda | El menor de los dos puntajes |
|---|---|
| Las 8 del plateado | 1856 la más baja (13:26 de las 12:49) |
| Las 100 que no son plateado | 1730 la más alta (13:54, 4:03: 1730 al llegar, 1778 después) |

El umbral 1790 queda en el medio: unos 60 de margen para cada lado. Los puntajes son de los cuadros crudos (PNG),
que es lo que ve la Pi.
- **13:54 se midió primero sobre el video** (1620/1808), porque su crudo no estaba en la PC. Estimé que en crudo
  daría entre 1560 y 1670, y estaba mal. El 7-nov se midió con el crudo que quedó en la Pi y dio 1730/1778. Por
  eso el umbral pasó de 1740 a 1790: con 1740 esa curva quedaba a 10 del umbral.
- **El margen es chico,** unos 60 para cada lado: el umbral hay que verificarlo en la sede.

Las dos condiciones hacen falta: el piso blanco ya da alrededor de 1000–1700 por los reflejos y los bordes de la
cinta, y la banda lo sube a 1850–3400.

**Lejos de las rampas: `PLATEADO_RAMPA_S=20`.** No actúa si la Teensy avisó rampa hace menos de 20 s.
- **Por qué:** arriba de una rampa la cámara ve la pista desde lo alto (baldosas, juntas, la rotonda, gente) y la
  banda da 2000–4000 sin que haya plateado. Una curva a la izquierda a 12 s de una rampa dio 1868 al llegar, y se
  salvó solo porque después del retroceso dio 1376.
- **A las entradas no las afecta:** las 13 entradas al plateado pasaron a más de 90 s del último aviso de rampa.
- **Si en la sede la zona queda justo después de una rampa,** bajarlo (por ejemplo a 5) o ponerlo en 0.

**Solo a la izquierda.** A la derecha hay curvas que no son plateado casi en el umbral (1927/1731, 31-oct 21:03).
Activarlo a la derecha rompería curvas. Por eso la entrada de 13:54 (3:14), que curvó a la derecha, no queda
cubierta.

**En el log.** Cada CURVA de la recuperación, de los dos lados, y cada RECTA escriben una línea con la hora y los
dos puntajes, actúe o no. Sirve para ajustar el umbral en la sede. Por ejemplo:

```text
[PLATEADO] 15:42:07 CURVA IZQ llegada=1962 post=2167 (umbral 1790, 2 cuadros post) -> RECTA (lateral previa + fragmento pequeno compatible)
[PERDIDA] RECTA -> busqueda GAP/camara; APDS vigila colores
```

**Costo:** guarda una copia del cuadro en cada vuelta (microsegundos). El puntaje se calcula solo durante una
recuperación: 6 cuadros al perder la cinta y 1 por cuadro después del retroceso, menos de 1 ms cada uno.

## Verificación

- **Instalador:** probado sobre copias del Desktop con las dos bases. Comprueba el `main.py` actual y los hashes,
  compila, prueba `verde_cresta` y `plateado_entrada` con casos sintéticos, respalda y reemplaza. Si se corre dos
  veces, se niega.
- **Casos sintéticos de `verde_cresta`:** ver `cambios/verde_cresta_20261101`.
- **Cambios 1 y 2 en el simulador:** comparados con lo que corre hoy en la Pi (`main.py` `df73beb1…`), con los
  mismos cuadros, cuadro por cuadro. Fueron 14 simulaciones: 13:54 y 14:09 completas, 10 tramos de 12:49 que la
  cubren casi toda, y tramos del 31-oct (21:03 y 22:11).
  - **Piso, rotonda y bajadas normales:** 0 cuadros distintos. Incluye 22:11 del 31-oct (el "derecho" bueno de
    4:20 que rompía `BAJADA_POST_S=2`) y 21:03.
  - **Verdes de la cresta:** cambian solo sus ventanas (14:09 ×5, 13:54 ×3, 12:49 ×3).
  - **19:17 de las 12:49:** en 19:20.70 dispara la recuperación en vez de seguir derecho. El log dice
    `[BAJADA] cinta perdida por el costado (-79) 2.6 s despues de BAJA, sin verde: recuperacion`.
  - **Fuera de eso,** cambian solo cuadros donde el robot ya estaba perdido y lo iban a reubicar: 12:49 en 15:10
    y 20:16, y 13:54 en 4:34 y 4:53.
- **Cambio 3 en el simulador:** comparado con el paquete sin el plateado, en las 11 corridas del 31-oct y el 1-nov.
  Cada corrida se cortó en las reubicaciones y los rescates: 178 tramos, 118.186 cuadros, y cada tramo arranca de
  cero como el robot.
  - **Cambian solo las 8 entradas** que curvaban a la izquierda: 11:47 (5:02 y 14:22), 12:38 (4:08) y 12:49
    (7:39, 12:47, 13:17, 13:26 y 17:31). En cada una, desde el primer cuadro de la CURVA pasa a `gap-inicio`.
    No cambia ningún otro cuadro.
  - **Los puntajes del log son los del análisis,** en las 8.
  - En la simulación hubo 92 decisiones CURVA a la izquierda: 8 fueron RECTA, las del plateado. Entre las otras 84,
    la más alta dio 1620/1808 y no actuó. Esa es 13:54 4:03, simulada con el video; en crudo da 1730/1778.
  - Ninguna de las 92 da entre 1740 y 1850, así que con el umbral nuevo (1790) cambian las mismas 8 y nada más.
  - La de 7:39 se reprodujo arrancando el tramo en el cuadro 9000. Antes de ahí el tramo largo ya se había separado
    del robot, y el simulador no se recupera solo de una parada.
  - Con `PLATEADO_RECTA=0`, en los mismos 178 tramos: 0 cuadros distintos contra el paquete sin el plateado.
  - Todo esto se corrió con este paquete, con la protección de rampa incluida (`main.py` `e9186911…`, umbral
    1740). El de ahora solo cambia el umbral por defecto a 1790, y ninguna de las 92 curvas cae entre los dos.
- **`calibrar_plateado.py`:** probado sobre las grabaciones. Con las 8 entradas como "entrada" y las vueltas de
  noche del 31-oct (21:03 y 22:11) como "vuelta", da la entrada más baja en 1856 y la curva más alta en 1564, y
  sugiere 1710. Da los mismos números que el log del `main.py`. También se probaron los casos "no hubo pérdida en
  la entrada", "no hay curvas para comparar" y "no separa".
- **De cada pasada por la entrada cuenta solo la última recuperación,** la de la banda. La primera versión tomaba
  todas: si el robot se perdía antes (en el zigzag), una curva común tiraba el resultado abajo y decía "no
  separa". Se probó con un tramo largo de 12:49 que mezcla pasadas que no llegaron a la banda. Igual sugiere 1710
  y nombra aparte las 4 pasadas que no la pasan.
- **Las recuperaciones de antes de la banda en cada pasada (el zigzag) cuentan como curvas comunes.** Ahí la regla
  no tiene que actuar, y es donde está el riesgo del primer giro de 45°. Si una curva a la izquierda del zigzag da
  alto, la herramienta sube el umbral por encima de ella, o dice "no separa" si queda pegada a la banda. Se probó
  con casos armados: zigzag 2100 y banda 2500 da 2300; zigzag 2400 y banda 2500 dice "no separa". Con las
  grabaciones reales sigue dando 1710, contando 6 curvas de antes de la banda.
- **En la Pi (7-nov),** con su Python y su OpenCV, da los mismos números que en la PC. Con el crudo de 13:54 que
  quedó en la Pi, la curva de 4:03 da 1730/1778, y con 3 entradas de 12:49 sugiere 1850.

**Lo que no está probado en pista:**
- Que el giro forzado de la cresta encuentre la rama.
- Hacia dónde gira la recuperación en 19:17 después del retroceso. El simulador no sabe dónde queda el robot.
- Que derecho desde esas 8 poses entre a la zona. Las 3 que fueron derecho por su cuenta sí entraron.
- El umbral del plateado con otra luz u otra cinta plateada.

**Lo que no arregla:**
- El segundo verde de la rotonda, cuando el cuadrado queda en el borde de la imagen.
- La salida de la rotonda que dobla justo al terminar la bajada. Ahí hubo verde hace poco y sigue derecho
  como hoy.
- La otra pasada por la rampa lateral (13:54, 5:06.85), porque pasa con la Teensy todavía en BAJA.
- Una entrada al plateado que la recuperación decide como CURVA a la derecha.

## La entrada de la competencia

En la foto de la entrada de la competencia la línea hace dos giros de unos 45° a la izquierda. El segundo queda
justo antes de la banda, y la línea termina perpendicular a la banda, cerca del medio.

Acá lo que separó las que entraron de las que no fue cómo se vio el final de la cinta. Si se vio de frente, sin
rama al costado, la recuperación eligió GAP (P01, P03 y P05). Si la cinta venía tocando el costado, eligió CURVA a
la izquierda. El ángulo de llegada no separaba.
- **Si termina el giro y ve el final de frente,** lo esperable es GAP y que entre. Este cambio no actúa.
- **Si llega todavía girando,** la cinta toca el costado izquierdo y lo más probable es CURVA a la izquierda. Es
  la misma falla de acá. Este cambio lo manda derecho, y cruza la banda en diagonal como las que entraron acá.
- **El primer giro de 45°** queda a unos 12 cm de la banda (estimado en la foto). Si ahí perdiera la cinta con la
  banda a la vista, este cambio lo mandaría derecho y estaría mal. El puntaje sube recién en el último medio
  segundo antes de perder la cinta: 24 cuadros antes (~1 s) da 1080–1700 en las 13 entradas, todas debajo de
  1790. Además tiene que pasar también después del retroceso. El riesgo es bajo, pero hay que mirarlo.
- **Lo que no se sabe hasta la sede** es la luz y la cinta plateada que pongan. Con otra luz se mueven los dos
  números, el del piso y el de la banda.
- **Todas las entradas medidas son de día,** con sol por las ventanas (1-nov). De noche, con luz artificial como
  en un gimnasio cerrado (31-oct), no hubo ninguna. Esas noches las curvas normales dieron más alto: la curva más
  alta del 31-oct (1564) es la más alta de todas.

## Antes de viajar (sábado, en la pista de ustedes)

1. **Instalar el paquete** y probar como siempre.
2. **Plateado con luz artificial:** cortinas cerradas o de noche, con las luces prendidas. Hacer las dos grabaciones
   de la sede (abajo) y correr `calibrar_plateado.py`. Es la prueba que más se parece al gimnasio. Usar los nombres
   `prueba_entrada` y `prueba_vuelta` en vez de `sede_…`, para no mezclarlas con las de la sede.
3. **Réplica de la entrada de la competencia:** con cinta, dos giros de 45° a la izquierda, el segundo justo antes
   de la banda, y la línea que termine perpendicular a la mitad de la banda. Hacer 5 a 10 entradas y mirar qué
   decide la recuperación.
4. **Ensayar una vez el paso a paso de la sede, con reloj.** Lleva unos 40 minutos.

## En la sede: por partes (unos 40 min de la hora)

1. **Parar el servicio:**

   ```bash
   sudo systemctl stop iita-robot.service
   ```

2. **Primero, la pista entera (~10 min), frenándolo antes de la entrada al plateado.** Sirve para dos cosas:
   - Ver cómo andan con esa luz los verdes, las curvas, las rampas y el negro.
   - Es la grabación "vuelta" de la herramienta: las curvas que NO tienen que activar la regla. Por eso no tiene
     que llegar a la banda: cuando llegue al zigzag de antes de la entrada, levantarlo.

   Va en `sombra`, que anota todo y no cambia nada: el robot anda como hoy.

   ```bash
   cd /home/iita/Desktop && PLATEADO_RECTA=sombra GRABAR_CRUDO="/home/iita/crudo_sede_vuelta" LOG_FILE="/home/iita/pista_sede_vuelta.log" python3 -u main.py
   ```

   Si se corta y hay que volver a arrancar, usar el mismo comando: se agrega a la misma carpeta y cuenta igual.

   **La cámara no se toca:** queda en automático, como siempre, con balance de blancos y exposición automáticos.
   Así se grabó todo lo que se midió del plateado: las 9 grabaciones crudas del 31-oct y el 1-nov dicen
   `white_balance_automatic=1` y `auto_exposure=3`.

3. **Después, las pasadas por la entrada (~10 min),** también en `sombra`. Si curva en la entrada, falla como hoy,
   porque es solo para medir.
   - Poner el robot en la línea ANTES del zigzag, para que llegue a la banda girando como en la competencia.
     Arrancar después del zigzag no sirve: llega más derecho y se mide otra cosa.
   - Hacer 4 a 6 pasadas, reubicando como siempre.
   - Cortar con Ctrl+C.
   - De cada pasada, la última recuperación es la de la banda. Las de antes, en el zigzag, la herramienta las
     cuenta como curvas comunes, que no tienen que activar la regla.

   ```bash
   cd /home/iita/Desktop && PLATEADO_RECTA=sombra GRABAR_CRUDO="/home/iita/crudo_sede_entrada" LOG_FILE="/home/iita/pista_sede_entrada.log" python3 -u main.py
   ```

4. **La herramienta (~1 min).** Calcula para cada recuperación lo mismo que el `main.py` y dice qué hacer:

   ```bash
   cd /home/iita/Desktop && python3 calibrar_plateado.py --entrada /home/iita/crudo_sede_entrada --vuelta /home/iita/crudo_sede_vuelta
   ```

   Arriba de todo lista las grabaciones que leyó, con la hora de arranque. Tienen que ser solo las de hoy.

   En "Resultado" puede salir una de cuatro cosas:
   - **Un umbral sugerido** y el comando `sed` para ponerlo en el servicio: copiarlo y correrlo.
   - **"dejar el umbral como está"**.
   - **"NO SEPARA"** con esa luz: corre el comando que apaga la regla, y queda como antes del cambio.
   - **"son pocas curvas":** si hay tiempo, dar otra vuelta.

   **Si también calibran verdes:** aplicar primero el perfil de verdes (`--apply`) y recién después correr este
   `sed`. El calibrador guarda la huella del `main.py` al calibrar y, si cambió, rechaza el perfil.
5. **Verificar la entrada (~5 min)** sin `sombra`, como en las rondas: 2 o 3 pasadas desde antes del zigzag. En el
   log tiene que aparecer `[PLATEADO] ... CURVA IZQ ... -> RECTA` y después `Llego 241 -> entrando a rescate`.
6. **Al final, la pista entera como en las rondas (~10 min),** sin `sombra` y con la entrada incluida. Es la prueba
   de que todo junto anda: en el log, `-> RECTA` tiene que aparecer solo en la entrada.

   ```bash
   cd /home/iita/Desktop && GRABAR_CRUDO="/home/iita/crudo_sede_final" LOG_FILE="/home/iita/pista_sede_final.log" python3 -u main.py
   ```

   ```bash
   grep "\[PLATEADO\]" /home/iita/pista_sede_final.log
   ```

Al terminar, volver a prender el servicio: `sudo systemctl start iita-robot.service`.

**Para que lo mire yo:** alcanza con el texto que imprime la herramienta (copiado o una foto de la pantalla) y las
líneas `grep "\[PLATEADO\]" /home/iita/pista_*.log`. Si hace falta más, las carpetas `crudo_*` comprimidas: son
unos 50 MB por minuto de grabación. El video `.avi` solo no sirve, porque la compresión cambia el puntaje.

## Instalar (con la Pi en la red)

Desde la carpeta `software` de la PC:

```bash
scp -r raspberry/cambios/cresta_bajada_20261101 iita@10.109.108.189:/home/iita/Desktop/.cresta_bajada
```

```bash
ssh iita@10.109.108.189 "cd /home/iita/Desktop/.cresta_bajada && python3 desplegar.py"
```

Si el `main.py` de la Pi no es el esperado, o la copia está incompleta, no toca nada. Al instalar, deja el respaldo
en `Desktop/respaldo_cresta_bajada_<fecha>/` e imprime el comando para volver atrás.

## Probar

```bash
sudo systemctl stop iita-robot.service
cd /home/iita/Desktop
N="cresta_bajada_$(date +%Y%m%d_%H%M%S)"
GRABAR_CRUDO="/home/iita/crudo_$N" GRABAR="/home/iita/pista_$N.avi" LOG_FILE="/home/iita/pista_$N.log" python3 -u main.py
```

Qué buscar en el log:
- **Al arrancar:** `[VERDE-CRESTA] VERDE-CRESTA-1 VERDE_CRESTA=1` y
  `[PLATEADO] PLATEADO-ENTRADA-1 PLATEADO_RECTA=1 umbral=1790`.
- **En la cresta:** `verde N subiendo: completa la Pi`, y después `suelta: cinta conectada` o `suelta por tope`.
- **En la bajada:** `[BAJADA] cinta perdida por el costado (...) sin verde: recuperacion`.
- **En la entrada al plateado:** `[PLATEADO] ... CURVA IZQ ... -> RECTA`, después
  `[PERDIDA] RECTA -> busqueda GAP/camara` y `Llego 241 -> entrando a rescate`.

Para comparar en el mismo lugar con lo de hoy, adelante de `python3`:
- `VERDE_CRESTA=0` apaga el cambio 1.
- `BAJADA_POST_LADO_ANG=0` apaga el cambio 2.
- `PLATEADO_RECTA=0` apaga el cambio 3; `PLATEADO_RECTA=sombra` solo anota.
- `PLATEADO_UMBRAL=…` cambia el umbral; `PLATEADO_RAMPA_S=…` cambia los segundos sin rampa que exige.
