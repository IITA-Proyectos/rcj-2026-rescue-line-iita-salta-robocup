# Calibrador de verde (copia de la Pi, b24d55fb): (1) los valores "MAIN" los LEE de main.py, ya no hay que
# copiarlos a mano; (2) el chequeo de espejo mira main.py; (3) cada tecla c y m queda anotada en
# ~/luz/calibraciones.txt con el cuadro usado (PNG) y los puntos. Uso: parche_calibrador.py calibrador_verde.py
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


rep('''BLACK_TOP_CUT = 55    # black_mask[:55, :] = 0
RATIO_NEGRO_MIN = 0.32
FACTOR_DOBLE = 1.25   # Main.py linea 828 (ojo: Main_challenge.py tambien usa 1.25)
''', '''BLACK_TOP_CUT = 60    # black_mask[:60, :] = 0 (main.py)
RATIO_NEGRO_MIN = 0.32
FACTOR_DOBLE = 1.2    # main.py: np.sum(green_mask) > 1.2 * min_square_size * 255


# 12-oct: los valores "MAIN" se LEEN del main.py que esta al lado (el que corre el robot). Antes habia que
# copiarlos a mano y quedaron viejos (550 / [80,87,85]-[205,123,120] contra 510 o 250 en main.py).
def _leer_main(ruta=os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")):
    out = {}
    try:
        src = open(ruta, encoding="utf-8", errors="replace").read()
    except OSError:
        return out
    for nombre in ("lower_green", "upper_green", "lower_black", "upper_black"):
        m = re.search(r"^" + nombre + r"\\s*=\\s*np\\.array\\(\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]", src, re.M)
        if m:
            out[nombre] = np.array([int(g) for g in m.groups()])
    m = re.search(r"^min_square_size\\s*=\\s*(\\d+)", src, re.M)
    if m:
        out["min_square_size"] = int(m.group(1))
    return out


_M = _leer_main()
if _M:
    MAIN_LOWER_GREEN = _M.get("lower_green", MAIN_LOWER_GREEN)
    MAIN_UPPER_GREEN = _M.get("upper_green", MAIN_UPPER_GREEN)
    MAIN_LOWER_BLACK = _M.get("lower_black", MAIN_LOWER_BLACK)
    MAIN_UPPER_BLACK = _M.get("upper_black", MAIN_UPPER_BLACK)
    MAIN_MIN_SQUARE_SIZE = _M.get("min_square_size", MAIN_MIN_SQUARE_SIZE)
    print("[calibrador] valores leidos de main.py:", {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in _M.items()})
else:
    print("[calibrador] OJO: no encontre main.py al lado: uso los valores escritos en este archivo")

# Registro de cada calibracion (tecla c) y medicion (tecla m), con el cuadro usado
REGISTRO_DIR = os.path.expanduser("~/luz")


def _registrar(texto, frame=None, puntos=None):
    try:
        os.makedirs(REGISTRO_DIR, exist_ok=True)
        sello = time.strftime("%m%d_%H%M%S")
        linea = "%s  %s" % (sello, texto)
        if frame is not None:
            img = os.path.join(REGISTRO_DIR, "calib_%s.png" % sello)
            cv2.imwrite(img, frame)
            linea += "  cuadro=%s" % os.path.basename(img)
        if puntos:
            linea += "  puntos=%s" % list(puntos)
        with open(os.path.join(REGISTRO_DIR, "calibraciones.txt"), "a") as f:
            f.write(linea + "\\n")
    except Exception as e:
        print("[calibrador] no pude anotar:", e)
''')

rep('''    for fname in ("Main.py", "Main_challenge.py"):
''', '''    for fname in ("main.py",):
''')

rep('''            rango_calibrado = (lo, hi)
            print("\\n--- Calibracion color ---")
''', '''            rango_calibrado = (lo, hi)
            _registrar("c lower=%s upper=%s" % (lo.tolist(), hi.tolist()), frame_resized, points)
            print("\\n--- Calibracion color ---")
''')

rep('''            rec = imprimir_recomendacion(green_mask, nombre_rango)
''', '''            rec = imprimir_recomendacion(green_mask, nombre_rango)
            _registrar("m rango=%s %s-%s verde=%dpx recomienda min_square_size=%s" % (
                nombre_rango, np.array(lower).tolist(), np.array(upper).tolist(),
                int(cv2.countNonZero(green_mask)), rec), frame_resized)
''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok calibrador")
