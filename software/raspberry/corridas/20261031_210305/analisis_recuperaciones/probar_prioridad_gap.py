"""Contraste de una propuesta usando las decisiones/evidencias registradas.

No reproduce la trayectoria ni altera los programas del robot.
"""
from pathlib import Path
import re,sys
import pandas as pd

B=Path(__file__).resolve().parent
sys.path.insert(0,str(B.parent/'programas_rpi'))
from terminal_local_guard import would_veto_curve

def proponer(decision,evidence):
    # Extension acotada, preservando las protecciones y motivos existentes.
    return bool(decision.get('kind')=='CURVA'
                and decision.get('reason')=='lateral previa + fragmento pequeno compatible'
                and evidence.get('strong') and evidence.get('strong_piso')
                and evidence.get('side_recent')==0)

p=pd.read_csv(B/'episodios_cruzados.csv').fillna('')
changes=[]
for r in p.itertuples():
    d=dict(kind=r.decision,reason=r.reason)
    ev=dict(strong=bool(r.strong),strong_piso=bool(r.piso),side_recent=int(re.search(r'side_recent=(\d+)',r.snapshot)[1]))
    if proponer(d,ev):
        assert not would_veto_curve(d,ev), 'La propuesta debe resolver casos que el veto actual omite'
        changes.append(r.id)
assert changes==[27,28,30,31],changes
assert all(i not in changes for i in [2,3,26,29,32,33])

old=B.parents[1]/'20261031_195318/pista_20261031_195318.log'
snapshot='';prior=[]
for line in old.read_text().splitlines():
    if '[TERM-HARD] snapshot' in line:snapshot=line
    if '[PERDIDA] disparo;' in line:prior.append(dict(snapshot=snapshot,reason='',kind='GAP'))
    if '[CURVE-LATCH]' in line:prior[-1].update(kind='CURVA',reason=line.split('reason=')[1])
old_changes=[]
for i,r in enumerate(prior,1):
    s=r['snapshot'];m=re.search(r'side_recent=(\d+)',s)
    ev=dict(strong='snapshot strong=True' in s,strong_piso='piso=True' in s,side_recent=int(m[1]) if m else None)
    if proponer(r,ev):old_changes.append(i)
assert not old_changes,old_changes
summary=f'''Contraste de decisiones registradas: OK
Corrida nueva: {len(p)} episodios; cambia {changes}; otros {len(p)-len(changes)} conservados.
GAP correctos 29/32: conservados. Decisiones de curva 2/3/26/33: conservadas.
Corrida anterior: {len(prior)} episodios; {len(old_changes)} cambios adicionales.
Esta comprobacion no es una simulacion fisica ni una reproduccion integral del lazo de vision.
'''
(B/'resultado_propuesta.txt').write_text(summary,encoding='utf-8');print(summary)
