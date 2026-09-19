#!/usr/bin/env python3
"""
Cruza el CSV del Teensy con el CSV de la vision y contesta, para cada curva,
QUE VEIA LA CAMARA cuando los motores hicieron lo que hicieron.

    python tools/analizar_conjunto.py curva1.csv curva1_vision.csv

CLAVE DE UNION: la columna `rxf` del Teensy (tramas COMPLETAS recibidas) contra
la columna `i` de la vision (frames enviados). Son la misma cuenta mientras no
se pierda una trama; si los totales no cierran, la diferencia ES la cantidad de
tramas perdidas y se reporta.

POR QUE HACE FALTA: el CSV del Teensy puede decir "la vision nunca pidio el
giro", pero no puede decir POR QUE. Estas son las tres razones posibles y cada
una se arregla en un lugar distinto:
  - la mascara quedo VACIA        -> exposicion / umbrales de negro
  - el centroide se puso MUDO     -> el metodo de calculo del angulo
  - se entro en LINEA PERDIDA     -> la rutina de recuperacion
"""
import argparse
import sys

# el analizador del Teensy vive al lado: se reusa su lectura y su deteccion
sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".")
try:
    import analizar_diagnostico as AD
except ImportError:
    sys.exit("Poné analizar_conjunto.py en la misma carpeta que analizar_diagnostico.py")


def leer_vision(path):
    with open(path, encoding="utf-8", newline="") as f:
        lineas = [l.rstrip("\r\n") for l in f if not l.startswith("#")]
    if not lineas:
        sys.exit("El CSV de vision no tiene datos.")
    idx = next((k for k, l in enumerate(lineas) if l.startswith("i,")), None)
    if idx is None:
        sys.exit("El CSV de vision no tiene cabecera ('i,...').")
    cab = lineas[idx].split(",")
    por_i, malas = {}, 0
    for l in lineas[idx + 1:]:
        c = l.split(",")
        if len(c) != len(cab):
            malas += 1
            continue
        try:
            f = {k: int(v) for k, v in zip(cab, c)}
        except ValueError:
            malas += 1
            continue
        por_i[f["i"]] = f
    return por_i, cab, malas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_teensy")
    ap.add_argument("csv_vision")
    args = ap.parse_args()

    filas = AD.leer(args.csv_teensy)
    if len(filas) < 2:
        sys.exit("El CSV del Teensy no tiene muestras suficientes.")
    vis, cab_v, malas_v = leer_vision(args.csv_vision)

    print("=" * 78)
    print("TEENSY : %d muestras" % len(filas))
    print("VISION : %d frames%s" % (len(vis), ", %d descartados" % malas_v if malas_v else ""))

    rxf_max = max(f.get("rxf", 0) for f in filas)
    i_max = max(vis) if vis else 0
    perdidas = i_max - rxf_max
    print("union  : la vision mando %d frames y el Teensy recibio %d tramas completas"
          % (i_max, rxf_max))
    # La clave de union es i (frames que mando la vision) contra rxf (tramas que
    # conto el Teensy). Los DOS se reinician al arrancar su placa: si se flashea la
    # Teensy sin reiniciar la vision -o al reves- los numeros no se corresponden y
    # el cruce contesta con la curva EQUIVOCADA, sin avisar.
    if i_max and rxf_max < 0.8 * i_max:
        sys.exit("Los dos CSV no son del mismo arranque: la vision mando %d frames y el\n"
                 "Teensy conto %d (%.0f%%). Reiniciar la vision DESPUES de cada flasheo\n"
                 "de la Teensy, y grabar los dos registros de la misma corrida."
                 % (i_max, rxf_max, 100.0 * rxf_max / i_max))
    if perdidas > 0:
        print("         -> %d tramas se perdieron en el camino (%.1f%%)"
              % (perdidas, 100.0 * perdidas / i_max if i_max else 0))
    elif perdidas < 0:
        print("         -> el Teensy conto MAS tramas que las enviadas: los dos CSV")
        print("            no son de la misma corrida, o el Teensy venia de antes.")
    else:
        print("         -> no se perdio ninguna")

    # ---- patologias de vision sobre TODA la corrida -------------------------
    print("\n" + "=" * 78)
    print("LADO VISION, corrida completa")
    n = len(vis) or 1
    deg = sum(1 for f in vis.values() if f.get("degenerado"))
    per = sum(1 for f in vis.values() if f.get("perdida"))
    inval = sum(1 for f in vis.values() if not f.get("valida"))
    print("  mascara VACIA (atan2(0,0) -> -90 espurio) : %d frames (%.1f%%)"
          % (deg, 100.0 * deg / n))
    print("  linea NO valida (black_sum bajo el umbral): %d frames (%.1f%%)"
          % (inval, 100.0 * inval / n))
    print("  en rutina de LINEA PERDIDA                : %d frames (%.1f%%)"
          % (per, 100.0 * per / n))
    if deg:
        dirs = [f.get("dir_busq", 0) for f in vis.values() if f.get("degenerado")]
        mismo = dirs.count(dirs[0]) if dirs else 0
        print("  -> en esos frames la busqueda apunto a %s"
              % ("SIEMPRE el mismo lado (%d/%d)" % (mismo, len(dirs))
                 if mismo == len(dirs) else "los dos lados"))
        if dirs and mismo == len(dirs):
            print("     ESTO ES EL BUG: con la mascara vacia el angulo vale -90 por")
            print("     atan2(0,0)-90, y ese -90 fija last_line_search_dir. La")
            print("     recuperacion siempre busca para el mismo lado, mire lo que mire.")

    procs = sorted(f.get("proc_ms", 0) for f in vis.values())
    if procs:
        print("  tiempo de proceso por frame: mediana %d ms, peor %d ms (%.1f fps de mediana)"
              % (procs[len(procs) // 2], procs[-1],
                 1000.0 / procs[len(procs) // 2] if procs[len(procs) // 2] else 0))

    # ---- curva por curva ----------------------------------------------------
    ev = AD.eventos_de_curva(filas)
    if not ev:
        print("\nNo hubo curvas en el CSV del Teensy: nada que cruzar.")
        return
    AD.EJE_GIRO, _ = AD.elegir_eje_giro(filas, ev, None)

    print("\n" + "=" * 78)
    print("%d curvas, cruzadas contra lo que veia la camara\n" % len(ev))
    for k, (a, b) in enumerate(ev, 1):
        r = AD.analizar_evento(filas, a, b)
        tramo = filas[a:b]
        rxfs = sorted({f.get("rxf", 0) for f in tramo})
        vf = [vis[i] for i in rxfs if i in vis]

        print("-" * 78)
        print("CURVA %d | %.0f ms | rot medio %+.3f | giro real %.1f d/s | %d frames de camara"
              % (k, r["dur_ms"], r["rot"], r["gz_abs_med"], len(vf)))
        if not vf:
            print("  sin frames de vision para esta curva (los CSV no se solapan)")
            continue

        env = [f.get("ang_env", 0) for f in vf]
        cru = [f.get("ang_crudo", 0) for f in vf]
        print("  angulo enviado : min %+d  max %+d  |  |max| = %d deg"
              % (min(env), max(env), max(abs(x) for x in env)))
        print("  angulo crudo   : min %+d  max %+d" % (min(cru), max(cru)))
        print("  mascara vacia %d/%d | no valida %d/%d | linea perdida %d/%d"
              % (sum(1 for f in vf if f.get("degenerado")), len(vf),
                 sum(1 for f in vf if not f.get("valida")), len(vf),
                 sum(1 for f in vf if f.get("perdida")), len(vf)))

        # el veredicto de motores, y encima el de vision
        for cod, tit, det in AD.veredicto(r):
            print("  -> [%s] %s: %s" % (cod, tit, det))

        pico = max(abs(x) for x in env)
        if pico < 20:
            print("  -> [F] LA VISION NUNCA PIDIO EL GIRO: el |angulo| mas grande que")
            print("         mando en toda la curva fue %d deg. El problema es de" % pico)
            print("         PERCEPCION; la actuacion es secundaria en esta curva.")
            if sum(1 for f in vf if not f.get("valida")) > len(vf) // 2:
                print("         Y la causa es la MASCARA: mas de la mitad de los frames")
                print("         no tenian linea valida. Es exposicion o umbral de negro.")
            else:
                print("         La mascara estaba bien: el que se quedo mudo es el")
                print("         CALCULO del angulo (el centroide en media curva).")
        elif any(f.get("perdida") for f in vf):
            print("  -> [F] la curva se hizo con la rutina de LINEA PERDIDA activa:")
            print("         el angulo no salio de la cinta sino del barrido de busqueda.")


if __name__ == "__main__":
    main()
