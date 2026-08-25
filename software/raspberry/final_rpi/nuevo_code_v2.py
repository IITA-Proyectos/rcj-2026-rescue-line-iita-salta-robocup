# -*- coding: utf-8 -*-
"""
NUEVO CODE V2 - shadow de percepción para RCJ Rescue Line

Cambios respecto a V1:
- deja de usar el TOP del contorno como objetivo directo;
- selecciona UNA componente por continuidad temporal;
- elimina fragmentos pequeños;
- cierra huecos chicos de reflejos (morph close leve);
- obtiene la línea central (skeleton);
- el target avanza por esa trayectoria a una distancia geodésica;
- en ramas, continuidad de heading/target decide antes que el área;
- si el target cambia demasiado, lo proyecta a una posición cercana de la
  trayectoria actual;
- en PERDIDA no inventa target.

NO mueve el robot. NO es simulación física.
"""

import argparse, csv, heapq, math, os
import cv2
import numpy as np
from skimage.morphology import skeletonize

W, H = 160, 120
CENTER = (W - 1) / 2.0
LO = np.array([0,0,0], np.uint8)
HI = np.array([90,90,90], np.uint8)

FLOOR_TOP = 35
NEAR = (110,119)
MID  = (95,105)
FAR  = (75,85)
PIX_MIN_BAND = 8
MIN_AREA = 30
LOOKAHEAD = 70.0

COLORS = {
    "HIGH": (70,220,70),
    "MEDIUM": (80,210,220),
    "LOW": (0,160,255),
    "LOW_FORWARD": (0,190,255),
    "SIN_CERCA": (255,180,60),
    "PERDIDA": (80,80,255),
}

N8 = [
    (-1,-1,2**0.5), (-1,0,1), (-1,1,2**0.5),
    (0,-1,1),                 (0,1,1),
    (1,-1,2**0.5),  (1,0,1),  (1,1,2**0.5),
]

def frame_pi(frame):
    if frame.shape[0] == 240 and frame.shape[1] >= 640:
        return frame[:, :320][1::2, 1::2]
    g = cv2.rotate(frame, cv2.ROTATE_180)
    return cv2.resize(g, (W,H), interpolation=cv2.INTER_NEAREST)

def atan2_actual(g):
    m = cv2.inRange(g, LO, HI)
    m[:60,:] = 0
    if m.sum() < 1:
        return 0.0
    ys,xs = np.nonzero(m)
    xc = (xs - (W/2 - 1)) / (W/2)
    yc = ((H-1) - ys) / H
    xb = np.mean(xc * (1-yc))
    yb = np.mean(yc)
    return (math.atan2(yb, xb)/math.pi*180.0) - 90.0

def mask_linea(g):
    m = cv2.inRange(g, LO, HI)
    m[:FLOOR_TOP,:] = 0

    # recorte de esquinas altas, siguiendo la idea de Airborne pero adaptado
    htri = int(H*0.15)
    wtri = int(W*0.25)
    cv2.fillPoly(m, [np.array([[0,FLOOR_TOP],[wtri,FLOOR_TOP],[0,min(H-1,FLOOR_TOP+htri)]], np.int32)], 0)
    cv2.fillPoly(m, [np.array([[W-1,FLOOR_TOP],[W-1-wtri,FLOOR_TOP],[W-1,min(H-1,FLOOR_TOP+htri)]], np.int32)], 0)

    # cierra huecos de reflejo pequeños sin copiar la morfología enorme de Airborne
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), iterations=4)
    return m

def runs_1d(xs):
    xs = np.sort(np.unique(xs))
    if len(xs) == 0:
        return []
    out=[]
    s=p=int(xs[0])
    for x in xs[1:]:
        x=int(x)
        if x == p+1:
            p=x
        else:
            out.append((s,p))
            s=p=x
    out.append((s,p))
    return out

def cc_candidates(m):
    n, lab, stats, _ = cv2.connectedComponentsWithStats((m>0).astype(np.uint8), 8)
    out=[]
    for k in range(1,n):
        area = int(stats[k, cv2.CC_STAT_AREA])
        if area < MIN_AREA:
            continue
        ys,xs = np.nonzero(lab==k)
        if len(xs)==0:
            continue
        mm=(lab==k)
        near = int(mm[NEAR[0]:NEAR[1]+1].sum()) >= PIX_MIN_BAND
        mid  = int(mm[MID[0]:MID[1]+1].sum()) >= PIX_MIN_BAND
        far  = int(mm[FAR[0]:FAR[1]+1].sum()) >= PIX_MIN_BAND
        out.append(dict(
            k=k, area=area,
            xmin=int(xs.min()), xmax=int(xs.max()),
            ymin=int(ys.min()), ymax=int(ys.max()),
            cx=float(xs.mean()), cy=float(ys.mean()),
            near=near, mid=mid, far=far
        ))
    return lab,out

def component_distance(lab,k,pt):
    ys,xs=np.nonzero(lab==k)
    if len(xs)==0:
        return 1e9
    return float(np.sqrt(((xs-pt[0])**2 + (ys-pt[1])**2).min()))

def graph_from_skeleton(sk):
    ys,xs=np.nonzero(sk)
    pts=list(zip(ys.tolist(), xs.tolist()))
    idx={p:i for i,p in enumerate(pts)}
    adj=[[] for _ in pts]
    deg=np.zeros(len(pts), np.int16)
    for i,(y,x) in enumerate(pts):
        for dy,dx,w in N8:
            j=idx.get((y+dy,x+dx))
            if j is not None:
                adj[i].append((j,w))
        deg[i]=len(adj[i])
    return pts,adj,deg

def dijkstra(adj,start):
    n=len(adj)
    dist=[float("inf")]*n
    prev=[-1]*n
    dist[start]=0.0
    pq=[(0.0,start)]
    while pq:
        d,u=heapq.heappop(pq)
        if d != dist[u]:
            continue
        for v,w in adj[u]:
            nd=d+w
            if nd<dist[v]:
                dist[v]=nd
                prev[v]=u
                heapq.heappush(pq,(nd,v))
    return np.asarray(dist),prev

def reconstruct(prev,start,end):
    a=[]
    u=end
    guard=0
    while u!=-1 and guard<10000:
        a.append(u)
        if u==start:
            break
        u=prev[u]
        guard+=1
    if not a or a[-1]!=start:
        return []
    return a[::-1]

def angdiff(a,b):
    return abs((a-b+180)%360-180)

class NuevoCodeV2:
    def __init__(self,fps):
        self.fps=float(fps)
        self.prev_entry=(CENTER,119.0)
        self.prev_target=None
        self.prev_heading=0.0
        self.last_good_target=None

    def choose_component(self,m):
        lab,cands=cc_candidates(m)
        if not cands:
            return lab,None,"PERDIDA"

        near=[c for c in cands if c["near"]]

        if near:
            # elimina fragmentos minúsculos respecto de la línea principal
            amax=max(c["area"] for c in near)
            viable=[c for c in near if c["area"] >= max(MIN_AREA,0.05*amax)]

            # núcleo Airborne: identidad por continuidad, no por área
            c=min(viable, key=lambda q: component_distance(lab,q["k"],self.prev_entry))

            # si lo de abajo es poco profundo pero hay una continuación adelante
            # pegada al target anterior, usar esa evidencia como guía
            if not c["mid"] and self.prev_target is not None:
                ahead=[a for a in cands if not a["near"] and a["ymax"]>=45]
                if ahead:
                    a=min(ahead, key=lambda q: component_distance(lab,q["k"],self.prev_target))
                    if component_distance(lab,a["k"],self.prev_target) < 35:
                        return lab,a,"AHEAD_BRIDGE"

            return lab,c,"NEAR"

        # no hay nada debajo: seguir la componente adelante más continua
        ref=self.prev_target if self.prev_target is not None else self.prev_entry
        amax=max(c["area"] for c in cands)
        viable=[c for c in cands if c["area"]>=max(MIN_AREA,0.03*amax)]
        c=min(viable, key=lambda q: component_distance(lab,q["k"],ref) + 0.08*(119-q["ymax"]))

        if component_distance(lab,c["k"],ref)>75 and c["ymax"]<70:
            return lab,None,"PERDIDA"

        return lab,c,"AHEAD"

    def state(self,comp):
        if comp is None:
            return "PERDIDA"
        def b(a,z):
            return int((comp[a:z+1]>0).sum()) >= PIX_MIN_BAND
        near,mid,far=b(*NEAR),b(*MID),b(*FAR)
        if near:
            if mid and far: return "HIGH"
            if mid: return "MEDIUM"
            return "LOW"
        return "SIN_CERCA"

    def path_target(self,comp,mode):
        sk=skeletonize(comp>0)
        pts,adj,deg=graph_from_skeleton(sk)
        if len(pts)<2:
            return sk,None

        arr=np.array([(x,y) for y,x in pts], float)
        maxy=max(y for y,x in pts)

        if mode=="NEAR":
            cand=[i for i,(y,x) in enumerate(pts) if y>=maxy-8]

            # Cuando la mancha inferior es muy ancha / tiene varias entradas,
            # elegir la entrada físicamente más cercana al centro del robot.
            row_x=np.where(comp[min(119,int(round(maxy)))]>0)[0]
            bruns=runs_1d(row_x)
            ys_all,xs_all=np.nonzero(comp>0)
            width=(xs_all.max()-xs_all.min()+1) if len(xs_all) else 0

            if len(bruns)>=2 or width>=0.85*W:
                run=min(bruns,key=lambda r:abs(((r[0]+r[1])/2)-CENTER)) if bruns else (CENTER,CENTER)
                rc=(run[0]+run[1])/2
                start=min(cand,key=lambda i:abs(arr[i,0]-rc)+0.2*abs(arr[i,1]-maxy))
            else:
                start=min(cand,key=lambda i:(arr[i,0]-self.prev_entry[0])**2+(arr[i,1]-self.prev_entry[1])**2)
        else:
            cand=[i for i,(y,x) in enumerate(pts) if y>=maxy-3]
            ref=self.prev_target if self.prev_target is not None else self.prev_entry
            start=min(cand,key=lambda i:(arr[i,0]-ref[0])**2+(arr[i,1]-ref[1])**2)

        sy,sx=pts[start]
        dist,prev=dijkstra(adj,start)
        finite=np.where(np.isfinite(dist))[0]
        if not len(finite):
            return sk,None

        simple_mode="AHEAD" if mode.startswith("AHEAD") else mode

        if simple_mode=="AHEAD":
            # evidencia presente manda: punto visible más cercano
            cands=[i for i in finite if pts[i][0]>=maxy-4]
            if not cands: cands=[start]
            ref=self.prev_target if self.prev_target is not None else (sx,sy)
            target_idx=min(cands,key=lambda i:(pts[i][1]-ref[0])**2+(pts[i][0]-ref[1])**2)
            path_idx=[start,target_idx] if target_idx!=start else [start]
        else:
            # shell geodésico: busca un objetivo ~48 px por delante SOBRE la línea central
            lo=max(18,LOOKAHEAD-16)
            hi=LOOKAHEAD+18
            cands=[i for i in finite if lo<=dist[i]<=hi and pts[i][0]<=sy+3]
            if not cands:
                cands=sorted(finite,key=lambda i:abs(dist[i]-LOOKAHEAD))[:min(30,len(finite))]

            def score(i):
                y,x=pts[i]
                dy=sy-y
                heading=math.degrees(math.atan2(x-sx,max(dy,1e-6)))
                s=0.35*abs(dist[i]-LOOKAHEAD)
                s+=0.55*angdiff(heading,self.prev_heading)
                if self.prev_target is not None:
                    s+=0.10*math.hypot(x-self.prev_target[0],y-self.prev_target[1])
                s+=0.30*max(0,8-dy)
                return s

            target_idx=min(cands,key=score)
            path_idx=reconstruct(prev,start,target_idx)
            if not path_idx:
                path_idx=[start,target_idx]

        ty,tx=pts[target_idx]
        heading=math.degrees(math.atan2(tx-sx,max(sy-ty,1e-6)))
        path=[(float(pts[i][1]),float(pts[i][0])) for i in path_idx]

        return sk,dict(
            start=(float(sx),float(sy)),
            target=(float(tx),float(ty)),
            heading=heading,
            path=path
        )

    def step(self,g):
        m=mask_linea(g)
        lab,c,mode=self.choose_component(m)

        if c is None:
            return dict(ok=False,state="PERDIDA",mask=m,comp=None,skel=None,
                        start=None,target=None,path=None,reason="sin_componente",mode=mode)

        comp=(lab==c["k"]).astype(np.uint8)*255

        # Rellenar huecos internos del contorno (reflejos blancos sobre la cinta).
        # Esto evita que el skeleton se bifurque alrededor de cada brillo sin
        # unir componentes externas distintas.
        ext,_ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        comp_filled=np.zeros_like(comp)
        if ext:
            cv2.drawContours(comp_filled, ext, -1, 255, thickness=-1)
        else:
            comp_filled=comp
        comp=comp_filled

        st=self.state(comp)
        if mode=="AHEAD_BRIDGE":
            st="LOW_FORWARD"

        sk,res=self.path_target(comp,mode)
        if res is None:
            return dict(ok=False,state="PERDIDA",mask=m,comp=comp,skel=sk,
                        start=None,target=None,path=None,reason="sin_path",mode=mode)

        raw=res["target"]
        target=raw
        reason=mode.lower()+"_path"

        # continuidad temporal sin sacar la cruz de la trayectoria:
        # si el target quiere saltar, buscar un punto del skeleton todavía cercano
        if self.prev_target is not None:
            jump=math.hypot(raw[0]-self.prev_target[0],raw[1]-self.prev_target[1])
            cap=16 if st in ("HIGH","MEDIUM") else 12 if st in ("LOW","LOW_FORWARD") else 20

            if jump>cap:
                ys,xs=np.nonzero(sk)
                dp=np.sqrt((xs-self.prev_target[0])**2+(ys-self.prev_target[1])**2)
                poss=np.where(dp<=cap)[0]

                if len(poss):
                    j=poss[np.argmin((xs[poss]-raw[0])**2+(ys[poss]-raw[1])**2)]
                    target=(float(xs[j]),float(ys[j]))
                    reason+="|continuidad"

        target_cap=target          # etapa 2, para registro

        # LOW: no permitir un salto grande si la geometría recién se degradó
        if st=="LOW" and self.last_good_target is not None:
            if math.hypot(target[0]-self.last_good_target[0],target[1]-self.last_good_target[1])>28:
                ys,xs=np.nonzero(sk)
                j=np.argmin((xs-self.last_good_target[0])**2+(ys-self.last_good_target[1])**2)
                target=(float(xs[j]),float(ys[j]))
                reason+="|low_proj"

        self.prev_entry=res["start"]
        self.prev_target=target
        self.prev_heading=res["heading"]
        if st in ("HIGH","MEDIUM"):
            self.last_good_target=target

        # Etapas intermedias, SOLO PARA REGISTRO. No cambian ningun calculo:
        # son tres claves mas en el dict de salida. `target_cap` sale despues
        # del cap de continuidad y `target_lowproj` despues de la proyeccion
        # LOW, que hasta ahora solo se podian inferir del sufijo de `reason`.
        # PROTOCOLO_SABADO.md las pide por nombre: sin ellas un log no permite
        # clasificar una falla, porque `target_geometric` de V4 ya viene con
        # estos dos guards aplicados y no es el geometrico crudo.
        # Fidelidad verificada sobre los 10 autonomos: 0 discrepancias.
        return dict(ok=True,state=st,mask=m,comp=comp,skel=sk,
                    start=res["start"],target=target,path=res["path"],
                    heading=res["heading"],reason=reason,mode=mode,
                    target_raw=raw,target_cap=target_cap,
                    target_lowproj=target)

def pxi(p):
    return None if p is None else (int(round(p[0])),int(round(p[1])))

def draw(r):
    vis=np.zeros((H,W,3),np.uint8)
    vis[r["mask"]>0]=(45,45,45)

    if r["comp"] is not None:
        vis[r["comp"]>0]=(35,90,35)

    if r["skel"] is not None:
        vis[r["skel"]>0]=(0,210,255)

    if r.get("path"):
        q=[(int(round(x)),int(round(y))) for x,y in r["path"]]
        if len(q)>=2:
            cv2.polylines(vis,[np.asarray(q,np.int32)],False,(255,180,60),1)

    if r.get("start") is not None:
        cv2.circle(vis,pxi(r["start"]),3,(255,100,50),-1)

    if r.get("target") is not None:
        col=(255,255,255) if r["state"] in ("HIGH","MEDIUM") else (0,220,255)
        cv2.drawMarker(vis,pxi(r["target"]),col,cv2.MARKER_TILTED_CROSS,11,2)

    cv2.line(vis,(int(round(CENTER)),0),(int(round(CENTER)),H-1),(90,90,90),1)
    return vis

def run(video,outavi,outcsv,fps):
    cap=cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir "+video)

    tr=NuevoCodeV2(fps)
    E=4
    CW,CH=W*E,H*E
    OW,OH=CW*2,CH+175
    vw=cv2.VideoWriter(outavi,cv2.VideoWriter_fourcc(*"MJPG"),fps,(OW,OH))

    f=open(outcsv,"w",newline="",encoding="utf-8")
    wr=csv.writer(f)
    wr.writerow(["frame","time_s","state","old_atan2","target_x","target_y",
                 "target_jump_px","target_on_selected_line","mode","reason"])

    prev=None
    i=0
    max_jump=0.0
    off_line=0
    no_target=0

    while True:
        ok,fr=cap.read()
        if not ok:
            break

        g=frame_pi(fr)
        r=tr.step(g)
        old=atan2_actual(g)

        jump=""
        online=0

        if r.get("target") is not None:
            t=r["target"]
            if prev is not None:
                jump=math.hypot(t[0]-prev[0],t[1]-prev[1])
                max_jump=max(max_jump,jump)
            prev=t

            x,y=pxi(t)
            if r["skel"] is not None and 0<=x<W and 0<=y<H and bool(r["skel"][y,x]):
                online=1
            else:
                off_line+=1
        else:
            no_target+=1
            prev=None

        wr.writerow([
            i,f"{i/fps:.3f}",r["state"],f"{old:.3f}",
            "" if r.get("target") is None else f"{r['target'][0]:.2f}",
            "" if r.get("target") is None else f"{r['target'][1]:.2f}",
            "" if jump=="" else f"{jump:.2f}",
            online,r.get("mode",""),r.get("reason","")
        ])

        cam=cv2.resize(g,(CW,CH),interpolation=cv2.INTER_NEAREST)
        pan=cv2.resize(draw(r),(CW,CH),interpolation=cv2.INTER_NEAREST)

        out=np.zeros((OH,OW,3),np.uint8)
        out[:CH,:CW]=cam
        out[:CH,CW:]=pan

        cv2.putText(out,"CAMARA QUE VIO LA PI",(10,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(235,235,235),1,cv2.LINE_AA)
        cv2.putText(out,"NUEVO CODE V2",(CW+10,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(235,235,235),1,cv2.LINE_AA)

        y0=CH+28
        col=COLORS.get(r["state"],(235,235,235))
        cv2.putText(out,f"frame {i}  t={i/fps:.2f}s   ESTADO {r['state']}",(10,y0),cv2.FONT_HERSHEY_SIMPLEX,.58,col,1,cv2.LINE_AA)
        cv2.putText(out,f"atan2 viejo {old:+6.1f} deg",(10,y0+30),cv2.FONT_HERSHEY_SIMPLEX,.54,(100,100,255),1,cv2.LINE_AA)

        if r.get("target") is None:
            tx="--"
        else:
            tx=f"({r['target'][0]:.1f}, {r['target'][1]:.1f})"

        cv2.putText(out,f"TARGET V2 {tx}",(10,y0+60),cv2.FONT_HERSHEY_SIMPLEX,.54,(120,230,120),1,cv2.LINE_AA)
        cv2.putText(out,f"{r.get('mode','')} | {r.get('reason','')}",(10,y0+90),cv2.FONT_HERSHEY_SIMPLEX,.45,(190,190,190),1,cv2.LINE_AA)
        cv2.putText(out,"AMARILLO = centro de trayectoria | X = objetivo",(10,y0+118),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,210,255),1,cv2.LINE_AA)
        cv2.putText(out,"SHADOW: no simula el movimiento futuro",(10,y0+145),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,210,255),1,cv2.LINE_AA)

        vw.write(out)
        i+=1

    cap.release()
    vw.release()
    f.close()

    print(f"frames={i}")
    print(f"target_off_selected_line={off_line}")
    print(f"frames_without_target={no_target}")
    print(f"max_target_jump_px={max_jump:.2f}")
    print(outavi)
    print(outcsv)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps",type=float,default=20.0)
    ap.add_argument("--avi",default="nuevo_code_v2_manual.avi")
    ap.add_argument("--csv",default="nuevo_code_v2_manual.csv")
    a=ap.parse_args()
    run(a.video,a.avi,a.csv,a.fps)

if __name__=="__main__":
    main()
