from pathlib import Path
import cv2,numpy as np,pandas as pd
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parent;D=B.parent/'crudo_20261031_195318/1031_195426';F=pd.read_csv(B/'frames_sincronizados.csv')
def sheet(name,ns,cols=4):
 ns=[int(n) for n in ns if 1<=n<=len(F)];o=Image.new('RGB',(cols*240,((len(ns)+cols-1)//cols)*210),'white');dr=ImageDraw.Draw(o)
 for i,n in enumerate(ns):
  r=F.iloc[n-1];x=i%cols*240;y=i//cols*210;o.paste(Image.open(D/f'f_{n:06d}.png').resize((240,180)),(x,y));dr.text((x,y+182),f'{n} AVI {(n-1)/20:.2f}s GS{r.green_state} a{r.angle:.0f}',fill='black');dr.text((x,y+196),str(r.quien),fill='black')
 o.save(B/name)
if __name__=='__main__':
 rows=[]
 for r in F.itertuples():
  im=cv2.imread(str(D/f'f_{r.n:06d}.png'));h=cv2.cvtColor(im,cv2.COLOR_BGR2HSV);m=(h[:,:,0]>=65)&(h[:,:,0]<=100)&(h[:,:,1]>=70)&(h[:,:,2]>=35);m[:30]=False
  rows.append((r.n,int(m.sum()),int(m[80:].sum())))
 p=pd.DataFrame(rows,columns=['n','cromatico','cromatico_bajo']);p.to_csv(B/'barrido_cromatico.csv',index=False)
 ix=np.flatnonzero(p.cromatico.to_numpy()>180);gs=np.split(ix,np.where(np.diff(ix)>16)[0]+1);events=[]
 for j,g in enumerate(gs):
  if not len(g):continue
  peak=g[np.argmax(p.iloc[g].cromatico.to_numpy())]+1;a=int(g[0]+1);b=int(g[-1]+1);events.append((j+1,a,b,int(peak),int(p.iloc[g].cromatico.max())))
  sheet(f'GV_{j+1:02d}.jpg',[a-20,a,a+(peak-a)//2,peak,peak+8,b,b+15,b+35])
 e=pd.DataFrame(events,columns=['id','start','end','peak','max_chroma']);e.to_csv(B/'todos_encuentros.csv',index=False);print(e.to_string(index=False))
 for i,indices in enumerate(np.array_split(np.arange(len(e)), max(1,(len(e)+7)//8))):
  chunk=e.iloc[indices]
  sheet(f'catalogo_verdes_{i+1}.jpg',[n for r in chunk.itertuples() for n in [r.start,r.peak,r.end,r.end+20]])
 for i,chunk in enumerate(np.array_split(np.arange(1,len(F)+1,45),5)):
  sheet(f'barrido_visual_{i+1}.jpg',chunk,6)
