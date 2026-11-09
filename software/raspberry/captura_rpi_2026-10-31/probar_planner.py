# -*- coding: utf-8 -*-
"""
probar_planner.py - Probar el seguidor de ruta y compararlo con el metodo actual.

USO
---
  python probar_planner.py video_4.avi        sobre un video grabado
  python probar_planner.py camara             en vivo con la camara (en la Pi)
  python probar_planner.py video_4.avi --sin-ventana    solo numeros (headless/SSH)
  python probar_planner.py video_4.avi --guardar        graba comparacion.avi

Si el OpenCV instalado es el "headless" (sin ventanas), el script se da cuenta
solo y pasa a grabar comparacion.avi en vez de fallar.

QUE MUESTRA
-----------
  Izquierda : lo que ve el metodo ACTUAL (su ROI y su angulo)
  Derecha   : la RUTA que arma el planner y su angulo
  Abajo     : los dos angulos y la velocidad sugerida

CONTROLES (con ventana)
  espacio = pausa/sigue      flecha der = un frame       q = salir
  g / G   = baja/sube GANANCIA en vivo

QUE MIRAR
---------
 1. Con la linea CENTRADA los dos tienen que dar cerca de 0.
 2. Con la linea a la DERECHA los dos tienen que dar NEGATIVO. Si el actual da
    positivo y el planner negativo, ese es el error de signo que buscamos.
 3. En una curva cerrada, la ruta verde tiene que seguir la cinta, no saltar al
    fondo ni a una silla.
 4. El angulo del planner tiene que moverse suave, sin saltar de golpe.
"""
import sys, os, math, time
import cv2, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seguidor_linea as SR

W, H = 160, 120
LOW = np.array([0, 0, 0]); HIGH = np.array([90, 90, 90])
_xc = np.zeros((H, W)); _yc = np.zeros((H, W))
for _i in range(H):
    for _j in range(W):
        _xc[_i][_j] = (_j - (W/2 - 1)) / (W/2)
        _yc[_i][_j] = ((H - 1) - _i) / H


def angulo_actual(f):
    """El calculo tal cual esta hoy en Main.py."""
    bm = cv2.inRange(f, LOW, HIGH); bm[:55, :] = 0
    xb = cv2.bitwise_and(_xc, _xc, mask=bm) * (1 - _yc)
    yb = cv2.bitwise_and(_yc, _yc, mask=bm)
    a = (math.atan2(np.mean(yb), np.mean(xb)) / math.pi * 180) - 90
    if int(bm.sum()) < 50000:
        a = 0.0
    return a, bm


def preparar(frame_crudo):
    f = cv2.rotate(frame_crudo, cv2.ROTATE_180)
    return cv2.resize(f, (W, H), interpolation=cv2.INTER_NEAREST)


def pintar(f, r, a_act, bm):
    izq = f.copy()
    m3 = cv2.cvtColor(bm, cv2.COLOR_GRAY2BGR); m3[:, :, 0] = 0; m3[:, :, 1] = 0
    izq = cv2.addWeighted(izq, 0.6, m3, 0.4, 0)
    cv2.line(izq, (0, 55), (W-1, 55), (0, 255, 255), 1)
    cv2.putText(izq, 'ACTUAL %+.0f' % a_act, (2, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 255, 255), 1)

    der = f.copy()
    if r.get('ok'):
        p = [(int(x), int(y)) for x, y in r['puntos']]
        for u, v in zip(p, p[1:]):
            cv2.line(der, u, v, (0, 255, 0), 2)
        for x, y in p:
            cv2.circle(der, (x, y), 1, (255, 0, 255), -1)
        mx,my=r.get('mira',(W//2,0)); cv2.circle(der,(int(mx),int(my)),4,(0,128,255),2); cv2.line(der,(W//2,H-1),(int(mx),int(my)),(255,255,0),1)
        col = (0, 255, 0)
    else:
        col = (0, 165, 255)
    
    est = 'PLANNER %+.0f' % r['angle_filtrado'] if 'angle_filtrado' in r else 'PLANNER'
    cv2.putText(der, est, (2, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.32, col, 1)
    if not r.get('ok'):
        cv2.putText(der, r.get('motivo', '')[:12], (2, H-4), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 165, 255), 1)
    return np.hstack([izq, der])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    con_ventana = '--sin-ventana' not in sys.argv
    fuente = args[0] if args else 'camara'

    cap = cv2.VideoCapture(0 if fuente == 'camara' else fuente)
    if not cap.isOpened():
        print('No pude abrir:', fuente); return 2
    if fuente == 'camara':
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    guardar = '--guardar' in sys.argv
    grabador = None
    seg = SR.Seguidor()
    n = 0; pausa = False; t_total = 0.0; discrepa = 0; comparables = 0
    print('fuente:', fuente, '| ganancia =', seg.ganancia)
    print('%6s %9s %9s %6s %5s' % ('frame', 'actual', 'planner', 'vel', 'ruta'))
    while True:
        if not pausa:
            ok, crudo = cap.read()
            if not ok:
                break
            f = preparar(crudo)
            a_act, bm = angulo_actual(f)
            t0 = time.perf_counter()
            r = seg.paso(f, ya_procesado=True)
            t_total += time.perf_counter() - t0
            a_pl = r['angle_filtrado']
            vel = SR.velocidad_sugerida(r)
            if abs(a_act) > 12 and abs(a_pl) > 12:
                comparables += 1
                if a_act * a_pl < 0:
                    discrepa += 1
            if n % 5 == 0 or (abs(a_act) > 12 and abs(a_pl) > 12 and a_act*a_pl < 0):
                marca = '  <-- SIGNO OPUESTO' if (abs(a_act) > 12 and abs(a_pl) > 12 and a_act*a_pl < 0) else ''
                print('%6d %+9.1f %+9.1f %6d %5s%s' % (n, a_act, a_pl, vel, 'si' if r.get('ok') else 'MEM', marca))
            n += 1
        if con_ventana or guardar:
            vis = pintar(f, r, a_act, bm)
            vis = cv2.resize(vis, (vis.shape[1]*4, vis.shape[0]*4), interpolation=cv2.INTER_NEAREST)
            if con_ventana:
                try:
                    cv2.imshow('actual  |  planner   (espacio=pausa  g/G=ganancia  q=salir)', vis)
                    k = cv2.waitKey(0 if pausa else 30) & 0xFF
                    if k == ord('q'): break
                    if k == ord(' '): pausa = not pausa
                    if k == ord('g'): seg.ganancia = max(0.3, seg.ganancia - 0.1); print('ganancia =', round(seg.ganancia, 2))
                    if k == ord('G'): seg.ganancia = min(2.5, seg.ganancia + 0.1); print('ganancia =', round(seg.ganancia, 2))
                except cv2.error:
                    # OpenCV headless: no hay ventanas. Se graba y se sigue.
                    print()
                    print('Este OpenCV no tiene ventanas (es el "headless").')
                    print('Cambio a grabar comparacion.avi -- abrilo con cualquier reproductor.')
                    print()
                    con_ventana = False; guardar = True
            if guardar:
                if grabador is None:
                    grabador = cv2.VideoWriter('comparacion.avi',
                                               cv2.VideoWriter_fourcc(*'MJPG'), 20.0,
                                               (vis.shape[1], vis.shape[0]))
                grabador.write(vis)
    cap.release()
    if grabador is not None:
        grabador.release()
        print('grabado: comparacion.avi')
    if con_ventana:
        try: cv2.destroyAllWindows()
        except cv2.error: pass
    print()
    print('frames: %d   costo del planner: %.2f ms/frame' % (n, 1000*t_total/max(n, 1)))
    if comparables:
        print('frames donde los dos opinan fuerte: %d   con SIGNO OPUESTO: %d (%.1f%%)'
              % (comparables, discrepa, 100.0*discrepa/comparables))
    return 0


if __name__ == '__main__':
    sys.exit(main())
