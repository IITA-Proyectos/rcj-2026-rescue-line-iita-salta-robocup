# Firma de la entrada al plateado en cada cuadro: cinta negra = una cuna abajo, sin rama hacia el borde izquierdo,
# con el borde de arriba recto en diagonal; mas el puntaje de banda (gris con textura).
import cv2, json, os, sys, csv, numpy as np
NEW = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, NEW)
def firma(im):
    negro = cv2.inRange(im, np.array([0, 0, 0]), np.array([90, 90, 90])); negro[:60] = 0
    n, et, st, _ = cv2.connectedComponentsWithStats(negro, 8)
    grandes = [k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] >= 40]
    toca_izq = any(np.count_nonzero(et[60:, :3] == k) > 0 for k in grandes)
    toca_der = any(np.count_nonzero(et[60:, -3:] == k) > 0 for k in grandes)
    abajo = [k for k in grandes if st[k, cv2.CC_STAT_TOP] + st[k, cv2.CC_STAT_HEIGHT] >= 115]
    res = dict(toca_izq=toca_izq, toca_der=toca_der, n_comp=len(grandes), area=0, ancho=0, pend=None, resid=None, top=None)
    if abajo:
        k = max(abajo, key=lambda q: st[q, cv2.CC_STAT_AREA])
        x0, w = st[k, cv2.CC_STAT_LEFT], st[k, cv2.CC_STAT_WIDTH]
        res.update(area=int(st[k, cv2.CC_STAT_AREA]), ancho=int(w), top=int(st[k, cv2.CC_STAT_TOP]))
        xs, ys = [], []
        for x in range(x0 + 2, x0 + w - 2):
            col = np.flatnonzero(et[:, x] == k)
            if len(col): xs.append(x); ys.append(col.min())
        if len(xs) >= 8:
            a, b = np.polyfit(xs, ys, 1); r = float(np.sqrt(np.mean((np.polyval([a, b], xs) - np.array(ys)) ** 2)))
            res.update(pend=float(a), resid=r)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    res['banda'] = int(((S < 60) & (V > 110) & (V < 225) & (sd > 7))[40:].sum())
    return res
if __name__ == '__main__':
    import rasgos_plateado as RP
    from rasgos2 import PLATEADO
    BASE = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
    eps = json.load(open(NEW + '/episodios.json')); cache = {}; out = []
    for e in eps:
        key = (e['run'], e['cr'])
        if key not in cache:
            r = list(csv.DictReader(open(os.path.join(BASE, e['run'], e['cr'], 'cuadros.csv')))); cache[key] = (r, {int(x['n']): i for i, x in enumerate(r)})
        r, idx = cache[key]; i0 = idx[e['n_gs4']]
        kd = next((k for k in range(i0, min(len(r), i0 + 80)) if r[k]['quien'] in ('recup-CURVA', 'gap-inicio')), None)
        if kd is None: continue
        ini = idx.get(e['post'][0], kd) if e['post'] else kd
        post = [int(r[k]['n']) for k in range(min(ini, kd), kd + 1)]
        pre = [int(r[k]['n']) for k in range(i0 - 6, i0)]
        out.append(dict(k=[e['corrida'], e['video']], dec=r[kd]['quien'], ang=float(r[kd]['angle']), plateado=(e['corrida'], e['video']) in PLATEADO,
                        post=[firma(RP.cuadro(e, n)) for n in post], pre=[firma(RP.cuadro(e, n)) for n in pre]))
    json.dump(out, open(NEW + '/firma.json', 'w')); print('listo', len(out))
