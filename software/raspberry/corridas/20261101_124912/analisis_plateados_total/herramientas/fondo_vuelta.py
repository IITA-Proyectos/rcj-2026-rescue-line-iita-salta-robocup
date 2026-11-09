# Cota "lo mas alto que da la banda en una vuelta normal": mediana movil de 6 cuadros sobre los cuadros de
# seguimiento en llano, lejos de las entradas al plateado. Comparar con las curvas IZQ (1620) y el plateado (1856).
import csv, json, os, sys, cv2, numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
RUNS = [('31-oct 19:53', '20261031_195318/crudo_20261031_195318/1031_195426'),
        ('31-oct 21:03', '20261031_210305/crudo_pista_completa_20261031_210305/1031_210325'),
        ('31-oct 21:36', '20261031_213650/crudo_recuperacion_corregida_20261031_213650/1031_213701'),
        ('31-oct 22:11', '20261031_221132/crudo_reenganche_20261031_221132/1031_221136'),
        ('1-nov 10:31', '20261101_103155/crudo_cierre3_20261101_103155/1101_103200'),
        ('1-nov 11:11', '20261101_111110/crudo_rampa_transicion_20261101_111110/1101_111120'),
        ('1-nov 11:47', '20261101_114747/crudo_verde_sombra_20261101_114747/1101_114752'),
        ('1-nov 12:38', '20261101_124912/crudo_doble_dato_20261101_123804/1101_123809'),
        ('1-nov 12:49', '20261101_124912/crudo_doble_dato_20261101_124912/1101_124926')]
def puntaje(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    return int(np.count_nonzero(((S < 60) & (V > 110) & (V < 225) & (sd > 7))[40:]))
def una(arg):
    nombre, rel = arg
    D = os.path.join(BASE, rel); r = list(csv.DictReader(open(os.path.join(D, 'cuadros.csv'))))
    s = [puntaje(cv2.imread(os.path.join(D, 'f_%06d.png' % int(x['n'])))) for x in r]
    return nombre, rel, [(int(x['n']), float(x['t']), x['quien'], x['rampa'], v) for x, v in zip(r, s)]
if __name__ == '__main__':
    with ProcessPoolExecutor(9) as ex:
        res = list(ex.map(una, RUNS))
    json.dump(res, open('fondo_vuelta.json', 'w'))
    print('listo', sum(len(x[2]) for x in res))
