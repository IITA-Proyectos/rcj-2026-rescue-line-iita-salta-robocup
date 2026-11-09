# Una casilla por cada decision de la recuperacion que anoto el log ([PLATEADO] hh:mm:ss ...): el cuadro de llegada y
# el de la decision, del video GRABAR. Sirve para ver cuales fueron en la entrada al plateado.
# Uso: python hoja_recuperaciones.py CARPETA_CORRIDA NOMBRE SALIDA.jpg
import csv, glob, os, re, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

R, N, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CR = glob.glob(os.path.join(R, 'crudo_' + N, '*', 'cuadros.csv'))[0]
sub = os.path.basename(os.path.dirname(CR))
T0 = int(sub[5:7]) * 3600 + int(sub[7:9]) * 60 + int(sub[9:11])
r = list(csv.DictReader(open(CR)))
t = np.array([float(x['t']) for x in r]) + T0
cap = cv2.VideoCapture(os.path.join(R, 'pista_' + N + '.avi'))
F = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 14)
dec = []
for l in open(os.path.join(R, 'pista_' + N + '.log'), encoding='utf-8', errors='replace'):
    m = re.match(r'\[PLATEADO\] (\d\d):(\d\d):(\d\d) (CURVA IZQ|CURVA DER|RECTA) llegada=(\d+) post=(\d+)', l)
    if m:
        h, mi, s = map(int, m.groups()[:3])
        dec.append((h * 3600 + mi * 60 + s, '%s:%s:%s' % m.groups()[:3], m.group(4), m.group(5), m.group(6)))


def cuadro(n):
    cap.set(cv2.CAP_PROP_POS_FRAMES, n - 1)
    ok, f = cap.read()
    return f[:, :320] if ok else np.zeros((240, 320, 3), np.uint8)


tiles = []
for th, hora, tipo, a, b in dec:
    cand = [i for i in range(len(r)) if th - 1.0 <= t[i] <= th + 2.0 and r[i]['quien'] in ('recup-CURVA', 'gap-inicio')]
    if not cand:
        continue
    kd = cand[0]
    i0 = kd
    while i0 > 0 and r[i0]['green_state'] in ('4', '18') and r[i0 - 1]['green_state'] in ('4', '18'):
        i0 -= 1
    lleg = cuadro(int(r[max(0, i0 - 3)]['n']))
    pos = cuadro(int(r[kd]['n']))
    im = Image.fromarray(cv2.cvtColor(np.hstack([lleg, pos]), cv2.COLOR_BGR2RGB)).resize((480, 180))
    d = ImageDraw.Draw(im)
    col = (255, 80, 80) if tipo == 'CURVA IZQ' else ((120, 200, 255) if tipo == 'CURVA DER' else (120, 255, 120))
    d.rectangle([0, 0, 480, 18], fill=(0, 0, 0))
    d.text((4, 1), '%s  %s  %s/%s   (llegada | decision)' % (hora, tipo, a, b), font=F, fill=col)
    tiles.append(im)
C = 4
hoja = Image.new('RGB', (C * 480, ((len(tiles) + C - 1) // C) * 180), (40, 40, 40))
for j, im in enumerate(tiles):
    hoja.paste(im, ((j % C) * 480, (j // C) * 180))
hoja.save(OUT, quality=85)
print('ok', len(tiles), 'de', len(dec), hoja.size)
