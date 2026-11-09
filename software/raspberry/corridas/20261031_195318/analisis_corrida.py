from pathlib import Path
import pandas as pd, numpy as np, cv2, json
from PIL import Image,ImageDraw
B=Path(__file__).parent; D=B/'crudo_20261031_195318/1031_195426'; O=B/'analisis'; O.mkdir(exist_ok=True)
f=pd.read_csv(D/'cuadros.csv'); c=pd.read_csv(B/'verdes_curvas_1031_195405.csv',comment='#'); c=c[pd.to_numeric(c.us,errors='coerce').notna()].copy(); c=c.apply(pd.to_numeric,errors='coerce')
c=c[c.us.between(3.7e9,4.3e9)].copy()
u=c.us.to_numpy(float); c['sec']=(u-u[0])/1e6
f['gap']=f.t.diff(); f['session']=(f.gap>1).cumsum()
def groups(mask):
 idx=np.flatnonzero(mask); return np.split(idx,np.where(np.diff(idx)>1)[0]+1) if len(idx) else []
events=[]
for kind,mask in [('verde',f.green_state.isin([1,2,3])),('recup',f.green_state.eq(4)),('gap',f.green_state.eq(18)),('verde_visible',f.verde_px.gt(100))]:
 for g in groups(mask):
  a,b=f.iloc[g[0]],f.iloc[g[-1]]; events.append(dict(kind=kind,n=int(a.n),end=int(b.n),t=float(a.t),duration=float(b.t-a.t),gs=int(a.green_state),angle=float(a.angle),maxgreen=int(f.iloc[g].verde_px.max())))
pd.DataFrame(events).to_csv(O/'eventos.csv',index=False)
print('FRAMES',len(f),'CSV',len(c),'time',f.t.min(),f.t.max(),'csvtime',c.sec.max(),'drops',c['drop'].iloc[-1]-c['drop'].iloc[0]); print('GAPS',f.loc[f.gap>1,['n','t','gap']].to_string(index=False)); print('GS',f.green_state.value_counts().to_dict()); print('EVENTS',json.dumps([e for e in events if e['kind']!='verde_visible']))
# Match the actual received steering to Pi command using global offset, excluding constant commands.
ft=f.t.to_numpy(); cmd=np.rint(f.angle.to_numpy())/90*1000
ct=c.sec.to_numpy(); rx=c.rxsteer.to_numpy(); changes=np.r_[False,np.diff(cmd)!=0]; valid=changes & (np.abs(cmd)>20) & (f.green_state.to_numpy()==0)
ts=ft[valid]; vs=cmd[valid]
scores=[]
for offset in np.arange(-60,61,.025):
 ix=np.searchsorted(ct,ts+offset+.025); ok=(ix>0)&(ix<len(ct)); ix=np.clip(ix,0,len(ct)-1)
 err=np.abs(rx[ix[ok]]-vs[ok]); scores.append((np.mean(np.minimum(err,1000)),offset))
best=sorted(scores)[:5]; print('ALIGN',best); offset=best[0][1]; f['csvsec']=f.t+offset
f.to_csv(O/'frames_sincronizados.csv',index=False)
def sheet(name,ns):
 ns=list(dict.fromkeys(int(n) for n in ns if 1<=n<=len(f))); w=800; out=Image.new('RGB',(w, len(ns)//4*175+(175 if len(ns)%4 else 0)),'#eeeeee'); draw=ImageDraw.Draw(out)
 for i,n in enumerate(ns):
  row=f.iloc[n-1]; im=Image.open(D/f'f_{n:06d}.png').resize((200,150)); x=i%4*200;y=i//4*175;out.paste(im,(x,y));draw.text((x,y+150),f'{n} t={row.t:.1f} gs={row.green_state} a={row.angle:.0f} g={row.verde_px}',fill='black')
 out.save(O/name)
stops=[int(n-1) for n in f.loc[f.gap>1,'n'] if n>2]+[len(f)]
sheet('paradas.jpg',[n+d for n in stops for d in [-20,-10,-3,0]])
for i,chunk in enumerate(np.array_split([e for e in events if e['kind']=='verde_visible' and e['maxgreen']>200],3)):
 sheet(f'verdes_{i}.jpg',[e['n']+int((e['end']-e['n'])*r) for e in chunk for r in [0,.33,.66,1]])
sheet('recuperaciones.jpg',[e['n']+d for e in events if e['kind']=='recup' for d in [-5,0,15,35]])
c.to_pickle(O/'teensy.pkl')
checks=[]
for row in f[f.verde_px>100].itertuples():
 im=cv2.imread(str(D/f'f_{row.n:06d}.png')); lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB); gm=cv2.inRange(lab,np.array([120,90,110]),np.array([198,109,134]));gm[:80]=0
 bm=cv2.inRange(im,np.array([0,0,0]),np.array([90,90,90]));bm[:60]=0
 xx=np.flatnonzero(gm.max(axis=0)); l,r=int(xx[0]),int(xx[-1]); m=cv2.moments(bm[90:]);cx=m['m10']/m['m00'] if m['m00'] else None
 density=np.count_nonzero(bm[60:90,l:r+1])/(30*max(1,r-l)); contours,_=cv2.findContours(cv2.dilate(cv2.erode(gm,np.ones((3,3),np.uint8)),np.ones((3,3),np.uint8),iterations=2),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
 checks.append(dict(n=row.n,t=row.t,gs=row.green_state,g=row.verde_px,density=density,cx=cx,l=l,r=r,contours=len(contours),reason='area' if row.verde_px<=600 else 'sin_negro_abajo' if cx is None else 'negro_encima' if density<=.32 else 'aceptado'))
pd.DataFrame(checks).to_csv(O/'verdes_filtros.csv',index=False)
stats=[]
for e in events:
 if e['kind'] not in ['verde','recup']:continue
 a=e['t']+offset; b=a+e['duration']+(2 if e['kind']=='verde' else 1)
 z=c[c.sec.between(a,b)].copy(); y=np.unwrap(z.yaw.to_numpy()/10*np.pi/180)*180/np.pi
 stats.append(dict(**e,csv_start=a,yaw_delta=float(y[-1]-y[0]) if len(y) else None,ramas=','.join(map(str,z.ram.unique())),drop=int(z['drop'].iloc[-1]-z['drop'].iloc[0]) if len(z) else None))
pd.DataFrame(stats).to_csv(O/'maniobras.csv',index=False)
for j,es in enumerate(np.array_split([e for e in events if e['kind']=='recup'],3)):
 sheet(f'recup_{j}.jpg',[e['n']+d for e in es for d in [-10,15,40,60]])
print('VERDE_REASONS',pd.DataFrame(checks).groupby('reason').size().to_dict())
turns=[]
for g in groups((c.ram.eq(13)).to_numpy()):
 z=c.iloc[g]; a,b=z.sec.iloc[0]-offset,z.sec.iloc[-1]-offset; fi=f.iloc[np.argmin(abs(f.t-a))];y=np.unwrap(z.yaw.to_numpy()/10*np.pi/180)*180/np.pi
 turns.append(dict(n=int(fi.n),t=round(a,3),duration=round(b-a,3),rxangle=round(z.rxsteer.median()*.09,1),yaw=round(y[-1]-y[0],1),after=str(f[f.t.between(b,b+.6)].quien.unique())))
pd.DataFrame(turns).to_csv(O/'pivotes_medidos.csv',index=False)
print('PIVOTS',json.dumps(turns))
for a,b in [(270,285),(1137,1149),(1572,1589),(5715,5723),(6574,6583),(6829,6845)]:
 z=pd.DataFrame(checks); print('REJECT',a,z[z.n.between(a,b)][['n','g','density','reason']].to_string(index=False))
sheet('evidencia_principal.jpg',[1577,1693,1694,1708,2808,2828,2840,2862,5378,5397,5405,5425])
# Quantitative evidence remains separate from production code.
st=[]
for nextrow in f[f.gap>1].itertuples():
 if nextrow.n<=2:continue
 r=f.iloc[nextrow.n-2]; prev=[e for e in events if e['kind'] in ['verde','recup','gap'] and e['n']<=r.n]
 st.append(dict(frame=int(r.n),t=float(r.t),angle=float(r.angle),gs=int(r.green_state),quien=r.quien,black=int(r.negro_px),last_event=str(prev[-1]) if prev else ''))
pd.DataFrame(st).to_csv(O/'paradas.csv',index=False)
