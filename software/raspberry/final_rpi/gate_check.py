# -*- coding: utf-8 -*-
"""Pasar CAMINO+MONO, BASE y V1 por el gate ENDURECIDO."""
import importlib.util, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import gate, camino_principal as CP
sp=importlib.util.spec_from_file_location("v1",os.path.join(AQUI,"airborne_v1_adaptado.py"))
V1=importlib.util.module_from_spec(sp); sp.loader.exec_module(V1)
v4,v2=CP.cargar(); SB=CP.hacer_sinbranch(v4)

def serie_cand(cfg):
    def f(ruta,fps,d,h):
        rest=CP.instalar(v2,cfg); tr=SB(fps); cap=cv2.VideoCapture(ruta); out=[]; i=0
        while True:                      # DESDE EL FRAME 0, como exige el gate
            ok,fr=cap.read()
            if not ok or i>h: break
            r=tr.step(v2.frame_pi(fr))
            if i>=d:
                t=r.get("target")
                out.append((t,None if t is None else float(np.clip(-90.0*(t[0]-v2.CENTER)/(v2.W/2.),-90,90)),r.get("state")))
            i+=1
        cap.release(); rest(); return out
    return f

def serie_v1(ruta,fps,d,h):
    tr=V1.AirborneV1(fps); cap=cv2.VideoCapture(ruta); out=[]; i=0
    while True:
        ok,fr=cap.read()
        if not ok or i>h: break
        r=tr.paso(V1.frame_de_la_pi(fr))
        if i>=d:
            t=r.get("target"); a=r.get("angle_target")
            out.append((t,None if (t is None or a is None or not np.isfinite(a)) else float(a),r.get("estado")))
        i+=1
    cap.release(); return out

print("")
print("="*92)
print("  RE-VERIFICACION CON EL GATE ENDURECIDO")
print("  El gate viejo dejo pasar una inversion de signo DENTRO del control.")
print("="*92)
for nom,fn in (("BASE",serie_cand(dict(camino=False,mono=False))),
               ("CAMINO+MONO",serie_cand(dict(camino=True,mono=True))),
               ("V1 (POI)",serie_v1)):
    print(""); print("  --- %s ---"%nom)
    gate.evaluar(fn)
print("="*92)
