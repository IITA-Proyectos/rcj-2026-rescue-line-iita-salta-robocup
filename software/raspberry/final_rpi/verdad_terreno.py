# -*- coding: utf-8 -*-
"""ERROR CONTRA VERDAD DE TERRENO. La medicion que faltaba en toda la campana.

Las cinco metricas del banco -disponibilidad, huecos, saltos, inversiones,
suavidad- son TODAS de auto-consistencia. Ninguna mide si el target esta sobre
la cinta correcta. Un tracker que se engancha a una sombra y la sigue suave saca
puntaje perfecto.

`groundtruth_video_4.csv` es el unico material del repo donde se conoce la
respuesta correcta: se anclo en un frame inequivoco de video_4 -donde Benjamin
movio el robot A MANO por la trayectoria correcta- y se propago hacia atras por
solape de componentes.

Se excluye el tramo MANUAL_LIFT: ahi el robot estaba levantado.
"""
import csv, importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import camino_principal as CP
sp=importlib.util.spec_from_file_location("v1",os.path.join(AQUI,"airborne_v1_adaptado.py"))
V1=importlib.util.module_from_spec(sp); sp.loader.exec_module(V1)
v4,v2=CP.cargar(); SB=CP.hacer_sinbranch(v4)
FPS=20.0   # video_4 es de 20 fps reales

GT={}
for r in csv.DictReader(open(os.path.join(AQUI,"groundtruth_video_4.csv"))):
    if r["gt_visible"]!="1" or not r["gt_target_x"]: continue
    if r["state"]=="MANUAL_LIFT": continue
    GT[int(r["frame"])]=float(r["gt_target_x"])
print("")
print("="*88)
print("  ERROR LATERAL CONTRA VERDAD DE TERRENO  (video_4, %d frames etiquetados)"%len(GT))
print("  Excluido MANUAL_LIFT. gt_target_x = la columna correcta del target.")
print("="*88)

def corr(kind, cfg=None):
    if cfg is not None: rest=CP.instalar(v2,cfg)
    cap=cv2.VideoCapture(os.path.join(AQUI,"video_4.avi"))
    tr = SB(FPS) if kind!="v1" else V1.AirborneV1(FPS)
    out={}; i=0
    while True:
        ok,fr=cap.read()
        if not ok: break
        g=v2.frame_pi(fr)
        if kind=="v1":
            r=tr.paso(g); t=r.get("target")
        else:
            r=tr.step(g); t=r.get("target")
        if i in GT: out[i]=(None if t is None else float(t[0]))
        i+=1
    cap.release()
    if cfg is not None: rest()
    return out

print("")
print("  %-14s %7s %8s %8s %8s %8s %9s %9s"
      %("variante","con gt","err p50","err p75","err p90","err max","sin target","|err|>20"))
filas=[]
for nom,kind,cfg in (("BASE","cand",dict(camino=False,mono=False)),
                     ("CAMINO+MONO","cand",dict(camino=True,mono=True)),
                     ("V1 (POI)","v1",None)):
    d=corr(kind,cfg)
    err=[abs(d[f]-GT[f]) for f in GT if d.get(f) is not None]
    sin=sum(1 for f in GT if d.get(f) is None)
    if not err: print("  %-14s sin datos"%nom); continue
    e=np.array(err)
    filas.append((nom,e,sin))
    print("  %-14s %7d %8.2f %8.2f %8.2f %8.2f %9d %9d"
          %(nom,len(e),np.percentile(e,50),np.percentile(e,75),np.percentile(e,90),
            e.max(),sin,int((e>20).sum())))
print("")
print("  En grados de steer (1 px = 1,125 grados):")
for nom,e,sin in filas:
    print("    %-14s p50 %6.2f deg   p90 %6.2f deg   max %6.2f deg"
          %(nom,1.125*np.percentile(e,50),1.125*np.percentile(e,90),1.125*e.max()))
print("")
print("  LIMITE HONESTO: son %d frames de UN video, el unico con verdad de"%len(GT))
print("  terreno. No decide sola, pero es lo unico que mide EXACTITUD y no")
print("  auto-consistencia.")
print("="*88)
