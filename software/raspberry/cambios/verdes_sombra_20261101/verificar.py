from pathlib import Path
import sys,textwrap,cv2,numpy as np,pandas as pd,json
B=Path(__file__).resolve().parent;O=B;sys.path.insert(0,str(B));from verde_oscuro import detectar_verde_oscuro, detectar_verde_sombra
s=(B/'main_base.py').read_text();a=s.index('            if np.sum(green_mask) > min_square_size * 255:');z=s.index('            if (not RECUP) and np.sum(black_mask) < min_line_size:',a);block=textwrap.dedent(s[a:z]);block=block[:block.index('# Respaldo oscuro:')]
code='def det(frame_resized,lab,black_mask,lower_green,upper_green,min_square_size):\n    green_mask=np.zeros((120,160),np.uint8);green_mask[80:]=cv2.inRange(lab[80:],lower_green,upper_green)\n    green_state=0; kernel=np.ones((3,3),np.uint8)\n'+textwrap.indent(block,'    ')+'\n    return green_state\n';env=dict(cv2=cv2,np=np,FACTOR_DOBLE=1.0,ENABLE_CX_BLACK_GUARD=True);exec(code,env);det=env['det']

R=B.parents[1]/'corridas';allrows=[]
runs=[('20261101_111110','crudo_rampa_transicion_20261101_111110/1101_111120'),('20261031_195318','crudo_20261031_195318/1031_195426'),('20261101_103155','crudo_cierre3_20261101_103155/1101_103200'),('20261031_221132','crudo_reenganche_20261031_221132/1031_221136'),('20261031_213650','crudo_recuperacion_corregida_20261031_213650/1031_213701'),('20261031_210305','crudo_pista_completa_20261031_210305/1031_210325')]
for run,folder in runs:
 D=R/run/folder;f=pd.read_csv(D/'cuadros.csv');rows=[]
 for r in f.itertuples():
  im=cv2.imread(str(D/f'f_{r.n:06d}.png'));lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB);black=cv2.inRange(im,np.array([0]*3),np.array([90]*3));black[:60]=0;lo=np.array([120,90,110]);hi=np.array([198,109,134]);old=det(im,lab,black,lo,hi,200)
  if not old:old=detectar_verde_oscuro(lab,black,lo,hi,200,1.)[0]
  extra=0 if old else detectar_verde_sombra(lab,black,lo,hi,200,1.)[0];new=old or extra
  assert not old or old==new
  rows.append(dict(run=run,n=r.n,old=old,new=new,extra=extra,recorded=r.green_state))
 p=pd.DataFrame(rows);p.to_csv(B/f'replay_{run}.csv',index=False);allrows.extend(rows)
 if run=='20261031_195318':
  for a,z in [(250,290),(1568,1589),(5692,5740),(6820,6845),(1139,1149),(6574,6583)]:assert p[p.n.between(a,z)].new.eq(0).all(),(a,z,p[p.n.between(a,z)&p.new.ne(0)].to_dict('records'))
 if run=='20261101_111110':
  for a,z in [(130,135),(1336,1339),(1469,1473),(11289,11295),(11418,11421)]:assert p[p.n.between(a,z)].new.eq(1).any(),(a,z)
  assert p[p.n.between(7702,7710)].new.eq(2).all()
  assert not p[p.n.between(12152,12165)].new.eq(3).any()
 print(run,'frames',len(p),'positivos conservados',sum(p.old.ne(0)),'cuadros nuevos',sum(p.extra.ne(0)),flush=True)
pd.DataFrame(allrows).to_csv(B/'replay_total.csv',index=False)
print('OK: todos los positivos conservados; falsos derechos de control rechazados; sombras nuevas y doble fragmentado verificados.')
