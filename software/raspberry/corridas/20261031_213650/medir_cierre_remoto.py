from pathlib import Path
import csv,ast,sys
import cv2,numpy as np
D=Path('/home/iita/crudo_recuperacion_corregida_20261031_213650/1031_213701');O=Path('/tmp/revision_213650')
sys.path.insert(0,'/home/iita/Desktop')
from completar_giro import forma_cinta
src=ast.parse(Path('/home/iita/Desktop/main.py').read_text());env=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in src.body:
 if isinstance(node,ast.FunctionDef) and node.name in ['_solo_mi_linea','_error_lateral']:
  exec(compile(ast.Module(body=[node],type_ignores=[]),'analisis','exec'),env)
f={int(r['n']):r for r in csv.DictReader((D/'cuadros.csv').open())};eps=list(csv.DictReader(Path('/tmp/episodios_213650.csv').open()));stats=[];frames=[]
for e in eps:
 end,last=int(e['end']),int(e['last']);run=maxrun=0;first=0;missing_after=0;missing=0;aligned=0;tail=[]
 for n in range(end+1,last+1):
  r=f[n];im=cv2.imread(str(D/f'f_{n:06d}.png'));full=cv2.inRange(im,np.array([0,0,0]),np.array([90,90,90]));full[:60]=0;mm=env['_solo_mi_linea'](full);area=np.count_nonzero(mm);ok=area>=200;sh=forma_cinta(mm,ok);err=env['_error_lateral'](mm,100,120)
  if err is None:err=env['_error_lateral'](mm,60,120)
  ad=sh in ('A','D');run=run+1 if ad else 0;maxrun=max(maxrun,run);aligned=aligned+1 if ad else 0
  if aligned>=2 and not first:first=n
  if not ok:missing+=1;missing_after+=bool(first)
  tail.append(ok);frames.append((e['id'],n,r['t'],int(ok),sh,'' if err is None else err,r['green_state'],r['angle'],r['quien']))
 stats.append((e['id'],end,last,len(tail),missing,first,missing_after,maxrun,sum(tail[-5:]),len(tail[-5:])))
with (O/'metricas_cierre.csv').open('w',newline='') as out:
 w=csv.writer(out);w.writerow(['id','end','last','post_frames','missing','first_two_AD','missing_after_two_AD','max_AD_run','last5_connected','last5_count']);w.writerows(stats)
with (O/'cierre_por_frame.csv').open('w',newline='') as out:
 w=csv.writer(out);w.writerow(['id','n','t','connected','shape','near_error','gs','angle','quien']);w.writerows(frames)
print('medidos',len(stats),'cuadros',len(frames))
