#!/usr/bin/env python3
"""
Analiza el CSV del entorno `banco_barrido` y decide entre las dos hipotesis.

    python tools/analizar_barrido.py banco_piso.csv
    python tools/analizar_barrido.py banco_piso.csv --aire banco_aire.csv

EL DISCRIMINADOR: las dos hipotesis predicen ORDENES OPUESTOS al subir `rotation`.

  PID CIEGO AL SIGNO -> el giro real MEJORA hacia rotation = 1.
      En rotation = 1 la consigna de la rueda interna es la velocidad COMPLETA,
      asi que el lazo no puede colapsar: haria falta que el chasis avance mas
      rapido que la rueda de afuera. El colapso vive en la banda 0,5-0,85.

  TECHO DE PAR       -> el giro real EMPEORA hacia rotation = 1.
      rotation = 1 es el caso de scrub MAXIMO. Si ahi no gira, la silicona es el
      limite y no hay firmware que lo arregle.

Con --aire compara la misma corrida con las ruedas levantadas: si en el aire
anda y en el piso no, el problema depende de la CARGA, que es la prueba directa
de que no es un bug de logica.
"""
import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analizar_diagnostico as AD

BANCO_ROT, BANCO_VEL = 50, 60
RUEDAS = ("fl", "fr", "bl", "br")


def segmentos(filas, marca):
    """Tramos contiguos con ram == marca."""
    out, ini = [], None
    for i, f in enumerate(filas):
        if f.get("ram") == marca and ini is None:
            ini = i
        elif f.get("ram") != marca and ini is not None:
            if i - ini >= 20:            # 20 muestras = 100 ms: descarta bordes
                out.append((ini, i))
            ini = None
    if ini is not None and len(filas) - ini >= 20:
        out.append((ini, len(filas)))
    return out


def resumir(filas, a, b, eje):
    t = filas[a:b]
    # se descarta el primer 30%: es el transitorio de arranque, no el regimen
    t = t[int(len(t) * 0.3):] or t
    rot = statistics.median(f.get("rot", 0) for f in t) / 1000.0
    interna = ("fl", "bl") if rot > 0 else ("fr", "br")
    d = {}
    for w in RUEDAS:
        sets = [f.get(w + "_set", 0) for f in t]
        rpms = [f.get(w + "_rpm", 0) for f in t]
        pwms = [f.get(w + "_pwm", 0) for f in t]
        draw = t[-1].get(w + "_raw", 0) - t[0].get(w + "_raw", 0)
        segs = (t[-1]["t"] - t[0]["t"]) / 1e6
        d[w] = {"set": statistics.median(sets), "rpm": statistics.median(rpms),
                "pwm": statistics.median(pwms), "pwm_min": min(pwms),
                "real": (draw / AD.TICKS_VUELTA) * 60.0 / segs if segs > 0 else 0.0}
    return {
        "rot": rot, "interna": interna,
        "vel": statistics.median(max(f.get("ls", 0), f.get("rs", 0)) for f in t),
        "giro": statistics.median(abs(f.get(eje, 0)) for f in t) / 10.0,
        "ruedas": d,
    }


def tabla_rot(filas, eje, titulo):
    segs = segmentos(filas, BANCO_ROT)
    if not segs:
        return None
    print("\n" + titulo)
    print("  rot   |giro real| rueda INTERNA: pedida  medida  real   PWM min | colapso")
    print("  " + "-" * 74)
    porrot = {}
    for a, b in segs:
        r = resumir(filas, a, b, eje)
        k = round(abs(r["rot"]), 2)
        w = r["interna"][0]
        d = r["ruedas"][w]
        col = "SI" if (d["set"] >= 1 and d["rpm"] - d["set"] > 8 and d["pwm_min"] < 30) else "no"
        print("  %+.2f | %6.1f  | %-3s          %6.1f  %6.1f %6.1f   %5d  | %s"
              % (r["rot"], r["giro"], w.upper(), d["set"], d["rpm"], d["real"],
                 d["pwm_min"], col))
        porrot.setdefault(k, []).append(
            {"giro": r["giro"], "colapso": 1 if col == "SI" else 0,
             "pwm_min": d["pwm_min"], "real": d["real"], "set": d["set"]})
    # por cada rotation: el giro del CHASIS y lo que hizo la rueda INTERNA.
    # Los dos hacen falta: el giro no vale en el aire (el chasis no guiña sin
    # reaccion del piso) y la rueda si.
    return {k: {"giro": statistics.median(x["giro"] for x in v),
                "colapso": sum(x["colapso"] for x in v),
                "de": len(v),
                "pwm_min": min(x["pwm_min"] for x in v),
                "real": statistics.median(x["real"] for x in v),
                "set": statistics.median(x["set"] for x in v)}
            for k, v in porrot.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--aire", help="CSV de la misma corrida con las ruedas levantadas")
    ap.add_argument("--eje", choices=("gx", "gy", "gz"),
                    help="forzar el eje del giroscopio. Correr el barrido con --eje gz y "
                         "con --eje gy: si el veredicto CAMBIA, no hay veredicto.")
    args = ap.parse_args()

    filas = AD.leer(args.csv)
    if len(filas) < 50:
        sys.exit("Muy pocas muestras: el barrido no llego a correr.")
    print("=" * 78)
    for l in dict.fromkeys(AD.CABECERA):
        print(l)
    dur = (filas[-1]["t"] - filas[0]["t"]) / 1e6
    print("%d muestras, %.1f s, %.0f Hz" % (len(filas), dur, len(filas) / dur if dur else 0))
    for a in AD.AVISOS:
        print("aviso: " + a)

    # el eje del giroscopo se elige con los datos, igual que en el otro analizador
    giro_sirve = True
    ev = [(a, b) for a, b in segmentos(filas, BANCO_ROT)]
    eje, razon = AD.elegir_eje_giro(filas, ev, args.eje)
    if razon:
        print("eje de giro elegido con los datos: %s (%.1f d/s de rotacion neta, "
              "%.1f de vibracion)" % (eje, razon[eje][0], razon[eje][1]))
        print("  los otros: %s   (rotacion/vibracion)" % ", ".join(
            "%s %.1f/%.1f" % (e, v[0], v[1]) for e, v in razon.items() if e != eje))
        if razon[eje][0] < 2.0:
            giro_sirve = False
            print("  ATENCION: ningun eje muestra rotacion NETA. Todo lo que diga la")
            print("  columna `giro` -la fase 2 y el VEREDICTO- queda anulado; leer solo")
            print("  la columna `colapso`, que no depende del giroscopio.")
    elif args.eje:
        print("eje de giro FORZADO por el usuario: %s" % eje)

    piso = tabla_rot(filas, eje, "FASE 1 - BARRIDO DE ROTATION (velocidad fija)")
    if piso is None:
        sys.exit("\nNo hay segmentos de barrido (ram=50). Se subio el entorno "
                 "`banco_barrido`? Se prendio el switch?")

    # --- fase 2: la velocidad ------------------------------------------------
    segs2 = segmentos(filas, BANCO_VEL)
    if segs2:
        print("\nFASE 2 - BARRIDO DE VELOCIDAD (rotation = 1)")
        print("  velocidad | giro real")
        print("  " + "-" * 26)
        porvel = {}
        for a, b in segs2:
            r = resumir(filas, a, b, eje)
            porvel.setdefault(round(r["vel"]), []).append(r["giro"])
        vs = sorted(porvel)
        for v in vs:
            print("  %6d    | %6.1f d/s" % (v, statistics.median(porvel[v])))
        if len(vs) >= 3 and not giro_sirve:
            print("  -> sin rotacion neta medible, la fase 2 NO concluye nada.")
        elif len(vs) >= 3:
            g = [statistics.median(porvel[v]) for v in vs]
            crec = (g[-1] - g[0]) / (g[0] + 1e-6)
            print("  -> de %d a %d el giro cambia %+.0f%%: %s"
                  % (vs[0], vs[-1], crec * 100,
                     "escala con la velocidad, NO hay techo de par"
                     if crec > 0.5 else
                     "SE APLANA: hay techo de par, el limite es mecanico"))

    # --- EL VEREDICTO --------------------------------------------------------
    print("\n" + "=" * 78)
    print("VEREDICTO")
    print("=" * 78)
    ks = sorted(piso)
    if len(ks) < 3:
        print("  pocos valores de rotation: no alcanza para decidir.")
        return
    # SIN rotation=1,00 no hay veredicto. El barrido lo deja para el final de cada
    # pasada, asi que un corte por switch, bateria o cable produce un archivo que
    # PARECE completo y en el que el giro solo puede bajar: sale "ES MECANICO" con
    # todas las letras sobre un dato que no existe.
    if 1.0 not in piso or piso[1.0]["de"] < 2:
        print("\n  BARRIDO INCOMPLETO: falta rotation=1,00 (hay %s)." % sorted(piso))
        print("  Ese punto es la mitad del discriminador: sin el, el giro solo puede")
        print("  bajar y cualquier veredicto diria MECANICO. Repetir el barrido entero.")
        return
    bajo = statistics.median([piso[k]["giro"] for k in ks if k <= 0.5] or [0])
    banda = statistics.median([piso[k]["giro"] for k in ks if 0.5 < k < 0.95] or [0])
    alto = statistics.median([piso[k]["giro"] for k in ks if k >= 0.95] or [0])
    print("  giro real por zona:  rot<=0.50 -> %.1f d/s   0.50-0.95 -> %.1f   rot=1.00 -> %.1f"
          % (bajo, banda, alto))

    # IMU MUDA: si el chasis no giro en NINGUNA consigna, el giroscopo no esta
    # midiendo o el robot no se movio. En los dos casos el veredicto por giro no
    # vale, y el `else` de mas abajo sentenciaria "el problema esta en la VISION",
    # que es justo lo unico que este banco NO puede concluir.
    if max(bajo, banda, alto) < 3.0:
        print("\n  -> NO HAY VEREDICTO POR GIRO: el chasis no giro en ninguna consigna.")
        if any("sin_imu=1" in l for l in AD.CABECERA):
            print("     EL ARCHIVO YA LO DICE: sin_imu=1, la IMU no arranco en esa corrida.")
            print("     El barrido corrio igual a proposito (antes se colgaba en un while(1)")
            print("     mudo). La tabla de colapso de mas arriba sigue siendo valida.")
        print("     O la IMU no esta midiendo, o el robot no se movio (ruedas al aire,")
        print("     switch apagado, bateria baja). ANTES de creerle a nada:")
        print("     levantar el robot y girarlo 90 grados a mano en un segundo; la")
        print("     columna gz del resumen en vivo tiene que saltar por encima de 200")
        print("     (esta x10). Si no salta, es la IMU.")
        print("     Igual mira la tabla de arriba: la columna `colapso` de la rueda")
        print("     interna SI es valida sin giroscopo y ya dice bastante.")
        colap = sum(v["colapso"] for v in piso.values())
        if colap:
            print("\n     De hecho hubo COLAPSO en %d de %d segmentos: la rueda interna se"
                  % (colap, sum(v["de"] for v in piso.values())))
            print("     queda sin esfuerzo aunque no sepamos cuanto giro el chasis.")
        return
    # La firma del PID ciego al signo NO es solo "mejora hacia 1": es que se HUNDE
    # en la banda intermedia, donde la consigna de la rueda interna es chica. Si
    # ademas no se recupera del todo en 1,00, antes esto salia como PAREJO.
    if bajo > banda * 1.3 and banda < alto * 1.3 and bajo > 5:
        print("\n  -> SE HUNDE EN LA BANDA INTERMEDIA (%.1f -> %.1f -> %.1f d/s)."
              % (bajo, banda, alto))
        print("     Es la firma del PID CIEGO AL SIGNO: el colapso vive donde la")
        print("     consigna de la rueda interna es mas chica, no en los extremos.")
        print("     Mirar la columna `colapso` para confirmarlo. SE ARREGLA POR FIRMWARE.")
    elif alto > banda * 1.3 and alto > 5:
        print("\n  -> MEJORA hacia rotation = 1.")
        print("     Es la firma del PID CIEGO AL SIGNO: en rotation=1 la consigna de la")
        print("     rueda interna es la velocidad completa y el lazo no puede colapsar.")
        print("     El colapso vive en la banda intermedia. SE ARREGLA POR FIRMWARE.")
        print("     Siguiente paso: grabar lo mismo con -e diagnostico_lazo y comparar.")
    elif banda > alto * 1.3:
        print("\n  -> EMPEORA hacia rotation = 1.")
        print("     Es la firma del TECHO DE PAR: rotation=1 es el scrub maximo.")
        print("     ES MECANICO. Ningun cambio de firmware lo va a arreglar: hay que")
        print("     hablar de ruedas, de reparto de peso o de geometria.")
    else:
        print("\n  -> el giro real es PAREJO en todo el rango.")
        print("     No se separa ninguna de las dos. Mirar la columna `colapso` de la")
        print("     tabla: si nunca dice SI, la actuacion esta sana y el problema del")
        print("     seguidor esta en la VISION, no en los motores.")

    # --- piso contra aire ----------------------------------------------------
    if args.aire:
        AD.CABECERA, AD.AVISOS = [], []
        fa = AD.leer(args.aire)
        pa = tabla_rot(fa, eje, "\nMISMA CORRIDA CON LAS RUEDAS AL AIRE")
        if pa:
            # NO se compara `giro`: con las cuatro ruedas en el aire el chasis no
            # guiña -no hay reaccion del piso- asi que el aire daria ~0 siempre y
            # la conclusion saldria SIEMPRE al reves. Se compara lo que la RUEDA
            # INTERNA hizo, que es valido en las dos condiciones.
            print("\n  rotation | COLAPSO piso | COLAPSO aire | pwm min piso | pwm min aire")
            print("  " + "-" * 68)
            for k in sorted(set(piso) | set(pa)):
                p, a = piso.get(k), pa.get(k)
                print("  %6.2f   |  %d de %d      |  %d de %d      | %8d     | %8s"
                      % (k,
                         p["colapso"] if p else 0, p["de"] if p else 0,
                         a["colapso"] if a else 0, a["de"] if a else 0,
                         p["pwm_min"] if p else 0,
                         ("%d" % a["pwm_min"]) if a else "-"))
            cp = sum(v["colapso"] for v in piso.values())
            ca = sum(v["colapso"] for v in pa.values())
            np_ = sum(v["de"] for v in piso.values())
            na = sum(v["de"] for v in pa.values())
            print("\n  colapsos: %d de %d en el PISO, %d de %d en el AIRE" % (cp, np_, ca, na))
            if cp > 0 and ca == 0:
                print("\n  -> EN EL AIRE LA RUEDA OBEDECE Y EN EL PISO SE APAGA.")
                print("     El problema DEPENDE DE LA CARGA: no es un bug de logica, es la")
                print("     interaccion entre el lazo y el arrastre. Es la prueba directa")
                print("     de toda la hipotesis del PID ciego al signo.")
            elif cp > 0 and ca > 0:
                print("\n  -> colapsa en las DOS. No depende de la carga: hay que buscar en")
                print("     la logica o en la electronica (mirar tambien la causa R,")
                print("     flancos espurios del encoder).")
            elif cp == 0 and ca == 0:
                print("\n  -> NO colapsa en ninguna de las dos. La rueda interna hace lo que")
                print("     se le pide. Si el robot igual no gira, el limite es MECANICO.")
            else:
                print("\n  -> colapsa en el aire y NO en el piso: al reves de lo esperado.")
                print("     Revisar que la cuna no este frenando una rueda (girarlas con el")
                print("     dedo antes de grabar): una rueda rozando simula exactamente esto.")


if __name__ == "__main__":
    main()
