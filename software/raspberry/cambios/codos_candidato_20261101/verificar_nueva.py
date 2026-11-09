from pathlib import Path
import ast,sys,csv,contextlib,io
import cv2,numpy as np,pandas as pd
B=Path(__file__).resolve().parent; R=B.parents[1]/'corridas'; N=R/'20261031_221132';D=N/'crudo_reenganche_20261031_221132/1031_221136'
sys.path.insert(0,str(R/'20261031_210305/programas_rpi'))
from recuperacion_guard import RecoveryGuard
import importlib.util
spec=importlib.util.spec_from_file_location('previous',B.parent/'reenganche_cierre_20261031/recuperacion_guard.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous);Old=previous.RecoveryGuard
E=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in ast.parse((B/'main.py').read_text()).body:
 if isinstance(node,ast.FunctionDef) and node.name=='_solo_mi_linea':exec(compile(ast.Module(body=[node],type_ignores=[]),'real','exec'),E)
def masks(n):
 im=cv2.imread(str(D/f'f_{n:06d}.png'));m=cv2.inRange(im,np.array([0]*3),np.array([90]*3));m[:60]=0;return E['_solo_mi_linea'](m),m
F=pd.read_csv(D/'cuadros.csv').set_index('n');eps=pd.read_csv(N/'analisis/episodios_69.csv');out=[]
for e in eps.itertuples():
 if e.kind!='CURVA':continue
 g=RecoveryGuard();o=Old();evidence=ast.literal_eval(e.evidence.split('evidencia=')[1]);g.evidence=evidence;o.evidence=evidence
 for n in range(e.start,e.end+1):
  if abs(F.loc[n].angle)>10:g.remember_fragment(masks(n)[1],F.loc[n].t);o.remember_fragment(masks(n)[1],F.loc[n].t)
 t0=F.loc[e.end+1].t;g.begin_finish(-np.sign(e.angle),t0);o.begin_finish(-np.sign(e.angle),t0)
 diff=None
 with contextlib.redirect_stdout(io.StringIO()):
  for n in range(e.end+1,e.last+1):
   row=F.loc[n];mm,full=masks(n);a=o.finish(row.t,mm,full,row.angle);b=g.finish(row.t,mm,full,row.angle)
   if a!=b:diff=(n,a,b);break
 out.append(dict(id=e.id,observed='new_trial',changed=bool(diff),first_difference=str(diff)))
q=pd.DataFrame(out);q.to_csv(B/'replay_69.csv',index=False)
print(q.to_string(index=False))
print('CHANGES',q[q.changed].id.tolist());assert q[q.changed].id.tolist()==[5,29],q[q.changed].id.tolist()

