import csv, glob, os, sys
RUNS = [
 ('31-oct 19:53', '20261031_195318', 'crudo_20261031_195318/1031_195426', 'pista_20261031_195318.avi'),
 ('31-oct 21:03', '20261031_210305', 'crudo_pista_completa_20261031_210305/1031_210325', 'pista_pista_completa_20261031_210305.avi'),
 ('31-oct 21:36', '20261031_213650', 'crudo_recuperacion_corregida_20261031_213650/1031_213701', 'pista_recuperacion_corregida_20261031_213650.avi'),
 ('31-oct 22:11', '20261031_221132', 'crudo_reenganche_20261031_221132/1031_221136', 'pista_reenganche_20261031_221132.avi'),
 ('1-nov 10:31', '20261101_103155', 'crudo_cierre3_20261101_103155/1101_103200', 'pista_cierre3_20261101_103155.avi'),
 ('1-nov 11:11', '20261101_111110', 'crudo_rampa_transicion_20261101_111110/1101_111120', 'pista_rampa_transicion_20261101_111110.avi'),
 ('1-nov 11:47', '20261101_114747', 'crudo_verde_sombra_20261101_114747/1101_114752', 'pista_verde_sombra_20261101_114747.avi'),
 ('1-nov 12:38', '20261101_124912', 'crudo_doble_dato_20261101_123804/1101_123809', 'pista_doble_dato_20261101_123804.avi'),
 ('1-nov 12:49', '20261101_124912', 'crudo_doble_dato_20261101_124912/1101_124926', 'pista_doble_dato_20261101_124912.avi'),
 ('1-nov 13:54', '20261101_135438', 'crudo', 'pista_giro_cresta_20261101_135438.avi'),
 ('1-nov 14:09', '20261101_140905', 'crudo', 'pista_cresta_verde_20261101_140905.avi'),
]
def mmss(n): return '%d:%05.2f' % (n / 20 // 60, n / 20 % 60)
def main():
    out = []
    for nombre, run, cr, vid in RUNS:
        r = list(csv.DictReader(open(os.path.join(run, cr, 'cuadros.csv'))))
        N = len(r)
        # tramos de bajada (rampa -1), uniendo huecos de hasta 30 cuadros
        tr = []; cur = None
        for i, x in enumerate(r):
            if x['rampa'] == '-1':
                if cur and i <= cur[1] + 30: cur[1] = i
                else: cur = [i, i]; tr.append(cur)
        print('=== %s (%s) %d cuadros, %d bajadas' % (nombre, vid, N, len(tr)))
        for a, b in tr:
            # contexto: 40 cuadros antes y 120 despues
            lo, hi = max(0, a - 40), min(N - 1, b + 120)
            verdes = []; prev = '0'
            for i in range(lo, hi + 1):
                g = r[i]['green_state']
                if g in ('1', '2', '3') and prev not in ('1', '2', '3'):
                    verdes.append('%s@%s(r%s)' % ({'1': 'IZQ', '2': 'DER', '3': 'DOBLE'}[g], mmss(int(r[i]['n'])), r[i]['rampa']))
                prev = g
            saltos = [mmss(int(r[i]['n'])) for i in range(lo + 1, hi + 1) if float(r[i]['t']) - float(r[i - 1]['t']) > 1.0]
            gs4 = sorted({mmss(int(r[i]['n'])) for i in range(lo, hi + 1) if r[i]['green_state'] in ('4', '18', '19') and r[i - 1]['green_state'] not in ('4', '18', '19')})
            dur = float(r[b]['t']) - float(r[a]['t'])
            print('  bajada %s-%s (%.1f s)  verdes %s  recup/gap %s  SALTO(reubicado) %s' % (
                mmss(int(r[a]['n'])), mmss(int(r[b]['n'])), dur, verdes or '-', gs4 or '-', saltos or '-'))
if __name__ == "__main__":
    main()
