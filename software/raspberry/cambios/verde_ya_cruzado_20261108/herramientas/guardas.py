# Las imagenes de protecciones del calibrador de ChatGPT: la funcion nueva decide igual que la de hoy?
import glob, importlib.util, sys, os
import cv2, numpy as np
sys.dont_write_bytecode = True
OLD = 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad'
NEW = 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/2a6124af-dd8b-472c-b95b-351384f76cc1/scratchpad'
def cargar(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
E = cargar(OLD + '/simE/verde_oscuro.py', 've'); F = cargar(NEW + '/simF/verde_oscuro.py', 'vf')
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
R = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/cambios/calibrador_verdes_express_20261102/protecciones'
pngs = sorted(glob.glob(R + '/**/*.png', recursive=True))
print('imagenes:', len(pngs)); dif = 0; dec = 0
for p in pngs:
    im = cv2.imread(p)
    if im is None or im.shape[:2] != (120, 160): print('  salto', os.path.basename(p), None if im is None else im.shape); continue
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); neg = cv2.inRange(im, np.zeros(3, np.uint8), np.array([90, 90, 90], np.uint8)); neg[:60] = 0
    a = E.detectar_verde_sombra(lab, neg, LG, UG, 200, 1.0)[0]; b = F.detectar_verde_sombra(lab, neg, LG, UG, 200, 1.0)[0]
    dec += a != 0
    if a != b: dif += 1; print('  DISTINTA', os.path.basename(p), a, b)
print('sombra decide en', dec, '| distintas:', dif)
