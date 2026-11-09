from pathlib import Path
import sys,re
import cv2,numpy as np,pandas as pd
from recuperacion_guard import RecoveryGuard
B=Path(__file__).resolve().parent;R=B.parents[1]/'corridas';N=R/'20261031_210305'
sys.path.insert(0,str(N/'programas_rpi'))
import ast
env=dict(np=np,cv2=cv2,AREA_MIN_LINEA=200)
for node in ast.parse((B/'main_base.py').read_text()).body:
    if isinstance(node,ast.FunctionDef) and node.name=='_solo_mi_linea':
        exec(compile(ast.Module(body=[node],type_ignores=[]),'funcion_real','exec'),env)

def masks(d,n):
    im=cv2.imread(str(d/f'f_{n:06d}.png'))
    full=cv2.inRange(im,np.array([0,0,0]),np.array([90,90,90]));full[:60]=0
    return env['_solo_mi_linea'](full),full

def history(d,n):
    guard=RecoveryGuard()
    # main observa tambien el cuadro que termina disparando GS4.
    for j in range(max(1,n-29),n+1):guard.observe(masks(d,j)[0])
    guard.freeze();return guard

p=pd.read_csv(N/'analisis_recuperaciones/episodios_cruzados.csv').fillna('')
d=N/'crudo_pista_completa_20261031_210305/1031_210325';rows=[]
for r in p.itertuples():
    guard=history(d,r.start)
    kind='AMBIGUA' if r.ambigua else 'RECTA' if r.decision=='GAP' else 'CURVA'
    reason='palillo: cinta partida' if r.palillo else r.reason
    decision=dict(kind=kind,side=-int(np.sign(r.angle)),heading=-float(r.angle) if r.angle else None,reason=reason)
    term=dict(strong=r.strong,strong_piso=r.piso,side_recent=int(re.search(r'side_recent=(\d+)',r.snapshot)[1]))
    new,why=guard.decide(decision,term,1.0)
    final='GAP' if new['kind'] in ['RECTA','AMBIGUA'] else 'CURVA'
    changed=final!=r.decision or (final=='CURVA' and new['side']!=decision['side'])
    rows.append((r.id,r.start,r.decision,decision['side'],final,new['side'],why,changed))
q=pd.DataFrame(rows,columns=['episode','frame','old','old_side','new','new_side','reason','changed'])
assert q.loc[q.changed,'episode'].tolist()==[1,7,10,11,13,15,16,22,23,25,27,28,30,31,34]
for id in [2,3,4,5,6,8,9,12,14,17,18,19,20,21,24,26,29,32,33]:assert not q[q.episode.eq(id)].changed.item()
q.to_csv(B/'decisiones_34.csv',index=False)

# Replay of the existing exit commands: all observed successful curve exits stay intact.
f=pd.read_csv(d/'cuadros.csv');checks=[]
for id in [2,3,5,6,9,12,14,18,19,21,24,10,13,16,17,22,25]:
    r=p[p.id.eq(id)].iloc[0];guard=RecoveryGuard();t0=float(f.iloc[int(r.end)].t)
    guard.begin_finish(-np.sign(r.angle),t0);actions=[]
    z=f[(f.n>r.end)&(f.t<=t0+1.5)]
    for row in z.itertuples():
        conn,full=masks(d,row.n);action=guard.finish(row.t,conn,full,row.angle)
        if action:actions.append((row.n,action['action']))
    good=id in [2,3,5,6,9,12,14,18,19,21,24]
    if good:assert not actions,(id,actions)
    else:assert actions and any(a=='STOP' for _,a in actions),(id,actions)
    checks.append((id,good,str(actions[:1]),str(actions[-1:])))
pd.DataFrame(checks,columns=['episode','successful_baseline','first_action','last_action']).to_csv(B/'cierres_verificados.csv',index=False)

# Old run: stable branch guard must preserve the observed working decisions.
old=R/'20261031_195318';od=old/'crudo_20261031_195318/1031_195426';of=pd.read_csv(od/'cuadros.csv');ix=np.flatnonzero(of.green_state.eq(4));groups=[g for g in np.split(ix,np.where(np.diff(ix)>1)[0]+1) if len(g)];conflicts=[]
for id,g in enumerate(groups,1):
    a,z=of.iloc[g[0]],of.iloc[g[-1]];guard=history(od,int(a.n));side=-int(np.sign(z.angle))
    if side and guard.evidence['side'] and side!=guard.evidence['side']:conflicts.append(id)
assert conflicts==[12,17],conflicts # Both previously documented failures, not successful baselines.

start='            if np.sum(green_mask) > min_square_size * 255:'
end='            if (not RECUP) and np.sum(black_mask) < min_line_size:'
src=(B/'main.py').read_text();base=(B/'main_base.py').read_text()
assert src[src.index(start):src.index(end)]==base[base.index(start):base.index(end)]
assert (B/'verde_oscuro.py').read_bytes()==(N/'programas_rpi/verde_oscuro.py').read_bytes()
print('OK: 34 decisiones; 15 corregidas, 19 conservadas (incluidos los GAP correctos).')
print('OK: 11 cierres de curva observados como correctos conservan todos sus comandos en replay.')
print('OK: 6 cierres sin recaptura abandonan avance ciego y terminan en STOP si no recuperan.')
print('OK: corrida anterior, 22 episodios: no se invierten lados de curvas observadas como correctas.')
print('OK: bloque de verdes y modulo oscuro identicos a la base probada.')
