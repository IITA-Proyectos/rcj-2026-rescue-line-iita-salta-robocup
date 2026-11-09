"""Reproduce cuadros PNG reales. Nunca importa ni ejecuta el programa del robot."""
from pathlib import Path
import argparse
import csv
import json
import time
import cv2
from silver_mask import SilverShadow, VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--step', type=int, default=1)
    parser.add_argument('--run', default='20261101_124912')
    args = parser.parse_args()
    if args.step < 1:
        parser.error('--step debe ser positivo')
    base = Path(__file__).resolve().parent
    runs = base.parents[1] / 'corridas'
    if args.run == '20261101_124912':
        folder = runs / args.run / 'crudo_doble_dato_20261101_124912/1101_124926'
        cases = json.loads((runs / args.run / 'analisis_plateados_total/casos.json').read_text())[:8]
    elif args.run == '20261101_123804':
        folder = next((runs / '20261101_124912/crudo_doble_dato_20261101_123804').glob('*'))
        cases = [dict(id='P09a', start=4757, end=4912),
                 dict(id='P09b', start=4913, end=5054)]
    else:
        parser.error('Solo corridas con PNG originales disponibles')
    with (folder / 'cuadros.csv').open(newline='') as source:
        frames = list(csv.DictReader(source))
    guard = SilverShadow()
    output = base / f'replay_{args.run}_paso{args.step}_{VERSION}.csv'
    started = time.perf_counter()
    count = 0
    with output.open('w', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=['n', 't', 'gs', 'rampa', 'case_window',
                                'candidate', 'stable', 'slope', 'score', 'occupancy'])
        writer.writeheader()
        for r in frames[::args.step]:
            n, now = int(r['n']), float(r['t'])
            im = cv2.imread(str(folder / f'f_{n:06d}.png'))
            if im is None:
                raise RuntimeError(f'Falta PNG original {n}')
            result = guard.step(im, now)
            candidate = result['candidate']
            label = next((e['id'] for e in cases if e['start'] <= n <= e['end']), '')
            writer.writerow(dict(n=n, t=now, gs=r['green_state'], rampa=r['rampa'],
                                 case_window=label, candidate=int(candidate is not None),
                                 stable=int(result['stable']), slope=result['slope'],
                                 score=candidate['score'] if candidate else '',
                                 occupancy=candidate['occupancy'] if candidate else ''))
            count += 1
            if count % 2000 == 0:
                print(f'{args.run}: {count} cuadros, {time.perf_counter()-started:.1f}s', flush=True)
    print(f'Listo: {count} cuadros en {time.perf_counter()-started:.1f}s -> {output}', flush=True)


if __name__ == '__main__':
    main()
