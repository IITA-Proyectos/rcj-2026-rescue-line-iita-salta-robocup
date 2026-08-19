#!/usr/bin/env python3
"""
Analiza un CSV grabado con registrar_diagnostico.py y dice QUE FALLA en cada
curva, contra la tabla de decision:

  A  la interna, comandada en REV, mide mas de lo pedido y el PWM se desploma
     -> PID CIEGO AL SIGNO. El lazo apaga la rueda que tenia que hacer el giro.
  B  la interna obedece y el PWM se mantiene alto, pero el robot NO gira
     -> TECHO DE PAR / SCRUB. Es mecanico; el firmware no lo arregla.
  C  los toggles del pin de direccion suben, o el sentido queda indefinido
     -> el `if (_pwmVal < 10) _dir = !_dir` esta oscilando el pin.
  D  huecos reales entre muestras
     -> el control se congela adentro de los movimientos bloqueantes.
  E  rxage alto (o nunca llego una trama) durante la curva
     -> el robot actua sobre un comando viejo: es problema de comms.
  F  la curva la pidio la vision pero la rama del case 7 no subio
     -> problema de PERCEPCION.
  P  LAS CUATRO ruedas se quedan cortas a la vez con el PWM alto
     -> SOSPECHA DE ALIMENTACION (bateria que cae o limite del driver), NO scrub.
        El scrub castiga a la rueda interna; una caida de tension las castiga a
        todas por igual. Es el unico discriminador posible sin sensor de corriente.
  G  la RPM que usa el PID no coincide con la que sale de los flancos crudos
     -> EL ESTIMADOR MIENTE. El lazo decide sobre un numero inventado y ningun
        ajuste de ganancias lo arregla.

Uso:
    python tools/analizar_diagnostico.py curva1.csv
"""
import argparse
import csv
import statistics
import sys

RUEDAS = ("fl", "fr", "bl", "br")
# |rotation| que le llega a DriveBase (columna `rot`), NO el `steer` del case 7:
# son dos escalas distintas. 0.35 se eligio porque por debajo de 0.5 la rueda
# interna todavia no invierte, asi que cubre la banda de riesgo entera.
UMBRAL_CURVA = 0.35
MIN_MUESTRAS = 5          # descarta parpadeos de una o dos muestras
# Se sobreescribe con el ticks_vuelta= que emite el firmware en la cabecera:
# tenerlo escrito a mano en dos lados era pedir que se despeguen.
TICKS_VUELTA = 540
# El FIT0441 da 159 rpm a 12 V y DriveBase ya hace constrain(speed, 0, 159).
# Cualquier medicion por encima de esto es FISICAMENTE IMPOSIBLE: es un flanco
# espurio del encoder. Importa porque un solo flanco espurio le mete al PID un
# error de -200 rpm, el integrador se desploma y la rueda cae a coast: en el CSV
# eso se ve IDENTICO a la firma [A], pero se arregla con un capacitor, no
# reescribiendo el lazo.
RPM_IMPOSIBLE = 185
# Flags de la cabecera que cambian el comportamiento. Dos corridas que difieran
# en mas de uno no son comparables: la diferencia no seria atribuible.
FLAGS_PROCEDENCIA = ("fix_lazo", "fix_curva", "ks", "kv", "piso", "anticoast",
                     "hz", "diag_puerto", "ticks_vuelta")
WRAP_US = 2 ** 32         # micros() del Teensy envuelve a los ~71,6 min
PERIODO_US = 5000         # 200 Hz nominales (por USB). Se recalcula con los datos.
# El mismo analizador sirve para el CSV de 200 Hz (USB) y para el convertido de
# la telemetria WiFi, que va a 10 Hz. Los umbrales que estan en MUESTRAS tienen
# que salir del periodo REAL, no de una constante.
PERIODO_REAL_US = 5000

# Colapso por muestra: la rueda mide bastante mas de lo pedido Y el esfuerzo cayo.
COLAPSO_ARRASTRE = 8
COLAPSO_PWM = 30
COLAPSO_MIN_MUESTRAS = 4  # 4 x 5 ms = 20 ms = un periodo del PID

CABECERA = []
AVISOS = []
EJE_GIRO = "gz"   # lo decide elegir_eje_giro() con los datos de la corrida

# La cabecera tiene que ser ESTA. Si la primera linea de datos se cuela como
# cabecera (pasa si el Teensy ya venia andando cuando se abrio el puerto), las
# 45 columnas parsean igual y quedan TODAS corridas de nombre: un CSV que se ve
# bien y esta mal. Por eso se valida en vez de confiar.
CAMPOS_OBLIGATORIOS = ("us", "dt", "drop", "rxsteer", "rot", "ram",
                       "fl_dir", "fl_set", "fl_rpm", "fl_pwm", "fl_raw",
                       "br_raw", "gz")


def leer(path):
    global CABECERA
    with open(path, encoding="utf-8", newline="") as f:
        todas = f.readlines()
    CABECERA = [l.strip() for l in todas if l.startswith("#")]
    datos = [l.rstrip("\r\n") for l in todas if l and not l.startswith("#")]
    if not datos:
        sys.exit("El CSV no tiene datos.")

    # buscar la cabecera REAL: la primera linea que empieza con 'us,'
    idx = next((i for i, l in enumerate(datos) if l.startswith("us,")), None)
    if idx is None:
        sys.exit("No hay linea de cabecera ('us,...') en el archivo.\n"
                 "El firmware la reemite cada 2 s: si falta, el CSV se grabo con\n"
                 "una version vieja del firmware. Reflashear el entorno `diagnostico`.")
    if idx > 0:
        AVISOS.append("se descartaron %d lineas antes de la cabecera "
                      "(el registrador arranco a mitad de un frame)" % idx)
    # el firmware emite ticks_vuelta= en la procedencia: se usa ESE, no el
    # que este escrito aca, para que no puedan despegarse en silencio.
    global TICKS_VUELTA
    for l in CABECERA:
        for tok in l.replace("#", " ").split():
            if tok.startswith("ticks_vuelta="):
                try:
                    v = int(tok.split("=", 1)[1])
                    if v != TICKS_VUELTA:
                        AVISOS.append("ticks_vuelta del archivo = %d (el analizador "
                                      "traia %d): se usa el del archivo" % (v, TICKS_VUELTA))
                    TICKS_VUELTA = v
                except ValueError:
                    pass

    cab = datos[idx].split(",")
    faltan = [c for c in CAMPOS_OBLIGATORIOS if c not in cab]
    if faltan:
        sys.exit("La cabecera no tiene los campos %s. No es un CSV de este firmware." % faltan)
    n_cols = len(cab)

    filas, malas, dup_cab = [], 0, 0
    prev_us, acum = None, 0
    for l in datos[idx + 1:]:
        if l.startswith("us,"):      # cabecera reemitida: se saltea
            dup_cab += 1
            continue
        campos = l.split(",")
        if len(campos) != n_cols:    # linea truncada o pegada: se tira entera
            malas += 1
            continue
        try:
            f = {k: int(v) for k, v in zip(cab, campos)}
        except ValueError:
            malas += 1
            continue
        # --- desenvolver micros(): sin esto un wrap o un reset dan dt negativos
        #     y rpm_real se fuerza a 0 en las cuatro ruedas, apagando G en silencio
        u = f["us"]
        if prev_us is not None and u < prev_us:
            if prev_us - u > WRAP_US // 2:
                acum += WRAP_US                      # wrap normal de micros()
            else:
                AVISOS.append("el Teensy parece haberse reseteado; se corta el "
                              "analisis en la muestra %d" % len(filas))
                break
        prev_us = u
        f["t"] = u + acum
        filas.append(f)

    if malas:
        AVISOS.append("%d lineas descartadas por largo o formato" % malas)
    if dup_cab:
        AVISOS.append("%d cabeceras reemitidas salteadas (es lo esperado)" % dup_cab)
    return filas


def elegir_eje_giro(filas, ev, forzado=None):
    """Cual de los tres ejes del giroscopio es el YAW (la velocidad de giro).

    Depende del MONTAJE de la IMU, no del modelo: por eso el firmware graba los
    tres y la eleccion se hace con los datos. El yaw es el eje cuya magnitud se
    dispara durante las curvas y queda chica en las rectas. Fijarlo a mano en 'gz'
    era jugarse la causa B entera a una suposicion: si el yaw fuera 'gy', el
    analizador estaria midiendo "cuanto giro el robot" con un numero que no tiene
    nada que ver con girar, y diria TECHO DE PAR sobre la nada.
    """
    if forzado:
        return forzado, None
    if not ev:
        return "gz", None
    mejor, razon = None, {}
    for eje in ("gz", "gy", "gx"):
        # media CON SIGNO por segmento, y despues el promedio de los modulos.
        # ESTE es el discriminador: una ROTACION real tiene componente de continua
        # -el robot gira para un lado durante todo el segmento- y una VIBRACION
        # promedia ~0 aunque su magnitud sea enorme. Comparar mean(|eje|) adentro
        # contra afuera elegia el eje que MAS VIBRA, que en un robot con cuatro
        # motores forzando contra el piso puede ser cualquiera menos el yaw.
        porseg, ruido = [], []
        for a, b in ev:
            v = [f.get(eje, 0) for f in filas[a:b]]
            if not v:
                continue
            porseg.append(abs(sum(v) / len(v)) / 10.0)      # continua = rotacion
            ruido.append(sum(abs(x) for x in v) / len(v) / 10.0)  # magnitud total
        mc = sum(porseg) / len(porseg) if porseg else 0.0
        mr = sum(ruido) / len(ruido) if ruido else 0.0
        # mr - mc es lo que NO es rotacion: cuanto mas grande, mas vibracion
        razon[eje] = (mc, mr - mc, mc)
        if mejor is None or mc > razon[mejor][2]:
            mejor = eje
    return mejor, razon


def eventos_de_curva(filas):
    """Tramos contiguos con |rot| sobre el umbral Y SIN cambio de signo.
    Sin el corte por signo, una curva a izquierda pegada a una a derecha se
    fusiona y el promedio elige las ruedas internas equivocadas."""
    ev, ini, signo = [], None, 0
    for i, f in enumerate(filas):
        r = f.get("rot", 0) / 1000.0
        dentro = abs(r) > UMBRAL_CURVA
        s = 1 if r > 0 else -1
        if dentro and ini is None:
            ini, signo = i, s
        elif ini is not None and (not dentro or s != signo):
            if i - ini >= MIN_MUESTRAS:
                ev.append((ini, i))
            ini, signo = (i, s) if dentro else (None, 0)
    if ini is not None and len(filas) - ini >= MIN_MUESTRAS:
        ev.append((ini, len(filas)))
    return ev


def analizar_evento(filas, a, b):
    tramo = filas[a:b]
    rot = sum(f.get("rot", 0) for f in tramo) / len(tramo) / 1000.0
    internas = ("fl", "bl") if rot > 0 else ("fr", "br")
    dur_ms = (tramo[-1]["t"] - tramo[0]["t"]) / 1000.0

    # hueco REAL entre muestras: dt del firmware esta saturado en 65535 us y NO
    # crece cuando el anillo descarta, asi que se calcula de los timestamps.
    huecos = [tramo[i]["t"] - tramo[i - 1]["t"] for i in range(1, len(tramo))]
    r = {
        "n": len(tramo), "dur_ms": dur_ms, "rot": rot, "internas": internas,
        "ram_vals": sorted({f.get("ram", 0) for f in tramo}),
        "gz_abs_med": sum(abs(f.get(EJE_GIRO, 0)) for f in tramo) / len(tramo) / 10.0,
        "gz_abs_max": max(abs(f.get(EJE_GIRO, 0)) for f in tramo) / 10.0,
        "rxage_max": max(f.get("rxage", 0) for f in tramo),
        "rxage_nunca": any(f.get("rxage", 0) < 0 for f in tramo),
        "hueco_max_ms": (max(huecos) / 1000.0) if huecos else 0.0,
        "drop": tramo[-1].get("drop", 0) - tramo[0].get("drop", 0),
        "ruedas": {},
    }

    for w in RUEDAS:
        sets = [f.get(w + "_set", 0) for f in tramo]
        rpms = [f.get(w + "_rpm", 0) for f in tramo]
        pwms = [f.get(w + "_pwm", 0) for f in tramo]
        dirs = [f.get(w + "_dir", 0) for f in tramo]
        # fr/br reciben !rightdir en DriveBase::steer: su _dir esta espejado
        derecha = w in ("fr", "br")
        rev = [(d == 0) if derecha else (d == 1) for d in dirs]

        # colapso POR MUESTRA y sostenido: exigir que las dos condiciones pasen
        # en la MISMA muestra y se mantengan un periodo de PID. Combinar los dos
        # extremos del evento por separado daba falsos positivos.
        # Si el CSV trae envolventes (viene del camino WiFi, 10 Hz), se usa el
        # PEOR caso de cada ventana: asi un desplome de 40 ms se ve igual aunque
        # el muestreo sea de 100 ms. Si no estan, se usan los instantaneos.
        pmins = [f.get(w + "_pmin", f.get(w + "_pwm", 0)) for f in tramo]
        rmaxs = [f.get(w + "_rmax", f.get(w + "_rpm", 0)) for f in tramo]
        racha = mejor = 0
        for st, rp, pw in zip(sets, rmaxs, pmins):
            if st >= 1 and (rp - st) > COLAPSO_ARRASTRE and pw < COLAPSO_PWM:
                racha += 1
                mejor = max(mejor, racha)
            else:
                racha = 0

        draw = tramo[-1].get(w + "_raw", 0) - tramo[0].get(w + "_raw", 0)
        segs = (tramo[-1]["t"] - tramo[0]["t"]) / 1e6
        rpm_real = (draw / TICKS_VUELTA) * 60.0 / segs if segs > 0 else 0.0

        tog_delta = tramo[-1].get(w + "_tog", 0) - tramo[0].get(w + "_tog", 0)
        if tog_delta < 0:
            # solo puede pasar por reset del Teensy o CSV pegado. Marcarlo como
            # invalido en vez de leerlo como "no hubo toggles", que seria la
            # conclusion opuesta a la verdadera.
            tog_delta = None
        # MEDIANA, no media: una sola muestra saturada en 32000 (int16) le sube
        # 500 rpm al promedio de un evento de 60 muestras, con lo cual `deficit`
        # se va negativo, la causa P queda apagada y G dispara sola.
        rpm_med = statistics.median(rpms)
        pwm_med = statistics.median(pwms)
        # muestras fisicamente imposibles, y cuantas de ellas ocurrieron ANTES
        # del primer colapso: si el ruido precede al desplome, [A] no prueba nada.
        imposibles = sum(1 for x in rpms if x > RPM_IMPOSIBLE)
        primer_col = next((k for k, (st, rp, pw) in enumerate(zip(sets, rpms, pwms))
                           if st >= 1 and (rp - st) > COLAPSO_ARRASTRE and pw < COLAPSO_PWM),
                          len(rpms))
        imposibles_antes = sum(1 for x in rpms[:primer_col] if x > RPM_IMPOSIBLE)
        pwm_ord = sorted(pwms)
        r["ruedas"][w] = {
            "set_med": statistics.median(sets),
            "rpm_med": rpm_med,
            "pwm_med": pwm_med,
            "imposibles": imposibles,
            "imposibles_antes": imposibles_antes,
            "pwm_min": min(pwms),
            # el minimo REAL de la ventana: con envolventes es el pmin, si no el
            # instantaneo. Es el numero que hay que mostrar cuando se habla del
            # desplome, si no el mensaje se contradice con la deteccion.
            "pwm_min_env": min(pmins),
            "pwm_p10": pwm_ord[max(0, len(pwm_ord) // 10)],
            "frac_rev": sum(rev) / len(rev),
            "colapso_muestras": mejor,
            "tog": tog_delta,
            "rpm_real": rpm_real,
            # cuanto se queda corta respecto de lo que se le pidio, en fraccion
            "deficit": ((statistics.median(sets) - rpm_med) / statistics.median(sets))
                       if statistics.median(sets) else 0.0,
        }
    return r


def veredicto(r):
    causas = []
    for w in r["internas"]:
        d = r["ruedas"][w]

        # --- C y G NO dependen del sentido: van FUERA de cualquier guard de
        #     direccion. Antes vivian adentro de `if frac_rev < 0.5: continue`,
        #     que los anulaba exactamente cuando el pin oscilaba, que es el caso
        #     que buscamos. Era un falso negativo garantizado.
        if d["tog"] is None:
            causas.append(("?", "CONTADOR DE TOGGLES INVALIDO",
                           "%s: el contador retrocedio (reset del Teensy o CSV pegado): "
                           "no se puede concluir nada de C en esta curva" % w.upper()))
        elif d["tog"] > 20:
            causas.append(("C", "TOGGLE DEL PIN DE DIRECCION",
                           "%s: %d toggles en %.0f ms" % (w.upper(), d["tog"], r["dur_ms"])))
        elif 0.2 < d["frac_rev"] < 0.8:
            causas.append(("C", "SENTIDO INDEFINIDO",
                           "%s: el sentido comandado alterna (%.0f%% de las muestras en REV): "
                           "el pin esta oscilando mas rapido que el muestreo"
                           % (w.upper(), d["frac_rev"] * 100)))

        # G: el estimador contra la realidad fisica. El caso MAS grave es rueda
        # parada con el PID leyendo un numero alto (getSpeed() promedia los 4
        # ultimos intervalos y solo devuelve 0 despues de 111 ms sin flanco).
        if d["rpm_real"] < 1.0 and d["rpm_med"] > 5:
            causas.append(("G", "EL ESTIMADOR DE RPM MIENTE (caso grave)",
                           "%s: la rueda no giro (%.1f rpm reales) y el PID uso %.0f rpm"
                           % (w.upper(), d["rpm_real"], d["rpm_med"])))
        elif abs(d["rpm_med"] - d["rpm_real"]) > max(5.0, 0.4 * d["rpm_real"]):
            causas.append(("G", "EL ESTIMADOR DE RPM MIENTE",
                           "%s: el PID uso %.0f rpm y los flancos crudos dan %.0f"
                           % (w.upper(), d["rpm_med"], d["rpm_real"])))

        # --- A y B si dependen del sentido, pero basta con que haya ALGUNA
        #     muestra en REV: con el pin oscilando nunca se llega a la mayoria.
        # A y B se evaluan SIEMPRE sobre la interna. Entre 0,35 y 0,5 de rotation
        # la rueda va lenta pero hacia adelante y el arrastre ya existe: apagar la
        # deteccion ahi era perderse la mitad temprana del fenomeno.
        comandada = "en REV" if d["frac_rev"] > 0.5 else "adelante con consigna reducida"
        if d["imposibles"]:
            causas.append(("R", "FLANCOS ESPURIOS DEL ENCODER",
                           "%s: %d muestras con rpm > %d, imposible (el motor da 159 max)%s"
                           % (w.upper(), d["imposibles"], RPM_IMPOSIBLE,
                              ", %d ANTES del colapso" % d["imposibles_antes"]
                              if d["imposibles_antes"] else "")))
        if d["colapso_muestras"] >= COLAPSO_MIN_MUESTRAS:
            causas.append(("A", "PID CIEGO AL SIGNO",
                           "%s: pedida %.0f rpm %s, %d muestras seguidas (%.0f ms) "
                           "midiendo de mas con el PWM por el piso (min %d)"
                           % (w.upper(), d["set_med"], comandada, d["colapso_muestras"],
                              d["colapso_muestras"] * PERIODO_REAL_US / 1000.0,
                              d["pwm_min_env"])))
            if d["imposibles_antes"]:
                causas.append(("!", "[A] NO ES CONCLUYENTE",
                               "%s: hubo %d flancos imposibles ANTES del colapso. Un solo "
                               "flanco espurio le mete al PID un error de -200 rpm y tira la "
                               "rueda a coast: se ve igual que el arrastre y se arregla con "
                               "un capacitor, no reescribiendo el lazo."
                               % (w.upper(), d["imposibles_antes"])))
        # El umbral de B era 60 y el de A es 30: entre medio quedaba una BANDA
        # MUERTA donde no disparaba ninguna causa y el informe decia "sin firma
        # clara". Peor todavia con el piso anti-coast en 45, que cae justo ahi.
        # Ahora B es el complemento de A: si el esfuerzo NO se desplomo y el robot
        # igual no giro, hay algo que impide el giro. No queda hueco entre las dos.
        elif d["pwm_p10"] > COLAPSO_PWM and r["gz_abs_med"] < 15:
            causas.append(("B", "TECHO DE PAR / SCRUB (probable)",
                           "%s: el PWM se mantuvo alto (p10 %d) y el robot igual giro "
                           "%.1f d/s. OJO: sin sensor de corriente esto NO distingue "
                           "rozamiento de limite del driver; mirar si tambien salio [P]"
                           % (w.upper(), d["pwm_p10"], r["gz_abs_med"])))

    # P antes que B: "PWM alto y no gira" tambien puede ser bateria o limite del
    # driver, no solo rozamiento. Sin sensor de corriente, el unico discriminador
    # es la SIMETRIA: el scrub castiga a la rueda INTERNA; una caida de tension
    # castiga a LAS CUATRO por igual.
    todas = [r["ruedas"][w] for w in RUEDAS]
    if (all(d["deficit"] > 0.25 for d in todas)
            and all(d["pwm_med"] > 120 for d in todas)):
        causas.append(("P", "SOSPECHA DE ALIMENTACION",
                       "las cuatro ruedas se quedan %d-%d%% cortas con el PWM alto: "
                       "eso no es scrub, es tension que cae o el driver limitando"
                       % (min(d["deficit"] for d in todas) * 100,
                          max(d["deficit"] for d in todas) * 100)))

    if r["hueco_max_ms"] > max(25.0, 5.0 * PERIODO_REAL_US / 1000.0):
        causas.append(("D", "EL CONTROL SE CONGELA",
                       "hueco real de %.1f ms entre muestras (el periodo es %.0f ms)"
                       % (r["hueco_max_ms"], PERIODO_REAL_US / 1000.0)))
    if r["drop"] > 0:
        causas.append(("D", "MUESTRAS PERDIDAS",
                       "%d muestras descartadas por anillo lleno durante la curva" % r["drop"]))
    if r["rxage_nunca"]:
        causas.append(("E", "LA RPi NUNCA MANDO UNA TRAMA",
                       "rxage = -1 durante la curva: el robot se movio sin comando de vision"))
    elif r["rxage_max"] > 200:
        causas.append(("E", "COMANDO RANCIO DE LA RPi",
                       "hasta %d ms sin trama nueva durante la curva" % r["rxage_max"]))

    # F: solo tiene sentido si la curva la pidio EL CASE 7. La marca -1 dice que
    # el giro vino de un runAngle/runTime (verde, 180, esquive): ahi la rama no
    # aplica y antes esto daba falso positivo en todo giro programado.
    # B ES RESIDUAL, no una causa mas. "Hubo esfuerzo y el robot no giro" solo
    # significa "es mecanico" DESPUES de descartar que el estimador este mintiendo
    # (G), que sea la alimentacion (P) o que el control se haya congelado (D).
    # Si alguna de esas ya explica la falta de giro, B sobra y solo hace ruido.
    if any(c[0] in ("G", "P", "D") for c in causas):
        expl = sorted({c[0] for c in causas if c[0] in ("G", "P", "D")})
        if any(c[0] == "B" for c in causas):
            causas = [c for c in causas if c[0] != "B"]
            causas.append(("i", "B DESCARTADA",
                           "hubo esfuerzo y el robot no giro, pero %s ya lo explica: "
                           "no se puede concluir que sea mecanico" % ("/".join(expl))))

    if -1 in r["ram_vals"]:
        causas.append(("-", "GIRO PROGRAMADO, NO LINETRACK",
                       "rama = -1: esta curva la pidio un runAngle/runTime, no la vision"))
    elif max(r["ram_vals"]) < 2:
        causas.append(("F", "LA VISION NUNCA PIDIO EL GIRO",
                       "la rama del case 7 no paso de %d" % max(r["ram_vals"])))
    return causas


def flags_de(path):
    """Los flags de procedencia que el firmware escribio en las lineas '#'."""
    d = {}
    with open(path, encoding="utf-8") as f:
        for l in f:
            if not l.startswith("#"):
                break
            for tok in l.replace("#", " ").split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    if k in FLAGS_PROCEDENCIA:
                        d[k] = v
    return d


def comparar_procedencias(a, b):
    """Un A/B solo es atribuible si las dos corridas difieren en UNA cosa."""
    fa, fb = flags_de(a), flags_de(b)
    if not fa or not fb:
        print("AVISO: uno de los dos CSV no tiene linea de procedencia; no puedo")
        print("       verificar que sean comparables. Regrabar con el firmware nuevo.")
        return
    dif = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
    print("=" * 78)
    print("COMPARABILIDAD")
    if not dif:
        print("  los dos CSV se grabaron con EXACTAMENTE la misma configuracion.")
        print("  Cualquier diferencia entre ellos es del robot o de la pista, no del codigo.")
    elif len(dif) == 1:
        k = dif[0]
        print("  difieren en UNA sola cosa: %s (%s -> %s). El A/B es atribuible."
              % (k, fa.get(k, "?"), fb.get(k, "?")))
    else:
        print("  *** DIFIEREN EN %d COSAS: %s" % (len(dif), ", ".join(dif)))
        for k in dif:
            print("      %-14s %s  ->  %s" % (k, fa.get(k, "(falta)"), fb.get(k, "(falta)")))
        print("  Cualquier diferencia entre las dos corridas tiene %d explicaciones" % len(dif))
        print("  posibles y ninguna forma de separarlas. Grabar una corrida por cambio.")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--comparar", metavar="OTRO.csv",
                    help="chequea que el otro CSV sea comparable con este "
                         "(que difieran en UN solo flag de procedencia)")
    ap.add_argument("--eje", choices=("gx", "gy", "gz"),
                    help="forzar el eje del giroscopio que es el yaw "
                         "(por defecto se elige con los datos)")
    args = ap.parse_args()

    if args.comparar:
        comparar_procedencias(args.csv, args.comparar)

    filas = leer(args.csv)
    if len(filas) < 2:
        sys.exit("Menos de dos muestras validas: no hay nada que analizar.")

    dur = (filas[-1]["t"] - filas[0]["t"]) / 1e6
    hz = len(filas) / dur if dur else 0
    global PERIODO_REAL_US, COLAPSO_MIN_MUESTRAS
    if hz > 0:
        PERIODO_REAL_US = 1e6 / hz
        # el colapso tiene que sostenerse un periodo del PID (20 ms). A 200 Hz
        # son 4 muestras; a 10 Hz una sola muestra ya cubre 100 ms.
        COLAPSO_MIN_MUESTRAS = max(1, int(round(20000.0 / PERIODO_REAL_US)))
    print("=" * 78)
    # el firmware reemite la procedencia cada 2 s: en una corrida de 5 minutos
    # son ~150 lineas identicas. Se imprimen las distintas y se dice cuantas hubo.
    vistas = []
    for l in CABECERA:
        if l not in vistas:
            vistas.append(l)
            print(l)
    if len(CABECERA) > len(vistas):
        print("# (%d lineas de procedencia repetidas, omitidas)" % (len(CABECERA) - len(vistas)))
    if not any("lazo=" in l for l in CABECERA):
        print("# ATENCION: sin marca de lazo. No se sabe si esta corrida es con el fix")
        print("#           o sin el, asi que NO sirve para comparar.")
    print("%d muestras, %.1f s, %.0f Hz efectivos" % (len(filas), dur, hz))
    for a in AVISOS:
        print("aviso: " + a)
    perdidas = filas[-1].get("drop", 0) - filas[0].get("drop", 0)
    if perdidas:
        print("ATENCION: %d muestras perdidas por anillo lleno EN ESTA CORRIDA" % perdidas)
    if hz < 150:
        print("ATENCION: %.0f Hz esta por debajo de los 200 nominales: hay huecos" % hz)

    ev = eventos_de_curva(filas)
    if not ev:
        rx = max(abs(f.get("rxsteer", 0)) for f in filas) / 1000.0
        print("\nNingun tramo con |rotation| > %.2f." % UMBRAL_CURVA)
        print("El |steer| MAXIMO que mando la Raspberry en toda la corrida fue %.3f." % rx)
        print("Si ese numero es chico, el problema es de PERCEPCION: la vision")
        print("nunca pidio la curva. Si es grande, mirar por que no llego a `rot`.")
        return

    # El eje del giroscopio que es el YAW depende del MONTAJE de la IMU, no del
    # modelo: por eso el firmware graba los tres y la eleccion se hace con los
    # datos de la propia corrida. Fijarlo a 'gz' era jugarse la causa B entera a
    # una suposicion: si el yaw fuera 'gy', el analizador estaria midiendo
    # "cuanto giro el robot" con un numero que no tiene nada que ver con girar.
    global EJE_GIRO
    EJE_GIRO, razon = elegir_eje_giro(filas, ev, args.eje)
    if razon:
        d = razon[EJE_GIRO]
        print("\neje de giro elegido con los datos: %s "
              "(%.1f d/s de rotacion neta, %.1f de vibracion)" % (EJE_GIRO, d[0], d[1]))
        print("  los otros: %s   (rotacion/vibracion)" % ", ".join(
            "%s %.1f/%.1f" % (e, v[0], v[1]) for e, v in razon.items() if e != EJE_GIRO))
        if d[2] < 3.0:
            print("  ATENCION: ningun eje se despega en las curvas. O el robot NO GIRO,")
            print("  o la IMU no reporta. La causa B no es concluyente en esta corrida.")
    elif args.eje:
        print("\neje de giro forzado por el usuario: %s" % EJE_GIRO)

    print("\n%d curvas detectadas\n" % len(ev))
    resumen = {}
    for k, (a, b) in enumerate(ev, 1):
        r = analizar_evento(filas, a, b)
        print("-" * 78)
        print("CURVA %d  |  %.0f ms  |  rot medio %+.3f  |  internas %s"
              % (k, r["dur_ms"], r["rot"], "+".join(w.upper() for w in r["internas"])))
        print("  giro real %.1f d/s (pico %.1f)  |  ramas %s  |  hueco max %.1f ms"
              "  |  drop %d  |  rxage max %d ms"
              % (r["gz_abs_med"], r["gz_abs_max"], r["ram_vals"],
                 r["hueco_max_ms"], r["drop"], r["rxage_max"]))
        print("  %-4s %8s %8s %8s %8s %8s %7s %6s" %
              ("", "set", "rpm PID", "rpm real", "pwm med", "pwm min", "%REV", "colap"))
        for w in RUEDAS:
            d = r["ruedas"][w]
            marca = " <- interna" if w in r["internas"] else ""
            print("  %-4s %8.0f %8.0f %8.0f %8.0f %8d %6.0f%% %6d%s"
                  % (w.upper(), d["set_med"], d["rpm_med"], d["rpm_real"],
                     d["pwm_med"], d["pwm_min"], d["frac_rev"] * 100,
                     d["colapso_muestras"], marca))
        cs = veredicto(r)
        if not cs:
            print("  -> sin firma clara. La curva se ejecuto como se pidio.")
        for cod, titulo, detalle in cs:
            print("  -> [%s] %s: %s" % (cod, titulo, detalle))
        for cod in {c[0] for c in cs}:
            resumen[cod] = resumen.get(cod, 0) + 1

    print("=" * 78)
    print("RESUMEN sobre %d curvas:" % len(ev))
    if not resumen:
        print("  ninguna causa detectada.")
    for cod in sorted(resumen):
        print("  [%s] en %d de %d curvas" % (cod, resumen[cod], len(ev)))


if __name__ == "__main__":
    main()
