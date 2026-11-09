# Dos cambios para main.py, cada uno detras de su variable (sin la variable, main.py hace exactamente lo mismo):
#   CAMARA_WB=4600     fija el balance de blancos de la camara en esa temperatura (2800-6500) al abrirla y cada
#                      vez que se reabre. Sale de medir_wb.py. Vacio = automatico, como hoy.
#   CAMARA_EXPO=40     fija tambien la exposicion (10-626, decimas de ms). Vacio = automatica, como hoy.
#   DOBLE_SIN_FACTOR=1 el doble verde ya no pide 1,2 veces min_square_size: alcanza con dos manchas y la cinta
#                      en el medio (corrida 12-oct: el doble de 21,5 s fallo con 299 px contra 300).
# Uso: python3 parche_camara_doble.py main.py
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b, veces=1):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == veces, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''RUTA_VIDEO   = os.environ.get("GRABAR", "")
''', '''RUTA_VIDEO   = os.environ.get("GRABAR", "")
# CAMARA (12-oct). La camara corria con balance de blancos y exposicion en AUTOMATICO: el color de las mismas
# marcas verdes se fue corriendo dia a dia (canal b 126 -> 120 -> 115) y el rango dejaba de alcanzar.
#   CAMARA_WB=4600   balance de blancos fijo en esa temperatura (medirla en el lugar con medir_wb.py)
#   CAMARA_EXPO=40   exposicion fija (decimas de ms). Probar en el lugar: 100 o mas quemo la imagen el 12-oct
# Vacias = automatico, exactamente como antes. Se aplican al abrir la camara y cada vez que se reabre.
CAMARA_WB    = os.environ.get("CAMARA_WB", "")
CAMARA_EXPO  = os.environ.get("CAMARA_EXPO", "")
# DOBLE_SIN_FACTOR=1 (12-oct): el doble verde pedia ademas 1,2 x min_square_size pixeles verdes. El primer
# cuadro con los dos cuadrados a la vista podia quedar justo abajo (299 contra 300) y salia como verde SIMPLE,
# que es lo que ejecuta la Teensy. Con 1, alcanza con dos manchas y la cinta entre ellas. 0 = como antes.
FACTOR_DOBLE = 1.0 if os.environ.get("DOBLE_SIN_FACTOR", "0") == "1" else 1.2
''')

rep('''
vs = WebcamVideoStream(src=0).start()
ser = serial.Serial(''', '''
vs = WebcamVideoStream(src=0).start()


def _fijar_camara(esperar=True):
    """CAMARA_WB / CAMARA_EXPO: fija los controles con v4l2-ctl. Sin las variables no hace nada."""
    if not (CAMARA_WB or CAMARA_EXPO):
        return
    import subprocess
    try:
        _fijar_camara_v4l2(subprocess, esperar)
    except Exception as e:   # sin v4l2-ctl o sin camara: sigue en automatico, como antes
        print("[CAMARA] no se pudo fijar la camara: %s" % e)


def _fijar_camara_v4l2(subprocess, esperar):
    ordenes = []
    if CAMARA_EXPO:
        ordenes += ["auto_exposure=1", "exposure_time_absolute=%d" % int(CAMARA_EXPO)]   # primero manual
    if CAMARA_WB:
        ordenes += ["white_balance_automatic=0", "white_balance_temperature=%d" % int(CAMARA_WB)]
    for o in ordenes:
        r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "-c", o], capture_output=True, text=True)
        if r.returncode != 0:
            print("[CAMARA] no se pudo aplicar %s: %s" % (o, r.stderr.strip()))
    r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "--list-ctrls"], capture_output=True, text=True)
    print("[CAMARA] " + " | ".join(l.split()[0] + "=" + l.split("value=")[1].split()[0]
                                   for l in r.stdout.splitlines()
                                   if "value=" in l and ("exposure" in l or "white_balance" in l)))
    if esperar:
        time.sleep(0.5)          # el sensor tarda unos cuadros en asentarse con los valores nuevos


_fijar_camara()
ser = serial.Serial(''')

rep('''    vs = WebcamVideoStream(src=0).start()
    return vs
''', '''    vs = WebcamVideoStream(src=0).start()
    _fijar_camara(esperar=False)  # al reabrir puede volver a automatico: se fija de nuevo, sin esperar
    return vs
''')

rep('''np.sum(green_mask) > (1.2 * min_square_size * 255):''',
    '''np.sum(green_mask) > (FACTOR_DOBLE * min_square_size * 255):''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok camara + doble")
