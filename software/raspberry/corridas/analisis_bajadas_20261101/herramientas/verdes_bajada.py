# Todos los verdes que aparecen bajando (Teensy en BAJA o hasta 1 s despues): largo del bloque, giro medido
# con flujo optico, que hizo la Pi despues y si hubo reposicionamiento (salto de tiempo) o recuperacion.
import csv, math, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario_bajadas import RUNS
F = 238.0
def mmss(n): return '%d:%05.2f' % (n / 20 // 60, n / 20 % 60)
def giro(video, a, b):
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, a - 1)
    mk = np.zeros((240, 320), np.uint8); mk[0:105, :] = 255; mk[0:60, 0:150] = 0
    prev = None; acc = 0.0; serie = {}
    for n in range(a, b + 1):
        ok, f = cap.read()
        if not ok: break
        g = cv2.cvtColor(f[:, :320], cv2.COLOR_BGR2GRAY)
        if prev is not None:
            p0 = cv2.goodFeaturesToTrack(prev, 80, 0.01, 6, mask=mk)
            if p0 is not None and len(p0) >= 6:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, winSize=(21, 21), maxLevel=3)
                o = st.ravel() == 1
                if o.sum() >= 6: acc += math.degrees(math.atan(np.median(p1[o, 0, 0] - p0[o, 0, 0]) / F))
        prev = g; serie[n] = acc
    return serie
filas = []
for nombre, run, cr, vid in RUNS:
    r = list(csv.DictReader(open(os.path.join(run, cr, 'cuadros.csv'))))
    N = len(r); i = 0
    while i < N:
        g = r[i]['green_state']
        if g in ('1', '2', '3') and (i == 0 or r[i - 1]['green_state'] not in ('1', '2', '3')):
            j = i
            while j + 1 < N and r[j + 1]['green_state'] in ('1', '2', '3'): j += 1
            t0 = float(r[i]['t'])
            # bajando: rampa -1 en el cuadro o en el segundo anterior
            k = i
            bajando = False
            while k >= 0 and t0 - float(r[k]['t']) <= 1.0:
                if r[k]['rampa'] == '-1': bajando = True; break
                k -= 1
            if bajando:
                # despues: hasta 8 s
                post = [x for x in r[j + 1:] if float(x['t']) - t0 <= 8.0]
                salto = next((mmss(int(r[m]['n'])) for m in range(i + 1, N) if float(r[m]['t']) - t0 <= 10.0 and float(r[m]['t']) - float(r[m - 1]['t']) > 1.0), '')
                recup = next((mmss(int(x['n'])) for x in post if x['green_state'] in ('4', '18', '19')), '')
                n0 = int(r[i]['n'])
                # cuadros con t <= t0 + 3,5 s
                nf = max(int(x['n']) for x in r[i:] if float(x['t']) - t0 <= 3.5)
                se = giro(os.path.join(run, vid), n0, nf)
                def g_at(dt):
                    cand = [int(x['n']) for x in r[i:] if float(x['t']) - t0 <= dt]
                    return se.get(max(cand), float('nan')) if cand else float('nan')
                cero = sum(1 for x in post if float(x['t']) - t0 <= 4.0 and x['angle'] in ('0.0', '0') and x['quien'] != 'centroide')
                filas.append((nombre, mmss(n0), {'1': 'IZQ', '2': 'DER', '3': 'DOB'}[g], j - i + 1,
                              round(g_at(1.0), 0), round(g_at(2.0), 0), round(g_at(3.5), 0), cero, recup, salto))
            i = j + 1
        else:
            i += 1
print('%-13s %-9s %-4s %5s %7s %7s %7s %7s %-9s %-9s' % ('corrida', 'video', 'lado', 'cuad', 'giro1s', 'giro2s', 'giro3.5', 'manda0', 'recup', 'reubicado'))
for f in filas:
    print('%-13s %-9s %-4s %5d %+7.0f %+7.0f %+7.0f %7d %-9s %-9s' % f)
print('total', len(filas))
