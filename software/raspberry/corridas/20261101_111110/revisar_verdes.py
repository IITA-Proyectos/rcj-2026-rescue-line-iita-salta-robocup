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
 nl=np.array([80,90,111]);nh=np.array([162,111,137]);p200=det(im,lab,black,nl,nh,200);p600=det(im,lab,black,nl,nh,600)
 hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV);wide=cv2.inRange(hsv,np.array([32,45,25]),np.array([100,255,255]));wide[:55]=0
 ys,xs=np.nonzero(wide);area=len(xs);newmask=cv2.inRange(lab[80:],nl,nh)
 rows.append(dict(n=r.n,t=r.t,gs=r.green_state,base=base,suggest200=p200,suggest600=p600,wide=area,proposed_px=int(np.count_nonzero(newmask)),quien=r.quien))
p=pd.DataFrame(rows);p.to_csv(O/'replay.csv',index=False)
ix=p.index[(p.wide>=120)|p.base.ne(0)|p.suggest200.ne(0)].to_numpy();groups=[g for g in np.split(ix,np.where(np.diff(ix)>20)[0]+1) if len(g)]
summary=[];cards=[]
for i,g in enumerate(groups,1):
 q=p.loc[g];start,end=int(q.n.min()),int(q.n.max());ns=np.linspace(max(1,start-5),min(len(f),end+5),8).astype(int).tolist();cards.append(dict(id=i,frames=ns));summary.append(dict(id=i,start=start,end=end,avi=(start-1)/20,wide_max=int(q.wide.max()),base=int((q.base!=0).sum()),s200=int((q.suggest200!=0).sum()),s600=int((q.suggest600!=0).sum()),gs=','.join(map(str,sorted(q.gs.unique())))))
pd.DataFrame(summary).to_csv(O/'encuentros.csv',index=False);(O/'tarjetas.json').write_text(json.dumps(cards))
for page in range((len(cards)+5)//6):
 chunk=cards[page*6:page*6+6];canvas=np.full((len(chunk)*150,1280,3),245,np.uint8)
 for i,c in enumerate(chunk):
  for j,n in enumerate(c['frames']):
   r=p.iloc[n-1];im=cv2.imread(str(D/f'f_{n:06d}.png'));x=j*160;y=i*150;canvas[y:y+120,x:x+160]=im
   cv2.putText(canvas,f'E{c["id"]} f{n} {(n-1)/20:.1f} G{r.gs}',(x+1,y+132),0,.29,(0,0,0),1);cv2.putText(canvas,f'base{r.base} nuevo{r.suggest600} px{r.proposed_px}',(x+1,y+145),0,.28,(0,0,0),1)
 cv2.imwrite(str(O/f'verdes_{page+1:02d}.jpg'),canvas)
print(pd.DataFrame(summary).to_string(index=False));print('positivos base',sum(p.base!=0),'nuevos600',sum((p.base==0)&(p.suggest600!=0)))

