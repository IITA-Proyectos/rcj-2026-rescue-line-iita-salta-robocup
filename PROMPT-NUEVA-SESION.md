```
TRASPASO NUEVA SESIÓN — NUEVO CODE RCJ / ROBOLIGA
Fecha del traspaso: 25-ago-2026, noche

Repositorio:  IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup
Rama:         collab/nuevo-code
Canal:        issue #138 (Claude ↔ ChatGPT)

==========================================================
0. ARRANQUE OBLIGATORIO
==========================================================
NO confíes en memoria de sesiones anteriores.

1. git fetch && checkout collab/nuevo-code && git status
2. LEÉ COMPLETO: TRASPASO-2026-08-25-NOCHE.md en la raíz.
   Es la fuente de verdad del DIAGNÓSTICO.
   TRASPASO-2026-08-25.md (el de la mañana) sigue valiendo
   sólo como inventario y por sus trece hipótesis muertas.
   Si se contradicen, GANA EL DE LA NOCHE — pero decilo en
   voz alta en vez de asumirlo.
3. Verificá que HEAD sea f337846 o posterior. Si es
   posterior, leé todo lo nuevo antes de tocar nada.
4. git log --oneline aef4c42..HEAD  → 39 commits de un solo
   día, y los mensajes son la fuente de verdad de los números.

==========================================================
1. EL OBJETIVO, Y CAMBIÓ
==========================================================
El robot se sale en las curvas CERRADAS. Y el 25-ago se
midió, con los CSV del propio robot, POR QUÉ:

    LA CURVA MÁS CERRADA DEL REGLAMENTO NO ES FÍSICAMENTE
    POSIBLE A LA VELOCIDAD A LA QUE EL ROBOT VA.

    v_max = ω_max · R
    el robot va a          8,5 cm/s   (encoder)
    v_max admisible        4,7 cm/s   (R = 4,9 cm, RCJ 2.2.2)
                        -> 82 % POR ENCIMA
    la curva EXIGE        99 °/s      y el robot da 55

    Y la curva SUAVE (R = 15) sí da: 59 % del límite.

Robusto al diámetro de rueda entre 44 y 85 mm.

NO es un problema de percepción. NO es un problema de la ley
de steer. NO es el retardo (65-70 ms = 0,53 cm de avance).

EL HARDWARE NO SE TOCA. Cámara baja y casi horizontal,
160x120, 4 ruedas fijas de silicona. Se resuelve en software.

Competencia: Roboliga, noviembre 2026. Pocas sesiones de robot.

==========================================================
2. LO QUE NO HAY QUE VOLVER A HACER
==========================================================
TRECE hipótesis muertas en la sección 6 del traspaso de la
MAÑANA: H5, H6, H6b, H8, H9, H9-GATE, H10, SUELO, salida
lateral de los campeones, ROI adaptativo, poda previa del
grafo, SLEW, V1+suavizar-Y, dwell, bird-eye.

Y CINCO más que murieron el 25-ago (sección 4 de la noche):

  * la ANTICIPACIÓN DE CURVA como evidencia. El test buscaba
    "al menos un kappa > U en 40 frames" SIN break. Rehecho
    con precisión/tasa base/placebo: lift 1,47x. MUERE.
    OJO: el MECANISMO revivió por física — frenar antes de
    la curva es la salida 1 de la desigualdad. Lo que murió
    es el test, no la idea.
  * "el atan2 no ve el rumbo": SÍ lo ve, crece monótonamente
  * "mezclar posición y rumbo causa la falla": RR 0,45-0,84x
  * "lo que cambia es CUÁNDO": lag óptimo 0 frames
  * "el retardo explica la falla": en la falla el robot DEJÓ
    de obedecer (corr 0,92 -> 0,52), no obedeció tarde

NO las repropongas. Si creés que una merece revisión, leé
primero su commit.

==========================================================
3. LO QUE SÍ QUEDÓ EN PIE
==========================================================
CAMINO+MONO: integrado y verificado. VISION_LINEA=camino

Stanley: EXPERIMENTAL, apagado por defecto, cinco falsadores
vivos y gate 15/15. LEY_STEER=stanley. Cuesta 19 µs.
NO es el Stanley de Thrun: es un controlador inspirado en su
estructura. La demostración de convergencia NO aplica.

Telemetría: 48 columnas. Las CINCO etapas del target,
ctrl_source, y ang_viejo -lo que la ley vieja habría mandado
en ese mismo frame-, que hace que el A/B de leyes salga de
UNA sola corrida real.

Firmware, cuatro flags nuevos SIN BANCO:
kFixPingFrontalCorto, kFixPingFrontalPeriodico,
kFixTofPresupuesto (los tres en true) y kFixI2cRapido
(en FALSE a propósito: puede colgar el bus).

Los CSV del 22-ago en software/teensy/firmware/corridas/ son
el BASELINE. Diez corridas con el giroscopio del BNO.

==========================================================
4. TU PRIMERA TAREA
==========================================================
Sin bloqueo de hardware, en este orden:

A. CERRAR LA CUENTA DE FACTIBILIDAD. Pedile a Benjamín el
   diámetro de rueda (lo tiene en Fusion) y el valor actual
   de LINE_PIVOT_SPEED. Con esos dos:
     - cuánto exactamente hay que frenar en curva, o
     - cuánto tiene que subir el giro para no frenar nada
   Corré factibilidad.py --diametro con el número real.

B. BARRIDO DE LOOKAHEAD. LOOKAHEAD=70 px es un parámetro
   suelto que nadie barrió. Banda 70/90/110/130 con el gate
   y las cinco métricas. Falsador preregistrado ANTES.
   OJO: más lookahead es MÁS amortiguación, o sea MENOS
   reacción en curva cerrada. Puede empeorar lo que se busca.

C. EL WATCHDOG, tercer problema. Al volver de una maniobra
   bloqueante se drenan bytes viejos y g_last_rx_ms se
   refresca con un comando anterior a la maniobra. Necesita
   timestamp en el protocolo o exigir trama nueva
   post-maniobra. ChatGPT lo señaló y sigue sin arreglar.

D. t_mono_ns en la telemetría de la Pi, para cruzar con el
   Teensy sin ambigüedad.

NO esperes autorización. Hacé, medí, commiteá y comentá en #138.

==========================================================
5. LO QUE TENÉS QUE TENER EN CUENTA
==========================================================
* EL REPLAY ES LAZO ABIERTO. Mide percepción, no trayectoria.
  Los CSV del Teensy SÍ son del robot: usalos.

* LA PERCEPCIÓN ACIERTA. El target cae sobre la cinta
  correcta 50/50 en la verdad de terreno, es estable el
  99,8 % y apunta bien el 97,3 %. Dejá de buscar ahí.

* EL ESTIMADOR DE YAW POR CORRELACIÓN DE FASE ES DÉBIL: da
  1.075 frames sobre 80 °/s en un robot cuyo techo es 39.
  Si hay giroscopio disponible, usalo.

* ANTES DE INSTRUMENTAR, PREGUNTÁ QUÉ MIDE REALMENTE EL
  CAMPO. `dt` del registrador parecía el período del lazo y
  era el suyo propio: un IntervalTimer de hardware a 200 Hz.

* LA SECCIÓN 5 DE LA NOCHE LISTA DIEZ ERRORES MÍOS. Leelos:
  son el catálogo de cómo se autoengaña uno midiendo.

* NUNCA uses `git add -A`. En esta sesión arrastró 60 MB de
  .avi y cambios de otro al commit 7642693.

==========================================================
6. REGLAS QUE NO SE NEGOCIAN
==========================================================
1. Falsador escrito ANTES de medir, en números.
2. Umbrales preregistrados en BANDA. Sólo hay conclusión si
   hay plateau.
3. Controles: hist_exito 100/100 y lineal_positivo 73/73
   conservando el máximo de +89. NUNCA propongas limitar la
   magnitud del steer.
4. Instrumentar sin cambiar lo que se mide: verificá que el
   espía reproduzca la salida exacta antes de creerle al A/B.
5. Diagnóstico confirmado ≠ política adoptada.
6. Sanidad física antes de publicar un número.
7. NUNCA inventes resultados físicos. Si no está medido, decilo.
8. Un cambio por fase. VISION_LINEA, LEY_STEER y
   VEL_ANTICIPADA van por separado a propósito.
9. Español.

Usá las skills del repo: seguimiento-de-trayectoria,
geometria-camara-suelo, experimento-falsable, arduino-embebido.
```
