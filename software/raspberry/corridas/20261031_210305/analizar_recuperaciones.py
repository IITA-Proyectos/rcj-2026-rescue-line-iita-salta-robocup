from pathlib import Path
import re,json
import cv2,numpy as np,pandas as pd
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parent;D=B/'crudo_pista_completa_20261031_210305/1031_210325';O=B/'analisis_recuperaciones';O.mkdir(exist_ok=True)
f=pd.read_csv(D/'cuadros.csv');c=pd.read_csv(B/'pista_completa_1031_210308.csv',comment='#').apply(pd.to_numeric,errors='coerce');c=c[c.us.notna()].copy();c['sec']=(c.us-c.us.iloc[0])/1e6
ft=f.t.to_numpy();cmd=np.rint(f.angle.to_numpy())/90*1000;ct=c.sec.to_numpy();rx=c.rxsteer.to_numpy();change=np.r_[False,np.diff(cmd)!=0]&(f.green_state.to_numpy()==0)&(abs(cmd)>20);ts=ft[change];vs=cmd[change];scores=[]
for off in np.arange(-30,61,.025):
 ix=np.searchsorted(ct,ts+off+.02);ok=(ix>0)&(ix<len(c));ii=np.clip(ix,0,len(c)-1);scores.append((np.mean(np.minimum(abs(rx[ii[ok]]-vs[ok]),1000)),off))
best=sorted(scores)[:3];off=float(best[0][1]);print('ALIGN',best)
def groups(mask):
 ix=np.flatnonzero(mask);return [g for g in np.split(ix,np.where(np.diff(ix)>1)[0]+1) if len(g)]
eps=[];snap=''
for line in (B/'pista_pista_completa_20261031_210305.log').read_text().splitlines():
 if '[TERM-HARD] snapshot' in line:snap=line
 if '[PERDIDA] disparo;' in line:eps.append(dict(snapshot=snap,prior=line,lines=[]))
 if eps:eps[-1]['lines'].append(line)
gg=groups(f.green_state.eq(4));assert len(gg)==len(eps)==34
rows=[]
for i,(e,g) in enumerate(zip(eps,gg)):
 a=f.iloc[g[0]];z=f.iloc[g[-1]];snap=e['snapshot'];ls=e['lines'];reason=next((l.split('reason=')[1] for l in ls if '[CURVE-LATCH]' in l),'');curve=bool(reason);piso='piso=True' in snap;strong='snapshot strong=True' in snap
 row=dict(id=i+1,start=int(a.n),end=int(z.n),avi_s=(a.n-1)/20,t=a.t,duration=z.t-a.t,segment='pruebas' if a.n<=4680 else 'pista',strong=strong,piso=piso,snapshot=snap,prior=e['prior'],reason=reason,decision='CURVA' if curve else 'GAP',palillo=any('[PALILLO]' in l for l in ls),ambigua=any('AMBIGUA sin resolver' in l for l in ls),veto=any('VETO_APLICADO' in l for l in ls),angle=float(z.angle))
 row['propuesta']='GAP' if curve and strong and piso and reason=='lateral previa + fragmento pequeno compatible' and 'side_recent=0' in snap else row['decision']
 # Scope both the reverse and directed pivot to this episode; include pivot end beyond Pi release.
 q=c[c.sec.between(a.t+off-.03,z.t+off+.8)].copy()
 rev=q[(q.ddir==1)&(q.ram==-1)&((q.ls>0)|(q.rs>0))]
 if len(rev):row['reverse_s']=float(rev.sec.iloc[-1]-rev.sec.iloc[0]);row['reverse_pulses_FL']=float(abs(rev.fl_enc.iloc[-1]-rev.fl_enc.iloc[0]));row['reverse_pulses_FR']=float(abs(rev.fr_enc.iloc[-1]-rev.fr_enc.iloc[0]))
 piv=q[(q.ram==13)&((q.ls>0)|(q.rs>0))]
 if len(piv):
  yy=np.unwrap(piv.yaw.to_numpy()/10*np.pi/180)*180/np.pi;row.update(pivot_s=float(piv.sec.iloc[-1]-piv.sec.iloc[0]),yaw=float(yy[-1]-yy[0]),gyro=float(np.trapezoid(piv.gz/10,piv.sec)),pivot_rx=float(piv.rxsteer.median()*.09),rpm_FL=float(piv.fl_rpm.median()),rpm_FR=float(piv.fr_rpm.median()),rpm_BL=float(piv.bl_rpm.median()),rpm_BR=float(piv.br_rpm.median()))
 if len(q):row['drop']=float(q['drop'].iloc[-1]-q['drop'].iloc[0])
 rows.append(row)
p=pd.DataFrame(rows);p.to_csv(O/'episodios_cruzados.csv',index=False);c.to_pickle(O/'teensy.pkl');(O/'sincronizacion.json').write_text(json.dumps(dict(offset=off,best=[(float(a),float(b)) for a,b in best]),indent=2))
print(p[['id','start','avi_s','decision','propuesta','reverse_s','pivot_s','yaw','gyro','pivot_rx','drop']].to_string(index=False))
assert p.loc[p.decision.ne(p.propuesta),'id'].tolist()==[27,28,30,31]
def sheet(name,ids):
 ns=[]
 for id in ids:
  r=p[p.id.eq(id)].iloc[0];ns.extend([r.start-35,r.start-15,r.start,r.start+18,r.end,r.end+20,r.end+40,r.end+60])
 o=Image.new('RGB',(960,((len(ns)+3)//4)*210),'white');dr=ImageDraw.Draw(o)
 for j,n in enumerate(ns):
  n=int(min(len(f),max(1,n)));r=f.iloc[n-1];x=j%4*240;y=j//4*210;o.paste(Image.open(D/f'f_{n:06d}.png').resize((240,180)),(x,y));dr.text((x,y+182),f'{n} AVI {(n-1)/20:.2f}s GS{r.green_state} a{r.angle}',fill='black');dr.text((x,y+196),str(r.quien),fill='black')
 o.save(O/name)
sheet('gaps_445_450_458.jpg',[27,28,29]);sheet('gaps_527_530.jpg',[30,31,32]);sheet('codos_comparacion.jpg',[2,3,26,33]);sheet('gap_forzado_codo.jpg',[1,11,23,34])
