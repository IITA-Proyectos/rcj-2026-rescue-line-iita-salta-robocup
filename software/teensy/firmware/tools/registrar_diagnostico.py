#!/usr/bin/env python3
"""
Graba el CSV de alta frecuencia del entorno `diagnostico` del Teensy.

    python tools/registrar_diagnostico.py COM7 curva1.csv
    python tools/registrar_diagnostico.py COM7 curva1.csv --nota "piso liso, pasada 3"

Guarda todo tal cual llega y muestra un resumen por segundo. El resumen NO es el
analisis -para eso esta analizar_diagnostico.py- sino la forma de saber EN LA
PISTA si la corrida sirve, antes de guardar el robot.

EL CRITERIO DE CORRIDA VALIDA esta arriba de todo (CURVAS_MINIMAS): si al cortar
no se llego, lo dice con todas las letras. El modo mas probable de terminar el
dia sin veredicto es grabar cinco corridas de rectas y darse cuenta a la noche.

Se corta con Ctrl-C.
"""
import argparse
import os
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("Falta pyserial:  pip install pyserial")

RUEDAS = ("fl", "fr", "bl", "br")
COLAPSO_ARRASTRE, COLAPSO_PWM = 8, 30      # mismo criterio que el analizador
UMBRAL_CURVA = 0.35                        # idem
CURVAS_MINIMAS = 5                         # curvas de VISION para dar la corrida por buena


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("puerto", help="COM7 en Windows, /dev/ttyACM0 en Linux")
    ap.add_argument("salida", help="archivo CSV a escribir")
    ap.add_argument("--baud", type=int, default=921600,
                    help="lo ignora el USB del Teensy; hace falta solo con DIAG_PUERTO=1")
    ap.add_argument("--nota", default=None,
                    help="contexto de la corrida (superficie, pasada, bateria medida "
                         "con tester, lo que sea). Va como linea '#' al principio.")
    ap.add_argument("--pisar", action="store_true", help="sobrescribir un CSV existente")
    args = ap.parse_args()

    if os.path.exists(args.salida) and not args.pisar:
        sys.exit("Ya existe %s. Elegi otro nombre o pasa --pisar." % args.salida)

    try:
        ser = serial.Serial(args.puerto, args.baud, timeout=0.2)
    except serial.SerialException as e:
        sys.exit("No se pudo abrir %s: %s" % (args.puerto, e))

    print("Grabando de %s a %s. Ctrl-C para cortar." % (args.puerto, args.salida))
    print("Esperando la cabecera (el firmware la reemite cada 2 s)...")

    cab, idx = None, {}
    n_lineas = 0
    t0 = time.time()
    t_resumen = t0
    en_ventana = 0
    drop_base = drop_ultimo = None
    colapso_cnt = {w: 0 for w in RUEDAS}
    # --- saber si se capturo el FENOMENO, no solo si se grabo ---------------
    curvas_vision = 0        # tramos con |rot| > umbral y rama >= 2
    curvas_programadas = 0   # tramos con rama == -1 (runAngle/runTime)
    ram_max = -99
    en_curva = False
    curva_es_vision = False
    ult = {}
    resto = b""

    with open(args.salida, "w", encoding="utf-8", newline="") as f:
        if args.nota:
            f.write("# nota: %s\n" % args.nota.replace("\n", " "))
            print("# nota: %s" % args.nota)
        try:
            while True:
                # Lectura POR BLOQUES. readline() de pyserial lee de a UN byte:
                # a 200 Hz x ~321 B son ~64.000 llamadas por segundo y el proceso
                # no da abasto; la contrapresion llena el anillo del Teensy y sube
                # `drop` sin que nadie sospeche del que graba.
                trozo = ser.read(4096)
                if not trozo:
                    continue
                datos = resto + trozo
                partes = datos.split(b"\n")
                resto = partes.pop()
                for cruda in partes:
                    linea = cruda.decode("utf-8", "replace").rstrip("\r")
                    if not linea:
                        continue
                    f.write(linea + "\n")

                    if linea.startswith("#"):
                        print(linea)
                        continue
                    # La cabecera se reconoce POR SU CONTENIDO: abrir el USB no
                    # resetea un Teensy 4.1, asi que si el robot ya venia andando
                    # lo primero que llega es una fila de datos.
                    if linea.startswith("us,"):
                        if cab is None:
                            cab = linea.split(",")
                            idx = {n: i for i, n in enumerate(cab)}
                            print("Cabecera OK: %d campos. Grabando..." % len(cab))
                        continue
                    if cab is None:
                        continue
                    campos = linea.split(",")
                    if len(campos) != len(cab):
                        continue
                    n_lineas += 1
                    en_ventana += 1

                    def v(nombre, dflt=0):
                        i = idx.get(nombre)
                        if i is None:
                            return dflt
                        try:
                            return int(campos[i])
                        except ValueError:
                            return dflt

                    for w in RUEDAS:
                        if (v(w + "_set") >= 1
                                and v(w + "_rpm") - v(w + "_set") > COLAPSO_ARRASTRE
                                and v(w + "_pwm") < COLAPSO_PWM):
                            colapso_cnt[w] += 1

                    rot = v("rot") / 1000.0
                    ram = v("ram")
                    ram_max = max(ram_max, ram)
                    dentro = abs(rot) > UMBRAL_CURVA
                    if dentro and not en_curva:
                        en_curva, curva_es_vision = True, False
                    if dentro and ram >= 2:
                        curva_es_vision = True
                    if not dentro and en_curva:
                        en_curva = False
                        if curva_es_vision:
                            curvas_vision += 1
                        else:
                            curvas_programadas += 1

                    d = v("drop")
                    if drop_base is None:
                        drop_base = drop_ultimo = d
                    ult = {"rot": rot, "ram": ram, "gz": v("gz"),
                           "rxage": v("rxage"), "drop": d}

                ahora = time.time()
                if ahora - t_resumen >= 1.0 and ult:
                    hz = en_ventana / (ahora - t_resumen)
                    nuevos = ult["drop"] - drop_ultimo
                    drop_ultimo = ult["drop"]
                    col = ", ".join("%s %d" % (w.upper(), c)
                                    for w, c in colapso_cnt.items() if c)
                    print("%6.1f Hz | %6d lin | drop %d(+%d) | CURVAS vision %d / "
                          "programadas %d | ram max %d | rot %+.2f | gz %+.1f%s"
                          % (hz, n_lineas, ult["drop"] - drop_base, nuevos,
                             curvas_vision, curvas_programadas, ram_max,
                             ult["rot"], ult["gz"] / 10.0,
                             ("  COLAPSO: " + col) if col else ""))
                    if nuevos:
                        print("   ^ se estan PERDIENDO muestras: el puerto no da abasto. "
                              "Bajar DIAG_HZ, o usar el USB si estas por Serial8.")
                    t_resumen = ahora
                    en_ventana = 0

        except KeyboardInterrupt:
            pass
        finally:
            ser.close()

    dur = time.time() - t0
    print("\n" + "=" * 72)
    print("%d muestras en %.1f s (%.1f Hz promedio) -> %s"
          % (n_lineas, dur, n_lineas / dur if dur else 0, args.salida))
    if cab is None:
        print("NUNCA LLEGO LA CABECERA. Revisar que el Teensy tenga el entorno")
        print("  `diagnostico`:   pio run -e diagnostico --target upload")
        return
    if n_lineas == 0:
        print("Llego la cabecera pero ninguna muestra. Revisar el cable/puerto.")
        return

    perdidas = (drop_ultimo - drop_base) if drop_base is not None else 0
    print("curvas de VISION (rama >= 2)   : %d" % curvas_vision)
    print("curvas PROGRAMADAS (rama -1)   : %d" % curvas_programadas)
    print("rama maxima vista              : %d" % ram_max)
    print("muestras perdidas en la corrida: %d" % perdidas)
    tot = sum(colapso_cnt.values())
    if tot:
        print("muestras con firma de colapso  : " +
              ", ".join("%s=%d" % (w.upper(), c) for w, c in colapso_cnt.items() if c))

    print("-" * 72)
    problemas = []
    if curvas_vision < CURVAS_MINIMAS:
        problemas.append("solo %d curvas de vision (hacen falta %d): el robot no llego "
                         "a la parte de la pista con curvas cerradas, o la vision nunca "
                         "las pidio" % (curvas_vision, CURVAS_MINIMAS))
    if perdidas:
        problemas.append("se perdieron %d muestras" % perdidas)
    if dur and n_lineas / dur < 150:
        problemas.append("%.0f Hz efectivos, por debajo de 150: hay huecos en el muestreo"
                         % (n_lineas / dur))
    if problemas:
        print("CORRIDA NO VALIDA. NO guardes el robot todavia:")
        for p in problemas:
            print("  - %s" % p)
    else:
        print("CORRIDA VALIDA. Analizar con:")
        print("  python tools/analizar_diagnostico.py %s" % args.salida)


if __name__ == "__main__":
    main()
