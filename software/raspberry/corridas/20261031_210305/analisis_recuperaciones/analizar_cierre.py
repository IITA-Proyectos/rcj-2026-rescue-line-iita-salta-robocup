from pathlib import Path
import ast,sys
import pandas as pd,numpy as np,cv2
B=Path(__file__).resolve().parent;D=B.parent/'crudo_pista_completa_20261031_210305/1031_210325'
sys.path.insert(0,str(B.parent/'programas_rpi'))
from completar_giro import forma_cinta
tree=ast.parse((B.parent/'programas_rpi/main.py').read_text());env=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and node.name in ['_solo_mi_linea','_error_lateral','_forma_recta']:
  exec(compile(ast.Module(body=[node],type_ignores=[]),'funciones_extraidas','exec'),env)
f=pd.read_csv(D/'cuadros.csv');p=pd.read_csv(B/'episodios_cruzados.csv');c=pd.read_pickle(B/'teensy.pkl');off=31.3;rows=[];details=[]
for e in p.itertuples():
 next_ep=p[p.start>e.end];limit=next_ep.t.iloc[0] if len(next_ep) else float('inf');q=f[(f.t>f.iloc[e.end-1].t)&(f.t<=min(f.iloc[e.end-1].t+1.5,limit))].copy()
 # End at an interruption in raw recording rather than mixing in a repositioned robot.
 breaks=q.index[q.t.diff()>1]
 if len(breaks):q=q.loc[q.index<breaks[0]]
 states=[]
 for r in q.itertuples():
  im=cv2.imread(str(D/f'f_{r.n:06d}.png'));mask=cv2.inRange(im,np.array([0,0,0]),np.array([90,90,90]));mask[:60]=0;mm=env['_solo_mi_linea'](mask);err=env['_error_lateral'](mm,100,120)
  if err is None:err=env['_error_lateral'](mm,60,120)
  ok=err is not None;shape=forma_cinta(mm,ok);states.append((r.n,r.t,ok,shape,r.quien,r.angle));details.append((e.id,r.n,r.t,ok,shape,r.quien,r.angle))
 s=pd.DataFrame(states,columns=['n','t','ok','shape','quien','angle'])
 row=dict(id=e.id,start=e.start,avi_s=e.avi_s,decision=e.decision,target=(max(35,min(58,28+.15*abs(e.pivot_rx))) if np.isfinite(e.pivot_rx) else None),measured_yaw=e.yaw,measured_gyro=e.gyro,post_frames=len(s))
 if len(s):
  row.update(post_no_connected=int((~s.ok).sum()),post_missing_fraction=round(float((~s.ok).mean()),3),post_cooldown=int(s.quien.eq('recup-cooldown-recto').sum()),post_empty=int(s.quien.eq('v66-bloqueo-mascara-vacia-recto').sum()),post_CG=int(s.quien.eq('recup-completa-giro').sum()),shapes=''.join(s['shape'].tolist()),last_frame=int(s.n.iloc[-1]),last_connected=bool(s.ok.iloc[-1]))
 rows.append(row)
pd.DataFrame(details,columns=['episode','n','t','connected','shape','quien','angle']).to_csv(B/'post_recuperacion_frames.csv',index=False)
r=pd.DataFrame(rows);r.to_csv(B/'cierre_recuperaciones.csv',index=False);print(r[r.id<=25].to_string(index=False))
