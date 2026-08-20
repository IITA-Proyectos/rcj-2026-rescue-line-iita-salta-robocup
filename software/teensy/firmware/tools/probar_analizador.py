#!/usr/bin/env python3
"""
Prueba de regresion del analizador, contra fallas de las que SABEMOS la respuesta.

    python tools/probar_analizador.py

Fabrica once corridas sinteticas con el formato exacto del entorno `diagnostico`,
cada una reproduciendo una falla conocida, y verifica que el analizador saque la
causa correcta. Corre en cualquier PC, sin robot.

POR QUE EXISTE: sin esto, la primera vez que el analizador ve datos es cuando ya
es el insumo de la decision de que arreglar, y cuando el resultado salga raro no
se va a poder saber si fallo el robot o fallo el analizador. Ademas cada caso
documenta, en codigo ejecutable, que se supone que significa cada causa.

Si tocas un umbral del analizador, corre esto ANTES de creerte la mejora.
"""
import io
import os
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

CAB = ("us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram,"
       "fl_dir,fl_set,fl_rpm,fl_pwm,fl_enc,fl_tog,fl_raw,"
       "fr_dir,fr_set,fr_rpm,fr_pwm,fr_enc,fr_tog,fr_raw,"
       "bl_dir,bl_set,bl_rpm,bl_pwm,bl_enc,bl_tog,bl_raw,"
       "br_dir,br_set,br_rpm,br_pwm,br_enc,br_tog,br_raw,yaw,pit,gx,gy,gz")
PROC = ("# hz=200 ticks_vuelta=540 fix_lazo=0 fix_curva=0 ks=8.00 kv=1.350 "
        "piso=0.50 anticoast=45.0 diag_puerto=0 lazo=historico commit=prueba")
DT = 5000


class Corrida:
    """Arma un CSV con el formato exacto que emite diagDrenar()."""

    def __init__(self, us0=0):
        self.f, self.us = [], us0
        self.enc, self.raw, self.tog = [0] * 4, [0] * 4, [0] * 4

    def paso(self, rot, ram, dir_, set_, rpm_, pwm_, gz, rxage=45,
             tog_inc=(0, 0, 0, 0), raw_rpm=None, gy=2, dt=DT):
        self.us = (self.us + dt) % (2 ** 32)
        ls = abs(int(45 * (1 - 2 * rot))) if rot >= 0 else 45
        rs = 45 if rot >= 0 else abs(int(45 + 2 * rot * 45))
        rr = raw_rpm if raw_rpm is not None else rpm_
        for i in range(4):
            self.raw[i] += max(0, round(rr[i] * 540 / 60 * (dt / 1e6)))
            self.enc[i] += max(0, rpm_[i] // 5)
            self.tog[i] += tog_inc[i]
        c = [self.us, min(65535, dt), 0, int(rot * 1000), 40, rxage, 7,
             int(rot * 1000), ls, rs, 0, ram]
        for i in range(4):
            c += [dir_[i], set_[i], rpm_[i], pwm_[i], self.enc[i], self.tog[i], self.raw[i]]
        c += [1800, 5, 1, gy, int(gz * 10)]
        self.f.append(",".join(str(x) for x in c))

    def recta(self, n=200, gy=2):
        for _ in range(n):
            self.paso(0.02, 0, [0, 1, 0, 1], [45] * 4, [44, 45, 44, 45],
                      [88, 90, 88, 90], 0.4, gy=gy)

    def guardar(self, ruta, cabecera_al_principio=True):
        with open(ruta, "w", encoding="utf-8") as fh:
            if cabecera_al_principio:
                fh.write("# RescueBot IITA - prueba sintetica\n" + PROC + "\n" + CAB + "\n")
            for i, l in enumerate(self.f):
                if not cabecera_al_principio and i == 130:
                    fh.write(PROC + "\n" + CAB + "\n")
                elif i and i % 400 == 0:
                    fh.write(PROC + "\n" + CAB + "\n")
                fh.write(l + "\n")
        return ruta


# ---------------------------------------------------------------- los casos
def caso_dir_oscilando(d):
    """El toggle del pin de direccion corre mas rapido que el muestreo, asi que
    `dir` alterna muestra a muestra. El guard viejo (frac_rev < 0.5) anulaba
    A, C y G justo en la rueda que oscila: falso negativo garantizado."""
    c = Corrida(); c.recta()
    for k in range(160):
        dd = k % 2
        c.paso(0.90, 2, [dd, 1, dd, 1], [20, 45, 20, 45], [35, 44, 35, 44],
               [5, 92, 5, 92], 1.8, tog_inc=(2, 0, 2, 0))
    c.recta(120)
    return c.guardar(d), {"A", "C"}


def caso_estimador_miente(d):
    """La rueda esta PARADA (los flancos crudos no avanzan) pero getSpeed()
    promedia los 4 ultimos intervalos y le devuelve 30 rpm al PID."""
    c = Corrida(); c.recta()
    for _ in range(200):
        c.paso(0.80, 2, [1, 1, 1, 1], [20, 45, 20, 45], [30, 44, 30, 44],
               [45, 92, 45, 92], 1.5, raw_rpm=[0.1, 44, 0.1, 44])
    c.recta(120)
    return c.guardar(d), {"G", "i"}


def caso_izq_pegada_a_der(d):
    """Curva a izquierda seguida sin pausa de una a derecha. Sin corte por signo
    se fusionaban en un evento y el promedio elegia las internas equivocadas."""
    c = Corrida(); c.recta(100)
    for _ in range(120):
        c.paso(0.70, 2, [1, 1, 1, 1], [18, 45, 18, 45], [33, 44, 33, 44],
               [8, 92, 8, 92], 2.0, tog_inc=(3, 0, 3, 0))
    for _ in range(120):
        c.paso(-0.70, 2, [0, 0, 0, 0], [45, 18, 45, 18], [44, 33, 44, 33],
               [92, 8, 92, 8], 2.0, tog_inc=(0, 3, 0, 3))
    c.recta(100)
    return c.guardar(d), {"A", "C", "G"}


def caso_sin_cabecera(d):
    """El registrador arranco DESPUES del Teensy: la cabecera inicial se perdio.
    Abrir el USB no resetea un Teensy 4.1, asi que es el flujo normal."""
    c = Corrida(); c.recta(100)
    for _ in range(160):
        c.paso(0.75, 2, [1, 1, 1, 1], [19, 45, 19, 45], [34, 44, 34, 44],
               [6, 92, 6, 92], 1.9, tog_inc=(2, 0, 2, 0))
    c.recta(100)
    return c.guardar(d, cabecera_al_principio=False), {"A", "C"}


def caso_wrap_micros(d):
    """micros() envuelve a los ~71,6 min en medio de la curva."""
    c = Corrida(us0=2 ** 32 - 300 * DT); c.recta(100)
    for _ in range(200):
        c.paso(0.78, 2, [1, 1, 1, 1], [19, 45, 19, 45], [34, 44, 34, 44],
               [7, 92, 7, 92], 1.7, tog_inc=(2, 0, 2, 0))
    c.recta(100)
    return c.guardar(d), {"A", "C"}


def caso_techo_de_par(d):
    """Las ruedas OBEDECEN (miden lo que se les pide) y el robot igual no gira.
    Es el unico caso en que [B] sobrevive: nada mas lo explica."""
    c = Corrida(); c.recta()
    for _ in range(200):
        c.paso(-0.75, 2, [0, 0, 0, 0], [45, 22, 45, 22], [45, 22, 45, 22],
               [95, 88, 95, 88], 1.2)
    c.recta(100)
    return c.guardar(d), {"B"}


def caso_control_congelado(d):
    """Huecos reales de 120 ms entre muestras: el control se traba adentro de
    un movimiento bloqueante."""
    c = Corrida(); c.recta(100)
    for k in range(60):
        c.paso(0.72, 2, [1, 1, 1, 1], [20, 45, 20, 45], [30, 44, 30, 44],
               [70, 92, 70, 92], 5.0, dt=DT if k % 10 else 120000)
    c.recta(100)
    return c.guardar(d), {"D", "i"}


def caso_yaw_en_gy(d):
    """La IMU esta montada de modo que el yaw cae en gy. El robot GIRA BIEN.
    Con el eje fijo en gz, el analizador leia 'no gira' y disparaba [B]:
    mandaba al equipo a desarmar la mecanica por nada."""
    c = Corrida(); c.recta(200, gy=3)
    for _ in range(200):
        c.paso(-0.75, 2, [0, 0, 0, 0], [45, 22, 45, 22], [45, 22, 45, 22],
               [95, 88, 95, 88], 0.7, gy=280)
    c.recta(100, gy=3)
    return c.guardar(d), set()


def caso_bateria(d):
    """LAS CUATRO ruedas se quedan cortas a la vez con el PWM alto. El scrub
    castiga a la INTERNA; una caida de tension castiga a todas por igual: es el
    unico discriminador posible sin sensor de corriente."""
    c = Corrida(); c.recta()
    for _ in range(200):
        c.paso(-0.75, 2, [0, 0, 0, 0], [45, 22, 45, 22], [24, 12, 24, 12],
               [210, 205, 210, 205], 1.1)
    c.recta(100)
    return c.guardar(d), {"P", "G", "i"}


def caso_ruido_encoder(d):
    """Flancos espurios ANTES del desplome de PWM. Un solo flanco le mete al PID
    un error de -200 rpm y lo tira a coast: se ve IGUAL que [A] pero se arregla
    con un capacitor, no reescribiendo el lazo."""
    c = Corrida(); c.recta()
    for k in range(200):
        ruido = k < 40 and k % 7 == 0
        rpm = 211 if ruido else (34 if k >= 40 else 19)
        pwm = 70 if k < 40 else max(4, 70 - (k - 40) * 3)
        c.paso(0.85, 2, [1, 1, 1, 1], [20, 45, 20, 45], [rpm, 44, rpm, 44],
               [pwm, 92, pwm, 92], 2.0)
    c.recta(100)
    return c.guardar(d), {"R", "A", "!"}


def caso_giro_programado(d):
    """La curva la pidio un runAngle (rama -1), no la vision. El analizador no
    tiene que atribuirle nada al lazo de linea."""
    c = Corrida(); c.recta()
    for _ in range(200):
        c.paso(0.95, -1, [1, 1, 1, 1], [45, 45, 45, 45], [44, 45, 44, 45],
               [92, 92, 92, 92], 30.0)
    c.recta(100)
    return c.guardar(d), {"-"}


CASOS = [
    ("dir del pin oscilando", caso_dir_oscilando),
    ("el estimador miente", caso_estimador_miente),
    ("izquierda pegada a derecha", caso_izq_pegada_a_der),
    ("sin cabecera inicial", caso_sin_cabecera),
    ("wrap de micros()", caso_wrap_micros),
    ("techo de par", caso_techo_de_par),
    ("control congelado", caso_control_congelado),
    ("yaw montado en gy", caso_yaw_en_gy),
    ("bateria cayendo", caso_bateria),
    ("ruido en el encoder", caso_ruido_encoder),
    ("giro programado (no linetrack)", caso_giro_programado),
]


# ============================================================================
#  SEGUNDA SUITE: analizar_barrido.py
#  Hasta ahora los 11 casos de arriba pasaban TODOS por analizar_diagnostico y
#  el analizador del barrido -el que da el veredicto firmware-vs-mecanica, o sea
#  el que decide como se usa el sabado- nunca habia visto un dato de prueba.
# ============================================================================
BANCO_ROT, BANCO_VEL = 50, 60
ROTS = (0.40, 0.50, 0.60, 0.70, 0.85, 1.00)
VELS = (25, 35, 45, 55, 70)


class Barrido(Corrida):
    """Arma un CSV con la estructura que emite bancoBarrido()."""

    def seg(self, rot, ram, vel, gz, colapsa, gx=1, n=300):
        vint = abs(vel * (1 - 2 * abs(rot)))
        rev = (1 - 2 * abs(rot)) < 0
        izq = rot > 0
        rint = int(vint + 16) if colapsa else int(vint)
        pint = 6 if colapsa else 95
        st = [0] * 4; rp = [0] * 4; pw = [0] * 4; dr = [0] * 4
        for i, w in enumerate(("fl", "fr", "bl", "br")):
            inte = (w in ("fl", "bl")) == izq
            st[i] = int(vint if inte else vel)
            rp[i] = rint if inte else int(vel)
            pw[i] = pint if inte else 95
            der = w in ("fr", "br")
            adel = not (inte and rev)
            dr[i] = (1 if adel else 0) if der else (0 if adel else 1)
        for _ in range(n):
            self.paso(rot, ram, dr, st, rp, pw, gz, gy=3)
            if gx != 1:                       # inyectar vibracion en gx
                self.f[-1] = self.f[-1].rsplit(",", 3)[0] + ",%d,3,%d" % (
                    gx if len(self.f) % 2 else -gx, int(gz * 10))

    def quieto(self, n=200):
        self.seg(0.0, 0, 0, 0.1, False, n=n)

    def completo(self, gz_fn, colapsa_fn, gx=1, hasta=None):
        for _ in range(2):
            for r in (hasta or ROTS):
                for sg in (1, -1):
                    self.quieto()
                    c = colapsa_fn(r)
                    self.seg(sg * r, BANCO_ROT, 45, gz_fn(r, c), c, gx=gx)
        for _ in range(2):
            for v in VELS:
                self.quieto()
                self.seg(1.0, BANCO_VEL, v, gz_fn(1.0, False), False, gx=gx)


def bar_pid(d):
    """Se hunde en la banda intermedia y se recupera en 1,00: firma del PID."""
    c = Barrido()
    c.completo(lambda r, col: 4.0 if col else (10.0 + 28.0 * r),
               lambda r: 0.5 < r < 0.95)
    return c.guardar(d), "SE HUNDE EN LA BANDA"


def bar_par(d):
    """Cuanto mas rotation, menos gira: techo de par."""
    c = Barrido()
    c.completo(lambda r, col: max(1.0, 26.0 - 24.0 * r), lambda r: False)
    return c.guardar(d), "TECHO DE PAR"


def bar_imu_muda(d):
    """La rueda colapsa igual, pero el giroscopio devuelve siempre 0."""
    c = Barrido()
    c.completo(lambda r, col: 0.0, lambda r: 0.5 < r < 0.95)
    return c.guardar(d), "NO HAY VEREDICTO POR GIRO"


def bar_vibracion(d):
    """Yaw real bajo (1,6 d/s) y VIBRACION alta (12 d/s) en gx. El selector viejo
    -mean(|eje|)- elegia gx y el guard de 3 d/s no disparaba nunca."""
    c = Barrido()
    c.completo(lambda r, col: 1.6, lambda r: 0.5 < r < 0.95, gx=120)
    return c.guardar(d), "NO HAY VEREDICTO POR GIRO"


def bar_incompleto(d):
    """Cortado antes de rotation=1,00: el giro solo puede bajar y cualquier
    veredicto diria MECANICO sobre un dato que no existe."""
    c = Barrido()
    c.completo(lambda r, col: max(1.0, 26.0 - 24.0 * r), lambda r: False,
               hasta=(0.40, 0.50, 0.60, 0.70))
    return c.guardar(d), "BARRIDO INCOMPLETO"


def bar_sano(d):
    """EL FALSO POSITIVO. Robot cinematicamente PERFECTO: el yaw es exactamente
    proporcional a rotation (40 d/s por unidad) y ninguna rueda colapsa.

    Con la metrica vieja -d/s CRUDOS por zona- esto imprimia:
        MEJORA hacia rotation = 1 ... SE ARREGLA POR FIRMWARE
    porque el cociente ideal alto/banda es 1,00/0,70 = 1,43 y el umbral era 1,3:
    la condicion se cumplia SOLA. El sesgo era sistematico hacia "es firmware",
    o sea hacia gastar las semanas siguientes reescribiendo un lazo que anda.
    """
    c = Barrido()
    c.completo(lambda r, col: 40.0 * r, lambda r: False)
    return c.guardar(d), "PLANO"


def bar_par_moderado(d):
    """EL FALSO NEGATIVO. Techo de par REAL pero moderado: el yaw sigue la
    consigna hasta que satura en 26 d/s y de ahi no sube mas.

    Con la metrica vieja salia "PAREJO -> el problema esta en la VISION", que es
    lo unico que este banco NO puede concluir (corre sin camara y sin pista).
    Para que la version vieja dijera MECANICO hacia falta que el yaw en rot=1
    cayera por debajo del 54% de su prediccion cinematica: solo un techo
    catastrofico se detectaba.
    """
    c = Barrido()
    c.completo(lambda r, col: min(40.0 * r, 26.0), lambda r: False)
    return c.guardar(d), "TECHO DE PAR"


def bar_tirita(d):
    """El robot VIBRA en el eje del yaw y no gira: |gz| = 26 d/s con rotacion
    NETA ~0. Es justo lo que predice el techo de par con la silicona, o sea el
    caso mas probable de todos.

    El guard `giro_sirve` ya detectaba esto e imprimia "el VEREDICTO queda
    anulado"... y doce lineas mas abajo el veredicto salia igual, porque el
    guard solo se aplicaba a la fase 2. El otro guard (`max(...) < 3.0`) no lo
    tapa: |gz| es grande. El caso `bar_vibracion` no lo cubria porque mete el
    ruido en gx y deja gz limpio, asi que lo salvaba el guard de los 3 d/s.
    """
    c = Barrido()
    c.completo(lambda r, col: 26.0, lambda r: False)
    n = 0
    for i, ln in enumerate(c.f):
        if ln.startswith("#") or ln.startswith("us,"):
            continue
        campos = ln.split(",")
        campos[-3] = "1" if n % 2 == 0 else "-1"        # gx: ruido chico, neto 0
        campos[-2] = "2" if n % 2 == 0 else "-2"        # gy: idem
        campos[-1] = "260" if n % 2 == 0 else "-255"    # gz: |26| d/s, neto 0,25
        c.f[i] = ",".join(campos)
        n += 1
    return c.guardar(d), "NO HAY VEREDICTO POR GIRO"


CASOS_BARRIDO = [
    ("barrido: firma del PID", bar_pid),
    ("barrido: techo de par", bar_par),
    ("barrido: IMU muda", bar_imu_muda),
    ("barrido: vibracion tapa el yaw", bar_vibracion),
    ("barrido: cortado sin rotation=1", bar_incompleto),
    ("barrido: robot SANO (falso positivo)", bar_sano),
    ("barrido: techo de par MODERADO", bar_par_moderado),
    ("barrido: tirita sin girar", bar_tirita),
]


def veredicto_barrido(csv):
    import analizar_barrido as AB
    AD_ = __import__("analizar_diagnostico")
    AD_.CABECERA, AD_.AVISOS = [], []
    argv, sys.argv = sys.argv, ["analizar_barrido.py", csv]
    buf, out = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        AB.main()
    except SystemExit:
        pass
    finally:
        sys.stdout = out
        sys.argv = argv
    return buf.getvalue()


def causas_de(csv):
    """Corre el analizador de verdad y saca los codigos de causa."""
    import analizar_diagnostico as AD
    AD.CABECERA, AD.AVISOS = [], []
    argv, sys.argv = sys.argv, ["analizar_diagnostico.py", csv]
    buf, out = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        AD.main()
    except SystemExit:
        pass
    finally:
        sys.stdout = out
        sys.argv = argv
    cods = set()
    for l in buf.getvalue().splitlines():
        t = l.strip()
        if t.startswith("-> [") and "]" in t:
            cods.add(t[4:t.index("]")])
    return cods, buf.getvalue()


def main():
    d = tempfile.mkdtemp(prefix="pruebas_diag_")
    print("=" * 74)
    print("PRUEBA DEL ANALIZADOR contra %d fallas conocidas" % len(CASOS))
    print("=" * 74)
    malos = []
    for k, (nombre, fn) in enumerate(CASOS, 1):
        csv, esperado = fn(os.path.join(d, "c%02d.csv" % k))
        obt, salida = causas_de(csv)
        ok = obt == esperado
        print("%2d. %-32s esperado %-16s obtenido %-16s %s"
              % (k, nombre, "{" + ",".join(sorted(esperado)) + "}",
                 "{" + ",".join(sorted(obt)) + "}", "OK" if ok else "*** MAL"))
        if not ok:
            malos.append((nombre, esperado, obt, salida))
    # --- segunda suite: el analizador del BARRIDO ---------------------------
    print("=" * 74)
    print("PRUEBA DEL ANALIZADOR DE BARRIDO contra %d casos" % len(CASOS_BARRIDO))
    print("=" * 74)
    for k, (nombre, fn) in enumerate(CASOS_BARRIDO, 1):
        csv, esperado = fn(os.path.join(d, "b%02d.csv" % k))
        salida = veredicto_barrido(csv)
        ok = esperado in salida
        print("%2d. %-34s espera %-26s %s"
              % (k, nombre, esperado, "OK" if ok else "*** MAL"))
        if not ok:
            malos.append((nombre, {esperado}, set(), salida))

    print("=" * 74)
    if malos:
        print("FALLARON %d de %d" % (len(malos), len(CASOS)))
        for nombre, esp, obt, salida in malos:
            print("\n--- %s ---\nesperado %s\nobtenido %s\n%s"
                  % (nombre, sorted(esp), sorted(obt), salida))
        return 1
    print("PASARON LAS %d + %d DEL BARRIDO." % (len(CASOS), len(CASOS_BARRIDO)))
    print("CSV de las pruebas en: %s" % d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
