# -*- coding: utf-8 -*-
"""
LEY DE STEER - separar POSICION de RUMBO. Defecto 3.5.1 del traspaso.

QUE ARREGLA
-----------
La ley de produccion es un solo numero:

    steer = -90 * (x_target - CENTER) / (W/2)

y `x_target` se corre por DOS causas fisicamente distintas:

    e     el robot esta corrido de la cinta        -> error de POSICION
    psi   la cinta DOBLA adelante                  -> error de RUMBO

Medido (`posicion_vs_rumbo.py`): steer = -1,011*e -0,758*psi, R2 0,82, con el
reparto de varianza 47,8 / 52,2. Mitad y mitad, POR EL MISMO NUMERO, con UNA
sola ganancia, y la ley nunca ve la velocidad.

Stanley (Snider CMU-RI-TR-09-08) los separa:

    delta = psi + arctan(k*e / v)

El termino de posicion SE DIVIDE POR LA VELOCIDAD; el de rumbo no. A mas
velocidad, menos angulo por el mismo corrimiento; a menos velocidad, mas.

QUE NO ES
---------
NO es un modulo de percepcion. No elige el target, no toca la mascara, no toca
el esqueleto. Consume el dict que la candidata YA devuelve y produce un numero.
Es puro: misma entrada, misma salida, sin estado.

POR QUE d_eje NO LO BLOQUEA
---------------------------
`d_eje` -la distancia del eje de rotacion al punto del piso de la fila 119- esta
sin medir y tiene suspendido a T4. Pure pursuit lo necesita, porque el bearing
al target se toma DESDE el eje de rotacion.

Stanley no. `d_eje` es un corrimiento a lo largo de Z, y:
  * la tangente del camino (psi) es invariante a una traslacion en Z;
  * el cross-track en la fila mas baja (e) es una coordenada X, ortogonal a Z.
Ninguno de los dos cambia. Por eso esta tarea se puede hacer con la Pi apagada.

LO QUE SIGUE SIN CALIBRAR, Y SE REPORTA EN BANDA
------------------------------------------------
El HFOV. `psi` en grados verdaderos depende de el, asi que todo va para
45 / 60 / 75 y si el veredicto cambia de signo adentro de esa banda, no hay
conclusion.

`v_h = 9,0` SI esta medido: `birdeye.py`, R2 0,982-0,999 en 9 de 11 videos.
"""

import math

W, H = 160, 120
CENTER = (W - 1) / 2.0

V_H = 9.0                # fila del horizonte, medida en birdeye.py
FILA_BASE = 119.0        # la fila mas cercana que ve el robot; Z_rel(119) = 1
HFOV_NOMINAL = 60.0
HFOV_BANDA = (45.0, 60.0, 75.0)

# Arco de suelo sobre el que se estima la tangente del camino, en unidades de
# Z_rel (1,0 = tan lejos como la fila 119). Corto a proposito: psi es la
# tangente LOCAL, no el rumbo promedio hasta el lookahead. Se barre en banda.
ARCO_PSI = 0.60
ARCO_PSI_BANDA = (0.30, 0.45, 0.60, 0.90, 1.30)

# Piso de la velocidad normalizada. Coincide con FACTOR_MIN de vision_linea.py:
# la vision nunca manda menos que 0,55 de la base, asi que dividir por algo mas
# chico seria extrapolar fuera del rango que el robot puede recibir.
V_MIN = 0.55


def f_px(hfov=HFOV_NOMINAL):
    """Distancia focal en pixeles para un campo visual horizontal dado."""
    return (W / 2.0) / math.tan(math.radians(hfov / 2.0))


def suelo(u, v, hfov=HFOV_NOMINAL):
    """(X, Z) en el suelo, RELATIVOS: Z(fila 119) = 1,0.

    Modelo de suelo plano validado en birdeye.py:  Z = k/(v - v_h).
    La escala absoluta no se conoce y no hace falta: se absorbe en la ganancia
    `k` de la ley. Lo que si es real es la FORMA, y con ella el hecho de que un
    pixel arriba vale decenas de veces mas suelo que uno abajo.
    """
    Z = (FILA_BASE - V_H) / max(v - V_H, 1e-6)
    X = (u - CENTER) * Z / f_px(hfov)
    return X, Z


def errores(res, hfov=HFOV_NOMINAL, arco=ARCO_PSI):
    """De un dict de la candidata saca (e, psi_deg) o (None, None).

    e        posicion lateral de la CINTA respecto del robot, en el suelo.
             Negativa = la cinta entra por la izquierda = el robot esta corrido
             a la derecha. Se toma en el punto de ENTRADA (`start`), que es lo
             mas cerca que la camara ve, o sea el cross-track de Stanley.

    psi_deg  rumbo de la tangente del camino, en grados verdaderos. Positivo =
             el camino se va a la DERECHA adelante. Se estima sobre un arco de
             suelo FIJO desde el start -no sobre un numero de pixeles-, porque
             la tangente es local y un criterio en pixeles cambia de escala
             fisica segun la fila.
    """
    st = res.get("start")
    path = res.get("path")
    if st is None:
        return None, None

    # El cross-track se mide en la CINTA, no en el nodo del esqueleto.
    #
    # `start` es un nodo del eje medial en la fila mas baja, y con la camara
    # casi horizontal la cinta ocupa ~65 px de ancho ahi (44 % del cuadro,
    # medido en birdeye.py). El eje medial de una franja tan ancha no pasa por
    # su centro. Medido sobre 13.257 frames: |start_x - centro real| da p50 14,
    # p90 35 y max 152 px, con el 58,5 % de los frames arriba de 10 px.
    #
    # Eso sesga `e` de forma masiva: 35 px son ~0,25 de cross-track en el suelo,
    # que con la ganancia calibrada valen ~48 grados de comando POR UN ERROR
    # QUE NO EXISTE. Es un defecto que introduje al construir `e` sobre el
    # start; la ley vieja no lo tiene porque usa el target.
    #
    # `entrada` es el centroide de la componente en sus 3 filas mas bajas: la
    # posicion lateral de la cinta en el punto del camino mas cercano al robot,
    # que es la definicion de cross-track. Si no esta -un dict viejo, otro
    # modo-, se cae al start y se sigue como antes.
    ent = res.get("entrada") or st
    X0, Z0 = suelo(ent[0], ent[1], hfov)
    e = X0
    # la tangente se sigue midiendo sobre el camino, que arranca en el start
    Xp, Zp = suelo(st[0], st[1], hfov)

    if not path or len(path) < 2:
        # sin camino no hay tangente; se cae al chord start->target, que es lo
        # unico que queda. Se marca devolviendo psi con la misma convencion.
        t = res.get("target")
        if t is None:
            return e, None
        X1, Z1 = suelo(t[0], t[1], hfov)
        dX, dZ = X1 - Xp, Z1 - Zp
        if abs(dZ) < 1e-9 and abs(dX) < 1e-9:
            return e, None
        return e, math.degrees(math.atan2(dX, dZ))

    # tangente sobre un arco de suelo fijo, recorriendo el camino desde el start
    P = [suelo(x, y, hfov) for x, y in path]
    acum = 0.0
    j = 0
    for i in range(1, len(P)):
        acum += math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1])
        j = i
        if acum >= arco:
            break
    if j == 0:
        return e, None
    dX = P[j][0] - P[0][0]
    dZ = P[j][1] - P[0][1]
    if abs(dZ) < 1e-9 and abs(dX) < 1e-9:
        return e, None
    return e, math.degrees(math.atan2(dX, dZ))


def steer_actual(res):
    """La ley de HOY, bit a bit igual que vision_linea._angulo_de.

    Se reimplementa aca a proposito y se verifica contra el original frame a
    frame (`fidelidad`): si el espia no reproduce la salida exacta, el A/B no
    vale nada.
    """
    t = res.get("target")
    if t is None:
        return None
    a = -90.0 * (float(t[0]) - CENTER) / (W / 2.0)
    return max(-90.0, min(90.0, a))


def steer_stanley(res, v_norm=1.0, k=1.0, k_psi=1.0, g=1.0,
                  hfov=HFOV_NOMINAL, arco=ARCO_PSI):
    """delta = -g * ( k_psi*psi + atan(k*e / max(v,V_MIN)) ), saturado a +-90.

    El signo global es negativo porque la convencion del protocolo es POSITIVO
    A LA IZQUIERDA, y tanto `e` como `psi` son positivos hacia la derecha.

    `g` es UNA ganancia global de escala, y existe por una razon concreta: la
    salida no es un angulo fisico que la Teensy vaya a ejecutar en grados, es
    una consigna en [-90,+90] cuya autoridad total ya esta validada en pista.
    Separar posicion de rumbo es REPARTIR esa autoridad entre dos terminos, no
    recortarla. `g` se calibra una sola vez para conservarla y despues no se
    toca.
    """
    c = componentes(res, v_norm, k, k_psi, g, hfov, arco)
    return None if c is None else c["delta"]


def componentes(res, v_norm=1.0, k=1.0, k_psi=1.0, g=1.0,
                hfov=HFOV_NOMINAL, arco=ARCO_PSI):
    """Los dos terminos por separado, para telemetria y para el A/B."""
    e, psi = errores(res, hfov, arco)
    if e is None or psi is None:
        return None
    v = max(float(v_norm), V_MIN)
    t_pos = -g * math.degrees(math.atan(k * e / v))
    t_psi = -g * k_psi * psi
    d = t_pos + t_psi
    return dict(e=e, psi=psi, v=v, t_pos=t_pos, t_psi=t_psi,
                delta=max(-90.0, min(90.0, d)), delta_sin_sat=d)
