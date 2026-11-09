# Tiras de cuadros por pasada (7-nov): del video GRABAR (panel con lo que mando la Pi + mascara), alrededor de cada
# decision de la recuperacion que el log anoto con hora.
# Uso: python tiras2.py CARPETA_CORRIDA NOMBRE SALIDA HH:MM:SS [HH:MM:SS ...]
import csv, os, sys, datetime
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

import glob
R, NOM = sys.argv[1], sys.argv[2]
CR = os.path.dirname(glob.glob(os.path.join(R, 'crudo_' + NOM, '*', 'cuadros.csv'))[0])
VID = os.path.join(R, 'pista_' + NOM + '.avi')
_s = os.path.basename(CR)
T0 = int(_s[5:7]) * 3600 + int(_s[7:9]) * 60 + int(_s[9:11])   # la carpeta del crudo se llama MMDD_HHMMSS
r = list(csv.DictReader(open(CR + '/cuadros.csv')))
t = np.array([float(x['t']) for x in r]) + T0
cap = cv2.VideoCapture(VID)
F = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)


def cuadro(n):
    cap.set(cv2.CAP_PROP_POS_FRAMES, n - 1)
    ok, f = cap.read()
    return f if ok else np.zeros((240, 640, 3), np.uint8)


def hms(s):
    return '%02d:%02d:%05.2f' % (s // 3600, s // 60 % 60, s % 60)


def tira(hora):
    h, m, s = map(int, hora.split(':'))
    th = h * 3600 + m * 60 + s
    # la decision: primer cuadro recup-CURVA / gap-inicio dentro de [th - 1, th + 2]
    cand = [i for i in range(len(r)) if th - 1.0 <= t[i] <= th + 2.0 and r[i]['quien'] in ('recup-CURVA', 'gap-inicio')]
    if not cand:
        return None
    kd = cand[0]
    i0 = kd
    while i0 > 0 and r[i0 - 1]['green_state'] in ('4',) or (i0 > 0 and r[i0]['green_state'] != '4' and r[i0 - 1]['green_state'] == '4'):
        i0 -= 1
    # cuadros: llegada, disparo, decision y despues
    fin = kd
    while fin + 1 < len(r) and t[fin + 1] - t[fin] < 1.0 and t[fin + 1] - t[kd] < 6.0:
        fin += 1
    idx = [max(0, i0 - 6), i0, kd] + [min(fin, kd + d) for d in (8, 16, 25, 35, 50, 70, 95)]
    idx += [fin]
    tiles = []
    for k in idx:
        f = cv2.resize(cuadro(int(r[k]['n'])), (480, 180))
        im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(im)
        txt = '%s  %+.2f s  %s %s gs%s' % (hms(t[k])[3:], t[k] - t[kd], r[k]['quien'][:22], r[k]['angle'], r[k]['green_state'])
        d.rectangle([0, 160, 480, 180], fill=(0, 0, 0))
        d.text((4, 162), txt, font=F, fill=(255, 255, 0))
        tiles.append(im)
    W, H = 480, 180
    hoja = Image.new('RGB', (W * 3, H * ((len(tiles) + 2) // 3) + 26), (255, 255, 255))
    d = ImageDraw.Draw(hoja)
    d.text((6, 4), 'decision %s (log)  |  ultimo cuadro antes del corte: %s (+%.1f s)' % (hora, hms(t[fin]), t[fin] - t[kd]),
           font=F, fill=(0, 0, 0))
    for j, im in enumerate(tiles):
        hoja.paste(im, ((j % 3) * W, 26 + (j // 3) * H))
    return hoja


if __name__ == '__main__':
    out = sys.argv[3]
    hojas = [h for h in (tira(x) for x in sys.argv[4:]) if h is not None]
    W = max(h.width for h in hojas)
    total = Image.new('RGB', (W, sum(h.height + 10 for h in hojas)), (200, 200, 200))
    y = 0
    for h in hojas:
        total.paste(h, (0, y)); y += h.height + 10
    total.save(out)
    print('ok', len(hojas), total.size)
