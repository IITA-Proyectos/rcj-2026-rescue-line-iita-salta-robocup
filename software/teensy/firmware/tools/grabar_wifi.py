#!/usr/bin/env python3
"""
Graba la telemetria del robot POR WIFI, sin ningun cable.

    python tools/grabar_wifi.py corrida1.jsonl --nota "pista de la sede, pasada 1"

Conectate al AP `RescueBot-Telemetria` y corre esto. Va a pedirle a la ESP32 el
frame JSON a 10 Hz y a escribir uno por linea. Ctrl-C para cortar.

POR QUE ESTE CAMINO Y NO EL USB: para seguir una linea el robot recorre metros.
Un cable lo ata y, peor, le tironea del chasis justo en las curvas cerradas, que
es la mecanica que se esta midiendo. Esta ruta ya existe, ya funciona y no toca
al robot: la ESP32 solo mira y publica.

QUE SE PIERDE: el JSON va a 10 Hz y el CSV por USB a 200 Hz. Pero el frame trae
las ENVOLVENTES (pmin/pmax/rmin/rmax), que son el minimo y el maximo de cada
ventana de 100 ms, asi que un desplome de PWM de 40 ms igual queda registrado.
Para el barrido de banco -donde el robot pivotea en el lugar- conviene el USB a
200 Hz; para una corrida de pista, esto.

Despues:
    python tools/wifi_a_csv.py corrida1.jsonl corrida1.csv
    python tools/analizar_diagnostico.py corrida1.csv
"""
import argparse
import json
import os
import sys
import time
import urllib.request

URL_DATA = "http://192.168.4.1/data"
URL_INFO = "http://192.168.4.1/info"


def pedir(url, timeout=0.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("salida", help="archivo .jsonl a escribir")
    ap.add_argument("--url", default=URL_DATA)
    ap.add_argument("--hz", type=float, default=12.0,
                    help="cada cuanto pedir (un poco mas que los 10 Hz del robot)")
    ap.add_argument("--nota", default=None)
    ap.add_argument("--pisar", action="store_true")
    args = ap.parse_args()

    if os.path.exists(args.salida) and not args.pisar:
        sys.exit("Ya existe %s. Elegi otro nombre o pasa --pisar." % args.salida)

    try:
        info = pedir(URL_INFO)
        print("ESP32 OK: ssid=%s frames=%s ultimo=%s ms"
              % (info.get("ssid"), info.get("frames"), info.get("lastMs")))
    except Exception as e:
        sys.exit("No llego a la ESP32 (%s).\n"
                 "  - Estas conectado al AP RescueBot-Telemetria?\n"
                 "  - Esta prendido el robot y flasheado con TELEMETRIA=1?" % e)

    print("Grabando en %s. Ctrl-C para cortar." % args.salida)
    periodo = 1.0 / args.hz
    n = repetidos = vacios = errores = 0
    ult_t = None
    t0 = time.time()
    t_res = t0
    en_ventana = 0

    with open(args.salida, "w", encoding="utf-8") as f:
        if args.nota:
            f.write(json.dumps({"nota": args.nota}) + "\n")
            print("nota: %s" % args.nota)
        try:
            while True:
                ini = time.time()
                try:
                    d = pedir(args.url)
                except Exception:
                    errores += 1
                    d = None
                if d and d.get("t") is not None:
                    # La ESP32 sirve el ULTIMO frame recibido. Si el enlace serie
                    # con el Teensy se corta, seguiria devolviendo el mismo para
                    # siempre: por eso se cuenta como NUEVO solo si `t` cambio.
                    if d["t"] != ult_t:
                        ult_t = d["t"]
                        f.write(json.dumps(d, separators=(",", ":")) + "\n")
                        n += 1
                        en_ventana += 1
                    else:
                        repetidos += 1
                else:
                    vacios += 1     # /data devuelve {} si el frame esta rancio

                ahora = time.time()
                if ahora - t_res >= 2.0:
                    hz = en_ventana / (ahora - t_res)
                    estado = "OK" if hz > 5 else ("SIN DATOS NUEVOS" if hz == 0 else "LENTO")
                    print("%5.1f frames/s | %5d guardados | repetidos %d | vacios %d | %s"
                          % (hz, n, repetidos, vacios, estado))
                    if hz == 0:
                        print("   ^ la ESP32 responde pero el frame no cambia: se corto el")
                        print("     cable TX8 del Teensy, o el Teensy se reseteo.")
                    t_res, en_ventana = ahora, 0

                dormir = periodo - (time.time() - ini)
                if dormir > 0:
                    time.sleep(dormir)
        except KeyboardInterrupt:
            pass

    dur = time.time() - t0
    print("\n" + "=" * 66)
    print("%d frames en %.1f s (%.1f/s) -> %s" % (n, dur, n / dur if dur else 0, args.salida))
    print("repetidos %d | vacios %d | errores de red %d" % (repetidos, vacios, errores))
    if n == 0:
        print("NO SE GRABO NADA. Revisar que el Teensy tenga TELEMETRIA=1 y que el")
        print("cable de TX8 (pin 35) llegue a la ESP32.")
    else:
        print("Convertir y analizar:")
        print("  python tools/wifi_a_csv.py %s %s"
              % (args.salida, args.salida.rsplit(".", 1)[0] + ".csv"))


if __name__ == "__main__":
    main()
