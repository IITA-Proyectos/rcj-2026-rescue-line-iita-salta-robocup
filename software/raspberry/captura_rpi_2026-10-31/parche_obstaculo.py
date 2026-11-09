# OBST_SIN_RECUP para main.py (sobre 9d081a1d). Va junto con la Teensy que manda 0xF5 / 0xF6 en el esquive
# (OBSTACULO_AVISA_PI en main.cpp). Sin la variable, main.py hace exactamente lo mismo que antes.
# Uso: python3 parche_obstaculo.py main.py
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''BAJADA_POST_S    = float(os.environ.get("BAJADA_POST_S", "1.5"))
''', '''BAJADA_POST_S    = float(os.environ.get("BAJADA_POST_S", "1.5"))
# OBSTACULO SIN RECUPERACION (12-oct, crudo 1012_135700 cuadros 8314-8590). Durante el esquive la cinta se
# pierde: la Pi pedia la recuperacion (GS=4) y esperaba el 0xEF todo el esquive (3,5 a 7 s); al volver a
# la cinta la Teensy la ejecutaba, retrocedia, pivoteaba y se iba de la pista. Con OBST_SIN_RECUP=1, desde
# que la Teensy avisa 0xF5 (empieza el esquive) hasta OBST_POST_S despues del 0xF6 (volvio a la cinta), sin
# cinta sigue DERECHO y no dispara la recuperacion ni el gap, igual que en la rampa. Con la cinta a la vista
# la sigue como siempre. Si el 0xF6 no llega, la ventana se cierra sola a los OBST_MAX_S.
# Necesita la Teensy con OBSTACULO_AVISA_PI. Sin la variable, exactamente lo de antes.
OBST_SIN_RECUP   = os.environ.get("OBST_SIN_RECUP", "0") == "1"
OBST_POST_S      = float(os.environ.get("OBST_POST_S", "3"))
OBST_MAX_S       = 10.0
''')

rep('''TEENSY_RAMPA_LLANO = b'\\xf4'  # 244 = llano
''', '''TEENSY_RAMPA_LLANO = b'\\xf4'  # 244 = llano
TEENSY_OBST_INICIO = b'\\xf5'  # 245 = empieza el esquive del obstaculo (OBST_SIN_RECUP)
TEENSY_OBST_FIN    = b'\\xf6'  # 246 = termino el esquive: volvio a la cinta
''')

rep('''_cresta = {"ult_linea": 0.0}''',
    '''_obst = {"ini": 0.0, "fin": 0.0, "reset": False}   # OBST_SIN_RECUP: cuando empezo / termino el esquive
_cresta = {"ult_linea": 0.0}''')

rep('''    if data == TEENSY_BOOT:
''', '''    if data in (TEENSY_OBST_INICIO, TEENSY_OBST_FIN):
        if data == TEENSY_OBST_INICIO:
            _obst.update(ini=time.monotonic(), fin=0.0, reset=True)
        elif _obst["ini"] > 0:
            _obst["fin"] = time.monotonic()
        if OBST_SIN_RECUP:
            print("[OBST] %s: %s" % (context, "empieza el esquive (0xF5): sin recuperacion"
                                     if data == TEENSY_OBST_INICIO else
                                     "volvio a la cinta (0xF6): sin recuperacion %.1f s mas" % OBST_POST_S))
        return 'obstaculo'

    if data == TEENSY_BOOT:
''')

# Cada entrada al modo linea: sin esquive pendiente.
rep('''        _recup_rumbo_fuente = "sin-camino"
        _loss_camino_frame = None
''', '''        _recup_rumbo_fuente = "sin-camino"
        _obst.update(ini=0.0, fin=0.0, reset=False)
        _loss_camino_frame = None
''')

rep('''                if BAJADA_SIN_RECUP and _vent_baj and not _linea_recup_ok:
                    _linea_recup_ok = True
                    angle = 0.0
                    _quien = "bajada-sin-recup"
''', '''                if BAJADA_SIN_RECUP and _vent_baj and not _linea_recup_ok:
                    _linea_recup_ok = True
                    angle = 0.0
                    _quien = "bajada-sin-recup"

                # ESQUIVANDO EL OBSTACULO y hasta OBST_POST_S despues: tampoco (ver OBST_SIN_RECUP).
                _now_ob = time.monotonic()
                _vent_obs = OBST_SIN_RECUP and _obst["ini"] > 0 and (
                    (_obst["fin"] == 0.0 and _now_ob - _obst["ini"] <= OBST_MAX_S) or
                    (_obst["fin"] > 0 and _now_ob - _obst["fin"] <= OBST_POST_S))
                if _vent_obs and not _linea_recup_ok:
                    _linea_recup_ok = True
                    angle = 0.0
                    _quien = "obstaculo-sin-recup"
''')

# Al empezar el esquive se cierra cualquier episodio de recuperacion que hubiera (el mismo reseteo que hace
# un verde). Solo con OBST_SIN_RECUP=1.
rep('''                _marca_prioritaria = green_state in (1, 2, 3)
''', '''                _marca_prioritaria = green_state in (1, 2, 3)
                if OBST_SIN_RECUP and _obst["reset"]:
                    _obst["reset"] = False
                    _marca_prioritaria = True
''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok obstaculo")
