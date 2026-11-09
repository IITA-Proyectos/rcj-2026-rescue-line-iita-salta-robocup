# Verdes de la bajada clasificados por tramo (1 = primer tramo, 2 = segundo tramo: abajo, antes de la rotonda),
# con rasgos medidos en los PNG crudos: donde estaba el cuadrado verde al detectarlo, cuanto duro la deteccion,
# giro de la Teensy (flujo optico), que veia la camara al terminar la maniobra y como termino.
import csv, math, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario_bajadas import RUNS
from lib_linea import solo_mi_linea, ley
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
def mmss(n): return '%d:%05.2f' % (n / 20 // 60, n / 20 % 60)
_CAPS = {}
VIDEO_ACTUAL = {'v': None}
def png(d, n):
    im = cv2.imread(os.path.join(d, 'f_%06d.png' % n)) if os.path.exists(os.path.join(d, 'f_%06d.png' % n)) else None
    if im is not None: return im
    v = VIDEO_ACTUAL['v']
    cap = _CAPS.setdefault(v, cv2.VideoCapture(v)); cap.set(cv2.CAP_PROP_POS_FRAMES, n - 1)
    ok, f = cap.read()
    return f[1::2, 1:320:2][:120, :160].copy()
def verde_info(im):
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); gm = np.zeros(im.shape[:2], np.uint8)
    gm[80:] = cv2.inRange(lab[80:], LG, UG)
    ys, xs = np.nonzero(gm)
    if len(ys) == 0: return 0, None, None
    return len(ys), int(np.mean(ys)), int(np.mean(xs))
def negro(im):
    bm = cv2.inRange(im, np.array([0, 0, 0]), np.array([90, 90, 90])); bm[:60] = 0
    return bm
def giro_serie(video, a, b):
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, a - 1)
    mk = np.zeros((240, 320), np.uint8); mk[0:105, :] = 255; mk[0:60, 0:150] = 0
    prev = None; acc = 0.0; s = {}
    for n in range(a, b + 1):
        ok, f = cap.read()
        if not ok: break
        g = cv2.cvtColor(f[:, :320], cv2.COLOR_BGR2GRAY)
        if prev is not None:
            p0 = cv2.goodFeaturesToTrack(prev, 80, 0.01, 6, mask=mk)
            if p0 is not None and len(p0) >= 6:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, winSize=(21, 21), maxLevel=3); o = st.ravel() == 1
                if o.sum() >= 6: acc += math.degrees(math.atan(np.median(p1[o, 0, 0] - p0[o, 0, 0]) / 238.0))
        prev = g; s[n] = acc
    return s
filas = []
for nombre, run, cr, vid in RUNS:
    VIDEO_ACTUAL['v'] = os.path.join(run, vid)
    d = os.path.join(run, cr); r = list(csv.DictReader(open(os.path.join(d, 'cuadros.csv')))); N = len(r)
    tn = [float(x['t']) for x in r]
    # tramos de bajada
    tr = []; cur = None
    for i, x in enumerate(r):
        if x['rampa'] == '-1':
            if cur and i <= cur[1] + 30: cur[1] = i
            else: cur = [i, i]; tr.append(cur)
    for k, (a, b) in enumerate(tr):
        tramo = 2 if k > 0 and 0 < tn[a] - tn[tr[k - 1][1]] <= 8.0 else 1
        # verdes desde el inicio del tramo hasta 4 s despues de su fin
        i = a; nv = 0
        while i < N and tn[i] - tn[b] <= 4.0:
            if r[i]['green_state'] in ('1', '2', '3') and r[i - 1]['green_state'] not in ('1', '2', '3'):
                j = i
                while j + 1 < N and r[j + 1]['green_state'] in ('1', '2', '3'): j += 1
                nv += 1; t0 = tn[i]; n0 = int(r[i]['n'])
                area, gy, gx = verde_info(png(d, n0))
                # vista al terminar la maniobra (~1,7 s)
                m17 = next((m for m in range(i, N) if tn[m] - t0 >= 1.7), N - 1)
                bm = negro(png(d, int(r[m17]['n']))); mi = solo_mi_linea(bm)
                post = [m for m in range(j + 1, N) if tn[m] - t0 <= 4.0]
                ceros = sum(1 for m in post if r[m]['angle'] in ('0.0', '0') and r[m]['quien'] != 'centroide')
                otro = next((mmss(int(r[m]['n'])) for m in post if r[m]['green_state'] in ('1', '2', '3') and r[m - 1]['green_state'] not in ('1', '2', '3')), '-')
                fin = next((m for m in range(i, N) if tn[m] - t0 > 3.5), N - 1)
                se = giro_serie(os.path.join(run, vid), n0, int(r[fin]['n']))
                g2 = se.get(int(r[next((m for m in range(i, N) if tn[m] - t0 >= 2.0), N - 1)]['n']), float('nan'))
                g35 = se.get(int(r[fin]['n']) - 1, float('nan'))
                salto = next((mmss(int(r[m]['n'])) for m in range(i + 1, N) if tn[m] - t0 <= 10.0 and tn[m] - tn[m - 1] > 1.0), '')
                recup = next((mmss(int(r[m]['n'])) for m in range(i, N) if tn[m] - t0 <= 10.0 and r[m]['green_state'] in ('4', '18', '19')), '')
                filas.append(dict(corrida=nombre, video=mmss(n0), tramo=tramo, orden=nv, gs={'1': 'IZQ', '2': 'DER', '3': 'DOB'}[r[i]['green_state']],
                                  cuadros=j - i + 1, verde_px=area, verde_y=gy, giro2=g2, giro35=g35,
                                  vista_px=int(np.count_nonzero(bm)), vista_conectada=int(np.count_nonzero(mi)),
                                  vista_ley=('%+.0f' % ley(mi)) if np.count_nonzero(mi) else '-', ceros=ceros, otro_verde=otro,
                                  recup=recup, reubicado=salto))
                i = j + 1
            else:
                i += 1
w = csv.DictWriter(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verdes_bajada_rasgos.csv'), 'w', newline=''), fieldnames=list(filas[0].keys()))
w.writeheader(); [w.writerow(f) for f in filas]
print('%-12s %-9s %-2s %-2s %-3s %4s %5s %4s %6s %6s %6s %6s %5s %5s %-9s %-8s %-8s' % ('corrida', 'video', 'tr', '#', 'gs', 'cuad', 'vpx', 'vy', 'giro2', 'giro35', 'vpx17', 'conec', 'ley', 'ceros', 'otroverde', 'recup', 'reubic'))
for f in filas:
    print('%-12s %-9s %-2d %-2d %-3s %4d %5d %4s %+6.0f %+6.0f %6d %6d %5s %5d %-9s %-8s %-8s' % (f['corrida'], f['video'], f['tramo'], f['orden'], f['gs'], f['cuadros'], f['verde_px'], f['verde_y'], f['giro2'], f['giro35'], f['vista_px'], f['vista_conectada'], f['vista_ley'], f['ceros'], f['otro_verde'], f['recup'], f['reubicado']))
