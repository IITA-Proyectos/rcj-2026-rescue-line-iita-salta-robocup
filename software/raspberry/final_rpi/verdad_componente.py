# -*- coding: utf-8 -*-
"""LIBRE DE CONVENCION: el target, cae SOBRE la componente correcta?

La medicion anterior comparaba contra `gt_target_x`, que sale de
`target_de_referencia` -el propio selector de V2 aplicado a la componente
correcta-. Eso favorece al linaje V2 por construccion y no sirve para comparar
arquitecturas distintas.

Esta version pregunta lo unico que es comun a las dos: la distancia del target
a la componente CORRECTA. Si el target esta sobre la cinta buena, la distancia
es 0, este donde este a lo largo.
"""
import csv, importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import groundtruth_v4 as GT4, camino_principal as CP
sp=importlib.util.spec_from_file_location("v1",os.path.join(AQUI,"airborne_v1_adaptado.py"))
V1=importlib.util.module_from_spec(sp); sp.loader.exec_module(V1)
v4,v2=CP.cargar(); SB=CP.hacer_sinbranch(v4)
FPS=20.0; DESDE, HASTA = 490, 600

cap=cv2.VideoCapture(os.path.join(AQUI,"video_4.avi")); frames=[]; i=0
while True:
    ok,fr=cap.read()
    if not ok or i>HASTA+2: break
    frames.append(v2.frame_pi(fr)); i+=1
cap.release()
gt, _anclas = GT4.propagar(v2, frames, DESDE, HASTA)

# frames validos: gt presente y fuera del tramo levantado a mano
valid=[]
for f in range(DESDE, HASTA+1):
    m = gt.get(f)
    if m is None: continue
    if GT4.invalido(os.path.join(AQUI,"video_4.avi"), f): continue
    valid.append(f)
print("")
print("="*90)
print("  DISTANCIA DEL TARGET A LA COMPONENTE CORRECTA  (%d frames con gt)"%len(valid))
print("  Libre de convencion: no importa DONDE a lo largo de la cinta este el")
print("  target, solo si esta SOBRE la cinta correcta.")
print("="*90)

def corr(kind,cfg=None):
    if cfg is not None: rest=CP.instalar(v2,cfg)
    tr = SB(FPS) if kind!="v1" else V1.AirborneV1(FPS)
    out={}
    for i,g in enumerate(frames):
        r = tr.paso(g) if kind=="v1" else tr.step(g)
        t=r.get("target")
        if i in valid: out[i]=None if t is None else (float(t[0]),float(t[1]))
    if cfg is not None: rest()
    return out

print("")
print("  %-14s %7s %8s %8s %8s %9s %10s"
      %("variante","n","d p50","d p75","d p90","d max","fuera>3px"))
res={}
for nom,kind,cfg in (("BASE","cand",dict(camino=False,mono=False)),
                     ("CAMINO+MONO","cand",dict(camino=True,mono=True)),
                     ("V1 (POI)","v1",None)):
    d=corr(kind,cfg); ds=[]
    for f in valid:
        t=d.get(f)
        if t is None: continue
        m=gt[f]
        ys,xs=np.nonzero(m)
        if not len(xs): continue
        ds.append(float(np.min(np.hypot(xs-t[0], ys-t[1]))))
    if not ds: print("  %-14s sin datos"%nom); continue
    a=np.array(ds); res[nom]=a
    print("  %-14s %7d %8.2f %8.2f %8.2f %9.2f %10d"
          %(nom,len(a),np.percentile(a,50),np.percentile(a,75),
            np.percentile(a,90),a.max(),int((a>3).sum())))
print("")
print("  d = 0 significa que el target cae EXACTAMENTE sobre la cinta correcta.")
print("  fuera>3px = frames donde el target esta en otra cosa.")
print("="*90)
