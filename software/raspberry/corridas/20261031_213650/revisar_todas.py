from pathlib import Path
import re,json
import numpy as np,pandas as pd
B=Path(__file__).resolve().parent;O=B/'analisis';O.mkdir(exist_ok=True)
f=pd.read_csv(B/'cuadros.csv'); f['session']=(f.t.diff()>1).cumsum()
ix=np.flatnonzero(f.green_state.eq(4));gg=[g for g in np.split(ix,np.where(np.diff(ix)>1)[0]+1) if len(g)]
episodes=[];snap='';evidence=''
for line in (B/'pista_recuperacion_corregida_20261031_213650.log').read_text().splitlines():
 if '[TERM-HARD] snapshot' in line:snap=line
 if '[RECUP-GUARD] evidencia=' in line:evidence=line
 if '[PERDIDA] disparo;' in line:episodes.append(dict(snapshot=snap,evidence=evidence,prior=line,lines=[]))
 if episodes:episodes[-1]['lines'].append(line)
assert len(episodes)==len(gg)==69
rows=[];cards=[]
for i,(e,g) in enumerate(zip(episodes,gg)):
 a=f.iloc[g[0]];z=f.iloc[g[-1]];nextstart=int(f.iloc[gg[i+1][0]].n) if i+1<len(gg) else len(f)+1
 q=f[(f.n>z.n)&(f.n<nextstart)&(f.session==a.session)&(f.t<=z.t+2.0)]
 if len(q):last=q.iloc[-1];stop=q[q.green_state.eq(19)];gap=q[q.green_state.eq(18)]
 else:last=z;stop=gap=q
 curve=next((x.split('reason=')[1] for x in e['lines'] if '[CURVE-LATCH]' in x),'')
 rows.append(dict(id=i+1,start=int(a.n),end=int(z.n),last=int(last.n),session=int(a.session),avi_s=(a.n-1)/20,t=a.t,duration=z.t-a.t,kind='CURVA' if curve else 'GAP',angle=z.angle,reason=curve,guard_side=any('[RECUP-GUARD] RAMA_PREVIA' in x for x in e['lines']),guard_gap=any('[RECUP-GUARD] GAP_PREVIO' in x for x in e['lines']),palillo=any('[PALILLO]' in x for x in e['lines']),ambigua=any('AMBIGUA sin resolver' in x for x in e['lines']),veto=any('VETO_APLICADO' in x for x in e['lines']),post_frames=len(q),stop_frame=int(stop.n.iloc[0]) if len(stop) else 0,gap_frame=int(gap.n.iloc[0]) if len(gap) else 0,guard_complete=int(q.quien.eq('recup-guard-completa').sum()),guard_stop=int(q.quien.eq('recup-guard-stop').sum()),CG=int(q.quien.eq('recup-completa-giro').sum()),cooldown=int(q.quien.eq('recup-cooldown-recto').sum()),empty=int(q.quien.eq('v66-bloqueo-mascara-vacia-recto').sum()),snapshot=e['snapshot'],evidence=e['evidence'],prior=e['prior']))
 ns=[max(1,int(a.n)-18),min(len(f),int(a.n)+18),min(len(f),int(z.n)+5),min(len(f),int(z.n)+22),min(len(f),int(z.n)+40),int(last.n)]
 # Do not display another session/episode as the outcome of this one.
 ns=[min(n,int(last.n)) if n>z.n else n for n in ns]
 cards.append(dict(id=i+1,frames=ns))
p=pd.DataFrame(rows);p.to_csv(O/'episodios_69.csv',index=False)
(O/'tarjetas.json').write_text(json.dumps(cards))
print(p[['id','start','avi_s','kind','angle','guard_side','guard_gap','stop_frame','guard_complete','CG']].to_string(index=False))
print('SUMMARY',len(f),'episodes',len(p),'guard side',p.guard_side.sum(),'gap',p.guard_gap.sum(),'stops',sum(p.stop_frame>0))
