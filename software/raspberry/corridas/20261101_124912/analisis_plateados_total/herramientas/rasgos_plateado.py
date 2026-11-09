# Rasgos de "banda plateada" en los cuadros despues del retroceso de cada recuperacion.
import cv2, json, os, sys, numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
eps = json.load(open(os.path.join(AQUI, 'episodios.json')))
PLATEADO = {('1-nov 12:49', n) for n in (5033, 9186, 9348, 15340, 15650, 15952, 16129, 21035)}
_caps = {}
def cuadro(e, n):
    p = os.path.join(BASE, e['run'], e['cr'], 'f_%06d.png' % n)
    if os.path.exists(p): return cv2.imread(p)
    v = os.path.join(BASE, e['run'], e['vid']); cap = _caps.setdefault(v, cv2.VideoCapture(v))
    cap.set(cv2.CAP_PROP_POS_FRAMES, n - 1); ok, f = cap.read()
    return f[1::2, 1:320:2][:120, :160].copy()
def rasgos(im):
    roi = im[60:120]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    gris = (S < 60) & (V > 110) & (V < 225)
    tex = gris & (sd > 7)
    # banda: componente gris mas ancha
    n, et, st, _ = cv2.connectedComponentsWithStats(gris.astype(np.uint8), 8)
    ancho = max([st[k, cv2.CC_STAT_WIDTH] for k in range(1, n) if st[k, cv2.CC_STAT_AREA] >= 300], default=0)
    blanco = (S < 40) & (V >= 225)
    negro = V < 90
    return dict(gris=int(gris.sum()), tex=int(tex.sum()), ancho=int(ancho), blanco=int(blanco.sum()), negro=int(negro.sum()))
out = []
for e in eps:
    rs = [rasgos(cuadro(e, n)) for n in e['post'][:30]]
    if not rs: continue
    mx = {k: max(r[k] for r in rs) for k in rs[0]}
    med = {k: float(np.median([r[k] for r in rs])) for k in rs[0]}
    out.append(dict(corrida=e['corrida'], video=e['video'], n=e['n_gs4'], decision=e['decision'], fin=e['fin'],
                    plateado=(e['corrida'], e['n_gs4']) in PLATEADO, mx=mx, med=med))
json.dump(out, open(os.path.join(AQUI, 'rasgos_plateado.json'), 'w'))
print('listo', len(out))
