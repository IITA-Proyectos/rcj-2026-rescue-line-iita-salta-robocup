# Corrida del 8-nov 10:30: cada vez que decide el detector de sombra, que diria la regla nueva; hoja con cada verde.
import csv, importlib.util, sys, collections
import cv2, numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.dont_write_bytecode = True
NEW = 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/2a6124af-dd8b-472c-b95b-351384f76cc1/scratchpad'
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134]); ZB, UB = np.zeros(3, np.uint8), np.array([90, 90, 90], np.uint8)
def cargar():
    s = importlib.util.spec_from_file_location('vf', NEW + '/simF/verde_oscuro.py'); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
VF = None
def banda(lab, L, R, m):
    col = lab[:, L:R + 1]; v = col[..., 1] < 120; neg = (col[..., 0] < 97) & ~v
    fr = v.mean(axis=1); f = np.flatnonzero(m[:, L:R + 1].any(axis=1)); y0, y1 = int(f[0]), int(f[-1])
    while y0 > 0 and fr[y0 - 1] > .15: y0 -= 1
    while y1 < 119 and fr[y1 + 1] > .15: y1 += 1
    a0, a1 = max(0, y0 - 14), max(0, y0 - 2); b0, b1 = y1 + 3, min(120, y1 + 15)
    return (float(neg[a0:a1].mean()) if a1 > a0 else -1.0, float(neg[b0:b1].mean()) if b1 > b0 else -1.0)
def una(f):
    global VF
    if VF is None: VF = cargar()
    n = int(f['n']); im = cv2.imread('%s/f_%06d.png' % (D, n))
    if im is None: return None
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); neg = cv2.inRange(im, ZB, UB); neg[:60] = 0
    gm = np.zeros((120, 160), np.uint8); gm[80:] = cv2.inRange(lab[80:], LG, UG)
    if np.count_nonzero(gm) > 200:
        cols = np.amax(gm, axis=0); idx = np.where(cols == cols.max())[0]; L, R = int(idx[0]), int(idx[-1])
        if R > L and np.sum(neg[60:90, L:R + 1]) / (255 * 30 * (R - L)) > .32 and np.sum(neg[90:]): return None
    if VF.detectar_verde_oscuro(lab, neg, LG, UG, 200, 1.0)[0]: return None
    # version sin la regla: se apaga un momento el ayudante
    orig = VF._verde_ya_cruzado; VF._verde_ya_cruzado = lambda *a: False
    gs, _ = VF.detectar_verde_sombra(lab, neg, LG, UG, 200, 1.0); VF._verde_ya_cruzado = orig
    if not gs: return None
    lo = LG.copy(); up = UG.copy(); lo[0] = min(int(lo[0]), 60); up[1] = max(int(up[1]), 111); up[2] = max(int(up[2]), 137)
    m = np.zeros(neg.shape, np.uint8); m[80:] = cv2.inRange(lab[80:], lo, up)
    xs = np.flatnonzero(m.any(axis=0)); L, R = int(xs[0]), int(xs[-1])
    ar, ab = banda(lab, L, R, m)
    return dict(n=n, t=f['t'], robot=int(f['green_state']), gs=int(gs), L=L, R=R, arriba=round(ar, 3), abajo=round(ab, 3), regla=int(orig(lab, m, L, R)), quien=f['quien'])
if __name__ == '__main__':
    filas = list(csv.DictReader(open(D + '/cuadros.csv')))
    with ProcessPoolExecutor(12) as ex: r = [x for x in ex.map(una, filas, chunksize=100) if x]
    with open(NEW + '/hoy_sombra.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(r[0].keys())); w.writeheader(); w.writerows(r)
    print('cuadros', len(filas), '| decide sombra', len(r), '| coincide con el gs del robot', sum(x['robot'] == x['gs'] for x in r))
    print('la regla los ignoraria:', [(x['n'], x['t'], 'gs', x['gs'], 'L-R', x['L'], x['R']) for x in r if x['regla']])
    print('mas cerca de la regla (arriba<0.2):')
    for x in sorted([x for x in r if 0 <= x['arriba'] < .2], key=lambda x: -x['abajo'])[:14]:
        print('  ', x['n'], 'gs', x['gs'], 'rob', x['robot'], 'arriba', x['arriba'], 'abajo', x['abajo'], 'L-R', x['L'], x['R'], 'regla', x['regla'])
