from pathlib import Path
import ast,cv2,numpy as np,pandas as pd,json,hashlib
B=Path('raspberry/corridas/20261031_221132');D=B/'crudo_reenganche_20261031_221132/1031_221136';O=B/'analisis_exhaustivo';O.mkdir(exist_ok=True)
f=pd.read_csv(B/'cuadros.csv');f['session']=(f.t.diff()>1).cumsum();eps=pd.read_csv(B/'analisis/episodios_69.csv');env=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in ast.parse((B/'main.py').read_text()).body:
 if isinstance(node,ast.FunctionDef) and node.name=='_solo_mi_linea':exec(compile(ast.Module(body=[node],type_ignores=[]),'real','exec'),env)
metrics=[];segments=[];pages=[];inventory=[]
for e in eps.itertuples():
 nextn=int(eps[eps.id.eq(e.id+1)].start.iloc[0]) if e.id<len(eps) else len(f)+1
 z=f[(f.n>=max(1,e.start-10))&(f.n<nextn)&(f.session==e.session)&(f.t<=float(f.loc[f.n.eq(e.end),'t'].iloc[0])+5)]
 groups=z.groupby((z.quien.ne(z.quien.shift())|z.green_state.ne(z.green_state.shift())).cumsum())
 for _,g in groups:segments.append(dict(id=e.id,start=int(g.n.iloc[0]),end=int(g.n.iloc[-1]),avi=(g.n.iloc[0]-1)/20,gs=int(g.green_state.iloc[0]),quien=g.quien.iloc[0],duration=g.t.iloc[-1]-g.t.iloc[0],angle_first=g.angle.iloc[0],angle_last=g.angle.iloc[-1]))
 transitions=set(z.loc[z.quien.ne(z.quien.shift())|z.green_state.ne(z.green_state.shift()),'n'])
 ns=[int(n) for j,n in enumerate(z.n) if j%2==0 or n in transitions]
 for row in z.itertuples():
  im=cv2.imread(str(D/f'f_{row.n:06d}.png'));m=cv2.inRange(im,np.array([0]*3),np.array([90]*3));m[:60]=0;mm=env['_solo_mi_linea'](m);geo=[]
  for a,b in [(100,120),(60,80)]:
   xs=np.nonzero(mm[a:b])[1];geo.append((np.median(xs)-79.5)/80 if len(xs)>=20 else np.nan)
  metrics.append(dict(id=e.id,n=row.n,t=row.t,gs=row.green_state,quien=row.quien,angle=row.angle,connected=int(np.count_nonzero(mm)),near=geo[0],heading=geo[1]-geo[0]))
 for page in range((len(ns)+63)//64):
  chunk=ns[page*64:page*64+64];canvas=np.full((((len(chunk)+7)//8)*148,1280,3),245,np.uint8)
  for j,n in enumerate(chunk):
   r=f.iloc[n-1];im=cv2.imread(str(D/f'f_{n:06d}.png'));x=(j%8)*160;y=(j//8)*148;canvas[y:y+120,x:x+160]=im
   cv2.putText(canvas,f'f{n} {(n-1)/20:.2f} G{r.green_state} a{r.angle:.0f}',(x+1,y+131),0,.29,(0,0,0),1)
   cv2.putText(canvas,str(r.quien).replace('recup-','r-')[:26],(x+1,y+144),0,.28,(0,0,0),1)
  name=f'E{e.id:02d}_{page+1}.jpg';cv2.imwrite(str(O/name),canvas,[cv2.IMWRITE_JPEG_QUALITY,94]);pages.append(name)
 inventory.append(dict(id=e.id,first=int(z.n.iloc[0]),last=int(z.n.iloc[-1]),frames=len(z),shown=len(ns),pages=(len(ns)+63)//64))
pd.DataFrame(metrics).to_csv(O/'metricas_todos_cuadros.csv',index=False);pd.DataFrame(segments).to_csv(O/'todas_acciones.csv',index=False);pd.DataFrame(inventory).to_csv(O/'inventario.csv',index=False);(O/'paginas.json').write_text(json.dumps(pages));print('frames',len(metrics),'shown',sum(r['shown'] for r in inventory),'pages',len(pages));print(pd.DataFrame(inventory).to_string(index=False))
