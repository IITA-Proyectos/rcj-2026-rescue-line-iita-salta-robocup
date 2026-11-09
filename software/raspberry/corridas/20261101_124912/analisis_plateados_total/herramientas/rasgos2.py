import cv2, json, os, sys, numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import rasgos_plateado as RP
eps = json.load(open(os.path.join(AQUI, 'episodios.json')))
PLATEADO = {('1-nov 12:49', '4:11.65'), ('1-nov 12:49', '7:39.30'), ('1-nov 12:49', '7:47.40'), ('1-nov 12:49', '12:47.00'),
            ('1-nov 12:49', '13:02.50'), ('1-nov 12:49', '13:17.60'), ('1-nov 12:49', '13:26.45'), ('1-nov 12:49', '17:31.75'),
            ('1-nov 12:38', '4:08.90'), ('1-nov 12:38', '4:02.35'), ('1-nov 11:47', '5:02.25'), ('1-nov 11:47', '14:22.20'),
            ('1-nov 13:54', '3:14.75')}
def feats(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); H = hsv[..., 0]; S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    tex = (S < 60) & (V > 110) & (V < 225) & (sd > 7)
    rojo = ((H < 8) | (H > 170)) & (S > 120) & (V > 90)
    verde = (H > 60) & (H < 95) & (S > 80) & (V > 40)
    return dict(tex_lo=int(tex[60:].sum()), tex_hi=int(tex[40:60].sum()), negro_hi=int((V[40:70] < 80).sum()),
                rojo_arr=int(rojo[0:45].sum()), verde_arr=int(verde[0:45].sum()))
out = []
for e in eps:
    fs = [feats(RP.cuadro(e, n)) for n in e['post'][:30]]
    if not fs: continue
    med = {k: float(np.median([f[k] for f in fs])) for k in fs[0]}
    mx = {k: max(f[k] for f in fs) for k in fs[0]}
    out.append(dict(k=[e['corrida'], e['video']], decision=e['decision'], fin=e['fin'], plateado=(e['corrida'], e['video']) in PLATEADO, med=med, mx=mx))
json.dump(out, open(os.path.join(AQUI, 'rasgos2.json'), 'w')); print('listo', len(out))
