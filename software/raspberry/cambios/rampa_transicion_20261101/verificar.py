from pathlib import Path
import ast,sys,cv2,numpy as np,pandas as pd
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B));from rampa_transicion import RampTransition
R=B.parents[1]/'corridas';env=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in ast.parse((B/'main_base.py').read_text()).body:
 if isinstance(node,ast.FunctionDef) and node.name=='_solo_mi_linea':exec(compile(ast.Module(body=[node],type_ignores=[]),'real','exec'),env)
rows=[]
for run,folder in [('20261101_103155','crudo_cierre3_20261101_103155/1101_103200'),('20261031_221132','crudo_reenganche_20261031_221132/1031_221136'),('20261031_213650','crudo_recuperacion_corregida_20261031_213650/1031_213701')]:
 d=R/run/folder;f=pd.read_csv(d/'cuadros.csv');guard=RampTransition();changed=[]
 for r in f.itertuples():
  if r.rampa!=1 and not guard.armed:continue
  im=cv2.imread(str(d/f'f_{r.n:06d}.png'));mask=cv2.inRange(im,np.array([0]*3),np.array([90]*3));mask[:60]=0;mm=env['_solo_mi_linea'](mask)
  result=guard.step(r.rampa==1,r.quien,mm,r.t)
  if result:
   assert r.rampa==1 and r.quien=='rampa-linea'
   assert abs(result['angle'])<=15
   changed.append(r.n);rows.append(dict(run=run,n=r.n,old=r.angle,new=result['angle'],who=result['who']))
  if r.green_state in [1,2,3,19]:guard.reset()
 if run=='20261101_103155':
  for a,b in [(587,700),(6872,6993)]:assert not any(a<=n<=b for n in changed)
  for a,b in [(788,921),(1073,1293),(1377,1526),(1786,1936)]:assert any(a<=n<=b for n in changed)
 print(run,'cuadros',len(f),'cambios',len(changed),'primeros',changed[:4])
pd.DataFrame(rows).to_csv(B/'replay_cambios.csv',index=False)
# Geometria y alcance: no actuar sin recta previa, no invadir modos de cresta.
mask=np.zeros((120,160),np.uint8);mask[60:,75:85]=255;g=RampTransition()
assert g.step(True,'rampa-linea',mask,0) is None
for i in range(20):assert g.step(True,'rampa-recta',mask,.03*i) is None
for who in ['rampa-cresta-recto','rampa-centra80','rampa-corta-recto']:assert g.step(True,who,mask,.61) is None
assert abs(g.step(True,'rampa-linea',mask,.65)['angle'])<=15
assert g.step(False,'centroide',mask,.7) is None
assert g.step(True,'rampa-linea',mask,.75) is None
s=(B/'main.py').read_text();base=(B/'main_base.py').read_text();a='            if np.sum(green_mask) > min_square_size * 255:';z='            if (not RECUP) and np.sum(black_mask) < min_line_size:'
assert s[s.index(a):s.index(z)]==base[base.index(a):base.index(z)]
print('OK: entrada recta, cresta, bajada, verdes y controles cortos de subida conservados; cambios solo fallback armado.')
