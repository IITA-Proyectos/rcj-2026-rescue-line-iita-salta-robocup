import csv, collections
import cv2, numpy as np
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
F = {int(x['n']): x for x in csv.DictReader(open(D + '/cuadros.csv'))}
W, H = 200, 150
filas = []
for titulo, base, ultimo in (('GS19 #1', 2739, 2763), ('GS19 #2', 8609, 8690), ('GS19 #3', 9088, 9159), ('quieto 4835', 4835, 4836), ('quieto 7517', 7517, 7518)):
    pasos = [base + d for d in (-60, -35, -20, -8, -2)] + [base, min(ultimo, base + 14), ultimo]
    c = []
    for n in pasos:
        im = cv2.resize(cv2.imread('%s/f_%06d.png' % (D, n)), (W, H), interpolation=cv2.INTER_NEAREST)
        x = F[n]
        cv2.putText(im, '%d gs%s a%.0f' % (n, x['green_state'], float(x['angle'])), (3, 13), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(im, x['quien'][:24], (3, 144), cv2.FONT_HERSHEY_SIMPLEX, .36, (0, 255, 255), 1, cv2.LINE_AA)
        c.append(im)
    filas.append(np.hstack(c))
    seq = []; ant = None
    for n in range(base - 90, ultimo + 1):
        if n in F and F[n]['quien'] != ant:
            ant = F[n]['quien']; seq.append('%d:%s(gs%s,a%s)' % (n, ant[:24], F[n]['green_state'], F[n]['angle']))
    print(titulo, ' -> '.join(seq)[-900:])
cv2.imwrite('paradas_103028.jpg', np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 86])
