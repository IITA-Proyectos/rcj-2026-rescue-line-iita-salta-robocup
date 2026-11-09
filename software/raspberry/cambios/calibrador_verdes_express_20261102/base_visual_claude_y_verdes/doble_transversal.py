"""Candidato OFFLINE. No se importa desde main ni gobierna motores.

Conserva el clasificador previo; agrega evidencia de par completo desde fila 50.
Sólo convierte una marca que el detector previo ya aceptó, con dos observaciones
compatibles. Nunca inicia una marca desde cero; puede sostener un doble ya
confirmado con los mismos límites de persistencia del detector anterior.
"""
import cv2
import numpy as np

VERSION = 'DOBLE-TRANSVERSAL-CANDIDATO-2'


class EarlyDouble:
    def __init__(self, legacy, lower, upper):
        self.legacy=legacy
        self.lower=np.array(lower,np.uint8)
        self.upper=np.array(upper,np.uint8)
        self.reset()

    def reset(self):
        self.last_time=None
        self.last_pair=None
        self.hits=0
        self.early_started=None
        self.early_last_seen=None

    def evidence(self, lab, black):
        reference=cv2.moments(black[90:])
        if not reference['m00']:return None
        cx=reference['m10']/reference['m00']
        color=cv2.inRange(lab,self.lower,self.upper)
        mask=color.copy()
        mask[:50]=0
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        # Main recorta el negro por encima de 60: reconstruir SOLO para
        # comprobar la transversal, sin modificar la mascara de seguimiento.
        full_black=cv2.inRange(cv2.cvtColor(lab,cv2.COLOR_LAB2BGR),
                               np.array([0,0,0]),np.array([90,90,90]))
        full_black[60:]=black[60:]
        # Un verde oscuro tambien puede satisfacer BGR<=90. No cuenta como
        # cinta negra para confirmar otro verde.
        full_black[color>0]=0
        _,_,stats,centers=cv2.connectedComponentsWithStats(mask)
        sides={-1:[],1:[]}
        for stat,center in zip(stats[1:],centers[1:]):
            x,y,w,h,area=map(int,stat)
            if area<120 or w<6 or h<5 or y+h<73:continue
            side=-1 if center[0]<cx-5 else 1 if center[0]>cx+5 else 0
            if not side:continue
            above=max(30,y-15)
            ratio=(np.count_nonzero(full_black[above:y,x:x+w])/float((y-above)*w)) if y>above else 0.
            # MISMO descarte del detector previo: negro encima de CADA
            # cuadrado. Un verde por arriba de la transversal no habilita par.
            if ratio<=.32:continue
            sides[side].append(dict(x=x,y=y,w=w,h=h,area=area,above=ratio,center=center))
        for left in sides[-1]:
            for right in sides[1]:
                x0,x1=left['x']+left['w'],right['x']
                y0=max(left['y'],right['y'],60)
                y1=min(left['y']+left['h'],right['y']+right['h'])
                if x1-x0<6 or y1-y0<5:continue
                if abs(left['y']-right['y'])>20:continue
                separator=float(np.mean(black[y0:y1,x0:x1]>0))
                if separator<.60:continue
                return dict(centers=[left['center'].tolist(),right['center'].tolist()],
                            separator=separator,above=[left['above'],right['above']],
                            areas=[left['area'],right['area']])
        return None

    def step(self, raw_state, lab, black, now):
        if self.last_time is not None and (now-self.last_time>.20 or now<=self.last_time):
            self.hits=0
            self.last_pair=None
            self.early_started=None
            self.early_last_seen=None
        pair=self.evidence(lab,black)
        compatible=(pair is not None and self.last_pair is not None
                    and np.max(np.linalg.norm(np.array(pair['centers'])-
                                              np.array(self.last_pair['centers']),axis=1))<=15)
        self.hits=self.hits+1 if compatible else 1 if pair else 0
        self.last_pair=pair
        self.last_time=now
        old=self.legacy.step(raw_state,lab,black,now)
        # La memoria nueva es independiente: nunca adelantar el reloj del
        # detector previo ni acortar un doble que antes se sostenia bien.
        if old==3:return 3
        if old not in (0,1,2):return old
        if self.early_started is not None:
            recent=(old in (1,2) or (self.early_last_seen is not None and now-self.early_last_seen<=.18))
            if now-self.early_started<=1.0 and recent:
                if old in (1,2):self.early_last_seen=now
                return 3
            self.early_started=None
            self.early_last_seen=None
        if old not in (1,2):return old
        if pair:
            if self.hits>=2:
                self.early_started=now
                self.early_last_seen=now
                return 3
            # Sólo un cuadro con dos manchas: esperar otra observación en vez
            # de enviar un simple irreversible. No se espera si sólo hay una.
            return 0
        return old
