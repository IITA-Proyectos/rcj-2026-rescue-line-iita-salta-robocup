# Figura: como sabe VERDE-CRESTA que la cinta ya conecto. Cuadros crudos de 12:49 (cruce de la cresta, verde DER).
import math, os, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

SW = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry'
sys.path.insert(0, SW + '/cambios/cresta_bajada_20261101')
import verde_cresta as VC

D = SW + '/corridas/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926'
SALIDA = sys.argv[1]
K = 3                                   # 160x120 -> 480x360
F = 'C:/Windows/Fonts/arial.ttf'; FB = 'C:/Windows/Fonts/arialbd.ttf'
f_tit = ImageFont.truetype(FB, 30); f_sub = ImageFont.truetype(F, 21)
f_cap_b = ImageFont.truetype(FB, 21); f_cap = ImageFont.truetype(F, 19); f_tag = ImageFont.truetype(FB, 18)

VERDE = (60, 200, 90); ROJO = (230, 60, 60); AMAR = (255, 210, 0); NAR = (255, 150, 0); AZUL = (40, 110, 255)

# (cuadro, titulo, explicacion, color de la etiqueta)
PANELES = [
    (22950, '0,00 s  Ve el verde a la derecha',
     'La Teensy está en SUBE: hace su maniobra (800 ms derecho + 39°). La Pi todavía no mira: espera 1,4 s.',
     (90, 160, 255), False),
    (22970, 'Así NO cuenta: apunta a la izquierda',
     'Toca la fila de abajo y es grande, pero apunta a la izquierda (ley +64). (Es de la maniobra: acá todavía no mira.)',
     NAR, True),
    (22984, '1,42 s  No hay cinta conectada → manda −85',
     'La cinta recién asoma en la esquina: toca abajo pero tiene 117 píxeles (hacen falta 200). Pivotea a la derecha.',
     ROJO, False),
    (22986, '1,49 s  Conectada y hacia la derecha: 1 de 4',
     'Ya tiene 299 píxeles, toca la fila de abajo y apunta a la derecha (ley −87). Empieza a contar.', VERDE, True),
    (22989, '1,60 s  4 cuadros seguidos así → suelta',
     'Ya está sobre la rama: deja de forzar y sigue la cinta con la cuenta de siempre.', VERDE, True),
    (22998, '1,98 s  Siguiendo la cinta normal',
     'Sigue la línea (ley +5). En este giro, el robot de verdad hizo lo mismo sin la regla.', VERDE, True),
]


def panel(n, tit, expl, col, flecha):
    im = cv2.imread(os.path.join(D, 'f_%06d.png' % n))
    neg = cv2.inRange(im, np.array([0, 0, 0]), np.array([90, 90, 90])); neg[:60] = 0
    con = VC._solo_mi_linea(neg)
    ley = VC._ley(con) if con is not None else None
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    ver = np.zeros(neg.shape, np.uint8)
    ver[80:] = cv2.inRange(lab[80:], np.array([120, 90, 110]), np.array([198, 109, 134]))
    big = cv2.resize(im, None, fx=K, fy=K, interpolation=cv2.INTER_NEAREST).astype(np.float32)
    up = lambda m: cv2.resize(m.astype(np.uint8), None, fx=K, fy=K, interpolation=cv2.INTER_NEAREST) > 0
    con_m = up(con) if con is not None else np.zeros(big.shape[:2], bool)
    suelto = up(neg > 0) & ~con_m
    big[:60 * K] = big[:60 * K] * 0.35 + 90                          # lo que no se mira
    for m, c in ((con_m, AZUL), (suelto, ROJO)):
        big[m] = big[m] * 0.4 + np.array(c[::-1]) * 0.6
    big = big.clip(0, 255).astype(np.uint8)
    cs, _ = cv2.findContours(up(ver).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(big, cs, -1, (255, 255, 0), 2)                  # cuadrado verde (celeste)
    y_fila = int((120 - 2) * K + K // 2)
    cv2.line(big, (0, y_fila), (big.shape[1], y_fila), AMAR[::-1], 2)
    if ley is not None and flecha:
        a = math.radians(ley + 90)
        x0, y0 = int(79.5 * K), int(119 * K)
        x1, y1 = int(x0 + 165 * math.cos(a)), int(y0 - 165 * math.sin(a))
        cuenta = ley <= 25
        cv2.arrowedLine(big, (x0, y0), (x1, y1), (VERDE if cuenta else NAR)[::-1], 5, tipLength=0.18)
    pi = Image.fromarray(cv2.cvtColor(big, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pi)
    d.text((8, 6), 'no se mira (arriba de la fila 60)', font=f_tag, fill=(235, 235, 235))
    d.text((8, y_fila - 26), 'fila de abajo', font=f_tag, fill=AMAR)
    if ley is not None and flecha:
        d.text((8, 32), 'ley %+.0f' % ley, font=f_tag, fill=(255, 255, 255))
    W = pi.width
    out = Image.new('RGB', (W, pi.height + 118), (250, 250, 248))
    out.paste(pi, (0, 0))
    d = ImageDraw.Draw(out)
    d.rectangle([0, pi.height, W, pi.height + 6], fill=col)
    d.text((10, pi.height + 12), tit, font=f_cap_b, fill=(25, 25, 25))
    palabras, lineas, cur = expl.split(), [], ''
    for p in palabras:
        if d.textlength(cur + ' ' + p, font=f_cap) > W - 20 and cur:
            lineas.append(cur); cur = p
        else:
            cur = (cur + ' ' + p).strip()
    lineas.append(cur)
    for k, l in enumerate(lineas[:3]):
        d.text((10, pi.height + 40 + 22 * k), l, font=f_cap, fill=(60, 60, 60))
    return out


ps = [panel(*p) for p in PANELES]
G = 18; W = ps[0].width; H = ps[0].height
head = 186
hoja = Image.new('RGB', (3 * W + 4 * G, head + 2 * H + 3 * G + 40), (250, 250, 248))
d = ImageDraw.Draw(hoja)
d.text((G, 14), '¿Cómo sabe la Pi que ya conectó?  Cruce de la cresta, verde a la derecha (12:49, a los 19:07)',
       font=f_tit, fill=(20, 20, 20))
d.text((G, 60), 'Conectada: la mancha negra toca la fila de abajo de la imagen (justo delante del robot) y tiene 200 píxeles'
       ' o más.', font=f_sub, fill=(50, 50, 50))
d.text((G, 88), 'Hacia la derecha: su ley (la cuenta de siempre de la Pi, con el centroide) da +25 o menos.',
       font=f_sub, fill=(50, 50, 50))
d.text((G, 116), 'Desde 1,4 s después del verde: 4 cuadros seguidos así → suelta. Si no, manda −85 (pivote a la derecha),'
       ' con un tope de 0,7 s.', font=f_sub, fill=(50, 50, 50))
x = G
for c, txt in ((AZUL, 'cinta conectada'), (ROJO, 'negro que no cuenta'), (AMAR, 'fila de abajo'),
               ((0, 255, 255), 'cuadrado verde'), (VERDE, 'flecha: apunta a la derecha'),
               (NAR, 'flecha: apunta a la izquierda')):
    d.rectangle([x, 156, x + 22, 174], fill=c); d.text((x + 30, 153), txt, font=f_sub, fill=(40, 40, 40))
    x += 46 + int(d.textlength(txt, font=f_sub))
for k, p in enumerate(ps):
    hoja.paste(p, (G + (k % 3) * (W + G), head + (k // 3) * (H + G)))
d.text((G, hoja.height - 34), 'Cuadros crudos de la Pi (corridas/20261101_124912). La regla y las cuentas son las de verde_cresta.py.',
       font=f_cap, fill=(110, 110, 110))
hoja.save(SALIDA)
print('ok', hoja.size)
