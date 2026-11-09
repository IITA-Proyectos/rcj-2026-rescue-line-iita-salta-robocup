from pathlib import Path
import cv2,numpy as np,pandas as pd
from doble_dato import DoubleData
B=Path(__file__).resolve().parent;R=B.parents[1]/'corridas';f=pd.read_csv(R/'20261101_114747/cuadros.csv');ev=pd.read_csv(R/'20261101_114747/analisis_doble_plateado/eventos_verdes.csv');g=DoubleData();rows=[];D=R/'20261101_114747/crudo_verde_sombra_20261101_114747/1101_114752'
for r in f.itertuples():
 raw=int(r.green_state);lab=black=None
 if raw in [1,2,3]:
  im=cv2.imread(str(D/f'f_{r.n:06d}.png'));lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB);black=cv2.inRange(im,np.array([0]*3),np.array([90]*3));black[:60]=0
 new=g.step(raw,lab,black,r.t);rows.append(dict(n=r.n,old=raw,new=new))
p=pd.DataFrame(rows);p.to_csv(B/'replay_114747.csv',index=False)
for e in ev.itertuples():
 q=p[p.n.between(e.start,e.end)];q=q[q.old.isin([1,2,3])]
 if e.has3:assert q.new.eq(3).all(),e.id
 else:assert q.old.eq(q.new).all(),e.id
print('OK ultima prueba: 7 dobles GS3 desde el primer aviso; 31 eventos simples conservados.')
folders={'20261101_111110':'crudo_rampa_transicion_20261101_111110/1101_111120','20261031_195318':'crudo_20261031_195318/1031_195426','20261101_103155':'crudo_cierre3_20261101_103155/1101_103200','20261031_221132':'crudo_reenganche_20261031_221132/1031_221136','20261031_213650':'crudo_recuperacion_corregida_20261031_213650/1031_213701','20261031_210305':'crudo_pista_completa_20261031_210305/1031_210325'}
base=pd.read_csv(B.parent/'verdes_sombra_20261101/replay_total.csv');out=[]
for run,z in base.groupby('run'):
 run=str(run);g=DoubleData();meta=pd.read_csv(R/run/folders[run]/'cuadros.csv').set_index('n');rr=[]
 for row in z.itertuples():
  raw=int(row.new);lab=black=None
  if raw:
   im=cv2.imread(str(R/run/folders[run]/f'f_{row.n:06d}.png'));lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB);black=cv2.inRange(im,np.array([0]*3),np.array([90]*3));black[:60]=0
  new=g.step(raw,lab,black,float(meta.loc[row.n].t));rr.append(dict(run=run,n=row.n,old=raw,new=new))
 q=pd.DataFrame(rr);out.extend(rr)
 if run=='20261031_195318':
  for a,b in [(250,290),(1568,1589),(5692,5740),(6820,6845),(1139,1149),(6574,6583)]:assert q[q.n.between(a,b)].new.eq(0).all(),(a,b)
 print(run,'cambios',sum(q.old!=q.new),'simples->doble',sum(q.old.isin([1,2])&q.new.eq(3)),flush=True)
pd.DataFrame(out).to_csv(B/'replay_anteriores.csv',index=False)
