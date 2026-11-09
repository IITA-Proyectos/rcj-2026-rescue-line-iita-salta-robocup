# Tira de un verde de la cresta: del cuadro del verde hasta ~3 s despues (video GRABAR con lo que mando la Pi).
import csv, sys, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
R = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261107_190335'
r = list(csv.DictReader(open(R + '/crudo_prueba_190335/1107_190339/cuadros.csv'))); idx = {int(x['n']): i for i, x in enumerate(r)}
cap = cv2.VideoCapture(R + '/pista_prueba_190335.avi'); F = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
out, n0 = sys.argv[1], int(sys.argv[2]); i0 = idx[n0]; t0 = float(r[i0]['t'])
quiero = [0.0, 0.7, 1.2, 1.45, 1.6, 1.75, 1.9, 2.1, 2.4, 2.8, 3.3, 4.0]
tiles = []
for q in quiero:
    k = min(range(i0, min(len(r), i0 + 200)), key=lambda j: abs(float(r[j]['t']) - t0 - q))
    if abs(float(r[k]['t']) - t0 - q) > 0.3: continue
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(r[k]['n']) - 1); ok, f = cap.read()
    im = Image.fromarray(cv2.cvtColor(cv2.resize(f, (480, 180)), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(im)
    d.rectangle([0, 160, 480, 180], fill=(0, 0, 0))
    d.text((4, 162), '+%.2f s  %s  manda %s  gs%s  rampa %s' % (float(r[k]['t']) - t0, r[k]['quien'][:24], r[k]['angle'], r[k]['green_state'], r[k]['rampa']), font=F, fill=(255, 255, 0))
    tiles.append(im)
hoja = Image.new('RGB', (1440, 180 * ((len(tiles) + 2) // 3)), (255, 255, 255))
for j, im in enumerate(tiles): hoja.paste(im, ((j % 3) * 480, (j // 3) * 180))
hoja.save(out, quality=85); print('ok', len(tiles))
