from pathlib import Path
import ast,sys,csv,contextlib,io
import cv2,numpy as np,pandas as pd
B=Path(__file__).resolve().parent; R=B.parents[1]/'corridas'; N=R/'20261031_213650';D=N/'crudo_recuperacion_corregida_20261031_213650/1031_213701'
sys.path.insert(0,str(R/'20261031_210305/programas_rpi'))
from recuperacion_guard import RecoveryGuard
from recuperacion_guard_base import RecoveryGuard as Old
E=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in ast.parse((B/'main_base.py').read_text()).body:
 if isinstance(node,ast.FunctionDef) and node.name=='_solo_mi_linea':exec(compile(ast.Module(body=[node],type_ignores=[]),'real','exec'),E)
def masks(n):
 im=cv2.imread(str(D/f'f_{n:06d}.png'));m=cv2.inRange(im,np.array([0]*3),np.array([90]*3));m[:60]=0;return E['_solo_mi_linea'](m),m
F=pd.read_csv(D/'cuadros.csv').set_index('n');eps=pd.read_csv(N/'analisis/inventario_final.csv');out=[]
for e in eps.itertuples():
 if e.kind!='CURVA':continue
 g=RecoveryGuard();o=Old();evidence=ast.literal_eval(e.evidence.split('evidencia=')[1]);g.evidence=evidence;o.evidence=evidence
 for n in range(e.start,e.end+1):
  if abs(F.loc[n].angle)>10:g.remember_fragment(masks(n)[1],F.loc[n].t)
 t0=F.loc[e.end+1].t;g.begin_finish(-np.sign(e.angle),t0);o.begin_finish(-np.sign(e.angle),t0)
 diff=None
 with contextlib.redirect_stdout(io.StringIO()):
  for n in range(e.end+1,e.last+1):
   row=F.loc[n];mm,full=masks(n);a=o.finish(row.t,mm,full,row.angle);b=g.finish(row.t,mm,full,row.angle)
   if a!=b:diff=(n,a,b);break
 out.append(dict(id=e.id,observed=e.clasificacion,changed=bool(diff),first_difference=str(diff)))
q=pd.DataFrame(out);q.to_csv(B/'replay_69.csv',index=False)
print(q.to_string(index=False))
print('CHANGES',q[q.changed].id.tolist());print('GOOD CHANGED',q[q.changed & q.observed.eq('recaptura_visible')].id.tolist())

assert q[q.changed].id.tolist()==[4,18,39,40,41,48,50,66,67,68,69]
assert not q[q.observed.eq('recaptura_visible')].changed.any()
# No se modifican ni decisiones, ni verdes, ni el cierre anterior: solo se envuelve su STOP.
a=ast.parse((B/'recuperacion_guard.py').read_text());z=ast.parse((B/'recuperacion_guard_base.py').read_text())
def method(tree,name):
 return next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
assert ast.dump(method(a,'decide'))==ast.dump(method(z,'decide'))
old=method(z,'finish');old.name='_legacy_finish'
assert ast.dump(method(a,'_legacy_finish'))==ast.dump(old)
s=(B/'main.py').read_text();base=(B/'main_base.py').read_text()
start='            if np.sum(green_mask) > min_square_size * 255:';end='            if (not RECUP) and np.sum(black_mask) < min_line_size:'
assert s[s.index(start):s.index(end)]==base[base.index(start):base.index(end)]
# Otros once cierres correctos de la corrida previa.
P=R/'20261031_210305';dd=P/'crudo_pista_completa_20261031_210305/1031_210325'
f=pd.read_csv(dd/'cuadros.csv').set_index('n');ep=pd.read_csv(P/'analisis_recuperaciones/episodios_cruzados.csv')
for ident in [2,3,5,6,9,12,14,18,19,21,24]:
 e=ep[ep.id.eq(ident)].iloc[0];g=RecoveryGuard();o=Old();t0=f.loc[e.end+1].t
 g.begin_finish(-np.sign(e.angle),t0);o.begin_finish(-np.sign(e.angle),t0)
 for row in f[(f.index>e.end)&(f.t<=t0+1.5)].itertuples():
  im=cv2.imread(str(dd/f'f_{row.Index:06d}.png'));full=cv2.inRange(im,np.array([0]*3),np.array([90]*3));full[:60]=0;mm=E['_solo_mi_linea'](full)
  assert g.finish(row.t,mm,full,row.angle)==o.finish(row.t,mm,full,row.angle),ident
print('OK: 11 codos aislados; exitos y GAP conservados; otros 11 cierres correctos conservados; decisiones y verdes identicos.')
