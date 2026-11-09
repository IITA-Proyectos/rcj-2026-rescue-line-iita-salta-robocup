from pathlib import Path
import sys,textwrap,cv2,numpy as np,pandas as pd,json
B=Path(__file__).resolve().parent;D=B/'crudo_rampa_transicion_20261101_111110/1101_111120';O=B/'analisis_verdes';O.mkdir(exist_ok=True);sys.path.insert(0,str(B));from verde_oscuro import detectar_verde_oscuro
s=(B/'main.py').read_text();a=s.index('            if np.sum(green_mask) > min_square_size * 255:');z=s.index('            if (not RECUP) and np.sum(black_mask) < min_line_size:',a);block=textwrap.dedent(s[a:z]);block=block[:block.index('# Respaldo oscuro:')]
code='def det(frame_resized,lab,black_mask,lower_green,upper_green,min_square_size):\n    green_mask=np.zeros((120,160),np.uint8);green_mask[80:]=cv2.inRange(lab[80:],lower_green,upper_green)\n    green_state=0; kernel=np.ones((3,3),np.uint8)\n'+textwrap.indent(block,'    ')+'\n    return green_state\n';env=dict(cv2=cv2,np=np,FACTOR_DOBLE=1.0,ENABLE_CX_BLACK_GUARD=True);exec(code,env);det=env['det']

f=pd.read_csv(B/'cuadros.csv');rows=[]
for r in f.itertuples():
 im=cv2.imread(str(D/f'f_{r.n:06d}.png'));lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB);black=cv2.inRange(im,np.array([0]*3),np.array([90]*3));black[:60]=0
 low=np.array([120,90,110]);high=np.array([198,109,134]);base=det(im,lab,black,low,high,200)
 if not base:base=detectar_verde_oscuro(lab,black,low,high,200,1.)[0]
 g60=det(im,lab,black,np.array([60,90,110]),np.array([198,111,137]),600)
 g70=det(im,lab,black,np.array([70,90,110]),np.array([198,111,137]),600)
 rows.append(dict(n=r.n,gs=r.green_state,base=base,lo60=g60,lo70=g70))
p=pd.DataFrame(rows);p.to_csv(O/'comparacion_sombra.csv',index=False)
ix=p.index[p.base.eq(0)&p.lo60.ne(0)].to_numpy();groups=[g for g in np.split(ix,np.where(np.diff(ix)>15)[0]+1) if len(g)];cards=[];out=[]
for i,g in enumerate(groups,1):
 q=p.loc[g];ns=np.linspace(max(1,int(q.n.min())-3),min(len(f),int(q.n.max())+3),8).astype(int).tolist();cards.append((i,ns));out.append(dict(id=i,start=int(q.n.min()),end=int(q.n.max()),avi=(q.n.min()-1)/20,values=','.join(map(str,q.lo60.unique())),count=len(q)))
for page in range((len(cards)+5)//6):
 chunk=cards[page*6:page*6+6];canvas=np.full((len(chunk)*150,1280,3),245,np.uint8)
 for i,(ident,ns) in enumerate(chunk):
  for j,n in enumerate(ns):
   r=p.iloc[n-1];im=cv2.imread(str(D/f'f_{n:06d}.png'));x=j*160;y=i*150;canvas[y:y+120,x:x+160]=im;cv2.putText(canvas,f'N{ident} f{n} {(n-1)/20:.2f}',(x+1,y+132),0,.29,(0,0,0),1);cv2.putText(canvas,f'base{r.base} L60:{r.lo60} L70:{r.lo70} G{r.gs}',(x+1,y+145),0,.28,(0,0,0),1)
 cv2.imwrite(str(O/f'sombra_{page+1:02d}.jpg'),canvas)
pd.DataFrame(out).to_csv(O/'nuevos_sombra.csv',index=False);print(pd.DataFrame(out).to_string(index=False))
