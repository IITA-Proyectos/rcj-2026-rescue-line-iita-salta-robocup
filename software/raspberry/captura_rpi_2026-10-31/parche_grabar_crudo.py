# GRABAR_CRUDO (12-oct): main.py guarda cada cuadro sin comprimir + lo que decidio + los parametros, con
# grabador_crudo.py. Sin la variable, main.py hace exactamente lo mismo que antes. Uso: parche_grabar_crudo.py main.py
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == 1, (a[:60], s.count(a))
    s = s.replace(a, b)


rep('''RUTA_VIDEO   = os.environ.get("GRABAR", "")
''', '''RUTA_VIDEO   = os.environ.get("GRABAR", "")
# GRABAR_CRUDO=carpeta (12-oct): ademas del video, guarda CADA cuadro sin comprimir (PNG 160x120), lo que se
# mando a la Teensy, los pixeles de verde/negro, los rangos y la camara (ver grabador_crudo.py). Sirve para
# calibrar y analizar despues con todos los datos. Vacio = apagado.
GRABAR_CRUDO = os.environ.get("GRABAR_CRUDO", "")
_crudo = None
''')

rep('''        print("[GRABAR] se apaga por error: %s" % _e)
        globals()["RUTA_VIDEO"] = ""
''', '''        print("[GRABAR] se apaga por error: %s" % _e)
        globals()["RUTA_VIDEO"] = ""


def _grabar_crudo(frame_bgr, green_mask, black_mask, speed, angle, green_state, silver, quien):
    """GRABAR_CRUDO: un PNG y una linea de CSV por cuadro. Nunca levanta una excepcion hacia el lazo."""
    global _crudo
    try:
        if _crudo is None:
            from grabador_crudo import GrabadorCrudo
            g = globals()
            par = {k: (g[k].tolist() if hasattr(g.get(k), "tolist") else g.get(k)) for k in (
                "lower_green", "upper_green", "lower_black", "upper_black", "min_square_size",
                "lower_red1", "upper_red1", "lower_red2", "upper_red2", "lower_silver_hsv", "upper_silver_hsv")}
            _crudo = GrabadorCrudo(os.path.expanduser(GRABAR_CRUDO), par, os.path.abspath(__file__))
        _crudo.cuadro(frame_bgr, estado, speed, angle, green_state, silver, quien,
                      int(np.count_nonzero(green_mask)), int(np.count_nonzero(black_mask)), _rampa_teensy)
    except Exception as _e:
        print("[GRABAR_CRUDO] se apaga por error: %s" % _e)
        globals()["GRABAR_CRUDO"] = ""
''')

rep('''            _grabar(frame_resized, _ang_viejo, angle, _r, _quien, _corte)
''', '''            _grabar(frame_resized, _ang_viejo, angle, _r, _quien, _corte)
            if GRABAR_CRUDO:
                _grabar_crudo(frame_resized, green_mask, black_mask, speed, angle, green_state, silver_line, _quien)
''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok grabar crudo")
