from pathlib import Path
import textwrap
import cv2
import numpy as np
import pandas as pd
from verde_oscuro import detectar_verde_oscuro

B = Path(__file__).resolve().parent
D = B.parents[1] / 'corridas/20261031_195318/crudo_20261031_195318/1031_195426'

def cargar_detector(path, area):
    src = path.read_text(encoding='utf-8')
    start = src.index('            if np.sum(green_mask) > min_square_size * 255:')
    end = src.index('            if (not RECUP) and np.sum(black_mask) < min_line_size:', start)
    block = textwrap.dedent(src[start:end])
    code = 'def detector(frame_resized):\n'
    code += '    lab = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)\n'
    code += '    black_mask = cv2.inRange(frame_resized, np.array([0,0,0]), np.array([90,90,90])); black_mask[:60] = 0\n'
    code += '    green_mask = np.zeros((120,160),dtype=np.uint8); green_mask[80:] = cv2.inRange(lab[80:],lower_green,upper_green)\n'
    code += '    green_state = 0; kernel = np.ones((3,3),dtype=np.uint8)\n'
    code += textwrap.indent(block, '    ')
    code += '\n    return green_state\n'
    env = dict(cv2=cv2, np=np, lower_green=np.array([120,90,110]), upper_green=np.array([198,109,134]),
               min_square_size=area, FACTOR_DOBLE=1.0, ENABLE_CX_BLACK_GUARD=True,
               detectar_verde_oscuro=detectar_verde_oscuro)
    exec(compile(code, str(path), 'exec'),env)
    return env['detector']

original = cargar_detector(B/'main_actual_rpi.py',600)
actual = cargar_detector(B/'main_actual_rpi.py',200)
nuevo = cargar_detector(B/'main.py',200)
f = pd.read_csv(D/'cuadros.csv')
rows = []
for r in f.itertuples():
    im = cv2.imread(str(D/f'f_{r.n:06d}.png'))
    a,b,c = original(im), actual(im), nuevo(im)
    rows.append((r.n,r.green_state,a,b,c))
p = pd.DataFrame(rows,columns=['frame','grabado','base600','actual200','nuevo200'])
p.to_csv(B/'validacion_7927_cuadros.csv',index=False)
assert len(p)==7927
assert (p.loc[p.grabado.isin([1,2,3]),'base600'].to_numpy()==p.loc[p.grabado.isin([1,2,3]),'grabado'].to_numpy()).all()
assert (p.loc[p.actual200.ne(0),'actual200'].to_numpy()==p.loc[p.actual200.ne(0),'nuevo200'].to_numpy()).all()
assert (p.loc[p.base600.ne(0),'base600'].to_numpy()==p.loc[p.base600.ne(0),'nuevo200'].to_numpy()).all()
for a,b in [(250,290),(1568,1589),(5692,5740),(6820,6845),(1139,1149),(6574,6583)]:
    assert p.loc[p.frame.between(a,b),'nuevo200'].eq(0).all(),(a,b)
for n in [1135,1266,6569]:
    assert p.loc[p.frame.eq(n),'nuevo200'].item()==1,n
assert p.loc[p.frame.eq(1444),'nuevo200'].item()==1
assert p.loc[p.frame.eq(6698),'nuevo200'].item()==1
changes=p[p.actual200.ne(p.nuevo200)]
print('OK: 7927 cuadros; conservadas las 102 detecciones grabadas y todas las detecciones de la base actual200.')
print('OK: cuatro derechos posteriores rechazados; izquierdos 1135/1266/6569 reconocidos; verdes aislados conservados.')
print('Cambios respecto de la Raspberry actual:')
print(changes.to_string(index=False))
