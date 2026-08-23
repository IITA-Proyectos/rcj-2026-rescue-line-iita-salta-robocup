# -*- coding: utf-8 -*-
"""
parche_planner.py - Enchufa mejoras al main.py que corre en la Raspberry, con
                    backup, reversible, y todas apagadas por defecto.

POR QUE UN PARCHE Y NO UN main.py NUEVO
---------------------------------------
El main.py que corre en la Pi vive FUERA de git y no es el del repo: importa
camthreader, recorta en la fila 60, y -esto es lo importante- NO TIENE rutina de
linea perdida, que el del repo si tiene. Reescribirlo entero es la forma mas
facil de perder algo sin darse cuenta.

USO
---
    python3 parche_planner.py             aplica (deja main.py.bak)
    python3 parche_planner.py /ruta/main.py    si esta en otro lado
    python3 parche_planner.py --revertir  vuelve atras
    python3 parche_planner.py --ver       muestra si entraria, sin tocar nada

LOS INTERRUPTORES, todos por variable de entorno y todos apagados por defecto
----------------------------------------------------------------------------
    ROI=auto      recorta en el horizonte real en vez de la fila 60 fija
    RECUP=1       al perder la linea, no sigue derecho
    RETROCEDER=1  al perder la linea, RETROCEDE un paso y vuelve a mirar
                  (necesita RECUP=1; necesita el firmware con LINEA_PERDIDA_GS)
    CTRL=lineal   reemplaza el atan2 por dos terminos de ganancia constante
    PLANNER=1     el seguidor de trazo maneja
    PLANNER=2     hibrido: el centroide manda, el trazo entra donde se satura
    GRABAR=ruta   graba video con lo que el robot vio y lo que decidio

    K_CERCA, K_LEJOS   ganancias del control lineal (40 y 40)
    RECUP_ANG          cuanto gira buscando la linea (75 grados)
    SATURA_DESDE       desde que angulo el hibrido le pasa el volante (70)

Sin ninguna de esas, el parche aplicado NO cambia el comportamiento.

MEDIDO EL 2026-08-22 SOBRE 6772 FRAMES DE PISTA
-----------------------------------------------
    control            cruces/s   <10px   desvio   linea perdida
    atan2 (original)     1,88      42%    20,0 px     17,9 %
    planner              1,07      37%    19,4        24,8 %
    lineal K=40          1,14      22%    26,1        33,9 %
    lineal K=70          1,62      37%    21,1        22,6 %

Cuatro leyes de control distintas, todas en la misma banda: el limite NO estaba
en el controlador. Lo que si aparecio mirando frame por frame es que cuando la
linea se va por un costado, main.py manda angle = 0 -o sea seguir derecho- y ahi
el robot se va de la pista. Esa es la rutina que falta, y es RECUP=1.
"""
import io
import os
import sys


def _buscar_main():
    """El main del robot al lado de este script. En Linux las mayusculas
    importan: en la Pi se llama main.py y en el repo Main.py."""
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return os.path.abspath(a)
    aca = os.path.dirname(os.path.abspath(__file__))
    for n in os.listdir(aca):
        if n.lower() == "main.py":
            return os.path.join(aca, n)
    return os.path.join(aca, "main.py")


RUTA = _buscar_main()

# ============================================================================
#  BLOQUE 1 - va despues de los imports de main.py
# ============================================================================
BLOQUE_IMPORT = '''
# ================== MEJORAS DE SEGUIMIENTO (parche IITA) ==================
# Todo apagado por defecto: sin las variables de entorno el robot se comporta
# EXACTAMENTE como antes.
_MODO = os.environ.get("PLANNER", "0")
USAR_PLANNER = _MODO in ("1", "2")
MODO_HIBRIDO = _MODO == "2"
RUTA_VIDEO   = os.environ.get("GRABAR", "")
ROI_MODO     = os.environ.get("ROI", "60")
CTRL         = os.environ.get("CTRL", "atan2")
RECUP        = os.environ.get("RECUP", "0") == "1"
# RETROCEDER AL PERDER LA LINEA (idea de Benjamin). En vez de girar buscando a
# ciegas, se le avisa al firmware -green_state = 4- y el robot RETROCEDE un paso
# corto y vuelve a mirar. La linea no desaparece por casualidad: desaparece
# porque el robot se paso, y un segundo antes la tenia abajo. Retroceder rehace
# el camino; girar a ciegas puede alejarlo mas. Y cuando reaparece, aunque sea
# en un borde, el control normal gira hacia ella solo: el "alinearse" sale gratis.
RETROCEDER   = os.environ.get("RETROCEDER", "0") == "1"
GS_LINEA_PERDIDA = 4
K_CERCA      = float(os.environ.get("K_CERCA", "40"))
K_LEJOS      = float(os.environ.get("K_LEJOS", "40"))
RECUP_ANG    = float(os.environ.get("RECUP_ANG", "75"))
SATURA_DESDE = float(os.environ.get("SATURA_DESDE", "70"))
AREA_MIN_LINEA = float(os.environ.get("AREA_MIN", "200"))   # px; ver _solo_mi_linea

_ult_lado = 0.0        # +1 la linea estaba a la derecha, -1 a la izquierda
_frames_sin = 0        # cuantos frames seguidos sin verla


def _fila_horizonte(frame_bgr, minimo=25, maximo=60):
    """Primera fila donde termina el SALON y empieza el piso de la pista.

    main.py recorta con black_mask[:60, :] = 0, un numero fijo. Medido sobre las
    corridas del 2026-08-22: el salon termina en la fila 35-40, asi que el
    recorte fijo tira 17-20 FILAS DE PISTA -casi un tercio del ROI utilizable, y
    justamente las mas lejanas, las unicas que sirven para anticipar-.

    Mira DOS cosas, no una: que la fila sea razonablemente clara (>110) y que
    sea PAREJA (desvio < 55). El salon es oscuro y texturado -muebles, sillas,
    patas-; el piso de la pista es claro y uniforme. La textura los separa mejor
    que el brillo solo, que es lo que fallaba en la primera version (cortaba en
    la fila 54 y recuperaba 5 filas en vez de 20).

    Validado a ojo sobre seis frames repartidos: la fila elegida cae en el borde
    salon/piso en los seis, y lo que se recupera es pista con cinta. Confundir
    negro con linea ya paso dos veces este mismo dia, asi que la validacion
    visual no es opcional.
    """
    try:
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(float)
        brillo = g.mean(axis=1)
        textura = g.std(axis=1)
        for y in range(maximo + 20):
            if brillo[y] > 110 and textura[y] < 55 and brillo[y:y + 10].mean() > 110:
                return max(minimo, y)
    except Exception:
        pass
    return maximo


def _solo_mi_linea(mask):
    """Deja SOLO la mancha que toca al robot; el resto del negro se descarta.

    En el ROI caen otros tramos negros de la pista -otra cinta cruzando, juntas
    del piso, cables- que no son la linea que el robot esta siguiendo. Medido:
    en el 38% de los frames hay algo asi, y aunque casi siempre es inofensivo,
    en el 2,2% corre el centroide lejano hasta 1,51 (de un extremo al otro).
    La linea seguible es, por definicion, la conectada con la que esta debajo.
    Cuesta 0,09 ms por frame.
    """
    try:
        num, et, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
        fila = et[mask.shape[0] - 2]
        suyas = np.unique(fila[fila > 0])
        # SI NADA TOCA AL ROBOT, DEVOLVER VACIO, NO LA MASCARA ENTERA.
        # Devolver la mascara completa era el peor fallback posible: cuando el
        # robot se sale a un piso de madera o al salon, el ruido de la veta pasa
        # el filtro, _error_lateral encuentra sus 20 pixeles y devuelve un
        # numero -basura, pero un numero-, asi que la recuperacion de linea
        # NUNCA se activa. Medido el 2026-08-22 en el video a.avi: en los cinco
        # episodios de salida la componente que toca al robot tiene area 0, y el
        # overlay decia "centroide" en vez de "buscando" durante los 3,7 s.
        if not len(suyas):
            return np.zeros_like(mask)
        # Y una mancha demasiado chica tampoco es una linea: es ruido pegado al
        # borde. Umbral sacado de los datos, no a ojo: con 200 px se marcan como
        # "sin linea" el 100% de los frames de salida y solo el 11% de los
        # normales, donde la mediana del area es 3080 px.
        area = max(int(st[i, cv2.CC_STAT_AREA]) for i in suyas)
        if area < AREA_MIN_LINEA:
            return np.zeros_like(mask)
        return (np.isin(et, suyas) * 255).astype(np.uint8)
    except Exception:
        return mask


def _error_lateral(mask, y0, y1):
    """Donde esta la cinta entre las filas y0 e y1, de -1 (izquierda) a +1."""
    banda = mask[y0:y1, :]
    xs = np.nonzero(banda)[1]
    if len(xs) < 20:
        return None
    return (float(xs.mean()) - (mask.shape[1] - 1) / 2.0) / (mask.shape[1] / 2.0)


def _angulo_lineal(mask, corte):
    """Dos terminos lineales. El atan2 que usa main.py no es un controlador, es
    un cambio de coordenadas, y su ganancia esta INVERTIDA. Medido sobre 3221
    frames de pista:

        desvio       angulo medio   ganancia
        0 - 5 px        19,3 gr      1,04 gr/px
        5 - 10 px       26,9         1,74
        30 - 45 px      55,6         0,29
        45 - 80 px      57,5        -0,61    <- deja de corregir

    A UN pixel del centro ya corrige 1,45 grados -por eso oscila- y a 45 px no
    corrige mas que a 30 -por eso, cuando se fue, no vuelve-.

        e_cerca  cuan corrido esta AHORA   -> lo endereza
        e_lejos  para donde va la cinta    -> lo anticipa
    Los dos con ganancia CONSTANTE (K/80 grados por pixel).
    """
    mask = _solo_mi_linea(mask)
    e_pos = _error_lateral(mask, 105, 119)
    if e_pos is None:
        e_pos = _error_lateral(mask, corte, 120)
        if e_pos is None:
            return None
    # RUMBO = la DIFERENCIA entre donde esta la linea lejos y donde esta cerca.
    # NO es la posicion lejana: eso seria medir posicion otra vez, un poco mas
    # arriba, y es el error que tenia la primera version -los dos terminos eran
    # posicion, correlacionados, asi que el controlador tenia UNO SOLO-.
    #
    # Medido el 2026-08-22 sobre hist.avi, y es el hallazgo que faltaba:
    #   el robot esta CENTRADO (|pos| < 12 px) el 40% del tiempo,
    #   pero de esos frames el 57% tiene el RUMBO torcido (>20 px),
    #   con una mediana de 28,6 px, que es casi un ancho de cinta.
    # O sea que se para sobre la linea apuntando para otro lado, y desde ahi se
    # vuelve a ir. Observado en pista por Benjamin: "no se reacomoda con el
    # centro de la linea y queda chueco hasta que en algun giro la pierde".
    #
    # Las cinco leyes de control probadas ese dia eran TODAS de posicion pura.
    # Ninguna miraba el rumbo, y por eso ninguna le gano al atan2 original.
    lejos = _error_lateral(mask, corte, min(corte + 18, 96))
    if lejos is None:
        # sin banda lejana no hay rumbo medible: solo posicion, con todo el peso
        return max(-90.0, min(90.0, -(K_CERCA + K_LEJOS) * e_pos))
    e_rumbo = lejos - e_pos
    return max(-90.0, min(90.0, -(K_CERCA * e_pos + K_LEJOS * e_rumbo)))


_seguidor = None
if USAR_PLANNER:
    try:
        from seguidor_linea import Seguidor
        _seguidor = Seguidor()
        print("[PLANNER] encendido")
    except Exception as _e:
        print("[PLANNER] no se pudo cargar (%s): sigo con el metodo de siempre" % _e)
        USAR_PLANNER = False

print("[PARCHE] ROI=%s CTRL=%s RECUP=%s PLANNER=%s" % (ROI_MODO, CTRL, RECUP, _MODO))

_video = None
_video_n = 0


def _cerrar_video():
    """cv2.VideoWriter escribe el indice del AVI recien en release(). Sin esto,
    cortando con Ctrl-C -que es como se corta siempre- el archivo puede no
    abrir. atexit corre igual con KeyboardInterrupt."""
    global _video
    if _video is not None:
        try:
            _video.release()
            print("[GRABAR] cerrado: %d frames en %s" % (_video_n, RUTA_VIDEO))
        except Exception:
            pass
        _video = None


import atexit
atexit.register(_cerrar_video)


def _grabar(frame_bgr, ang_viejo, ang_nuevo, r, quien, corte):
    """Una imagen por frame: lo que el robot vio Y lo que decidio.
    Nunca levanta una excepcion hacia el lazo de vision."""
    global _video, _video_n
    if not RUTA_VIDEO:
        return
    try:
        vis = cv2.resize(frame_bgr, (320, 240), interpolation=cv2.INTER_NEAREST)
        cv2.line(vis, (0, corte * 2), (319, corte * 2), (0, 255, 255), 1)
        if r is not None and r.get("mascara") is not None:
            mk = cv2.cvtColor(cv2.resize(r["mascara"], (320, 240),
                              interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        else:
            m = cv2.inRange(frame_bgr, lower_black, upper_black)
            m[:corte, :] = 0
            mk = cv2.cvtColor(cv2.resize(_solo_mi_linea(m), (320, 240),
                              interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        if r is not None and r.get("puntos"):
            p = [(int(x * 2), int(y * 2)) for x, y in r["puntos"]]
            for u, v in zip(p, p[1:]):
                cv2.line(vis, u, v, (0, 255, 0), 2)
            for x, y in p:
                cv2.circle(mk, (int(x * 2), int(y * 2)), 2, (0, 0, 255), -1)
        cv2.putText(vis, "viejo %+.0f" % ang_viejo, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        if ang_nuevo is not None:
            cv2.putText(vis, "manda %+.0f" % ang_nuevo, (4, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        cv2.putText(vis, quien, (4, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 128, 255) if quien == "buscando" else (0, 255, 0), 1)
        cv2.putText(mk, "mascara  corte f%d" % corte, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 128, 0), 1)
        vis = np.hstack([vis, mk])
        if _video is None:
            _video = cv2.VideoWriter(os.path.expanduser(RUTA_VIDEO),
                                     cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (640, 240))
            print("[GRABAR] escribiendo en %s" % RUTA_VIDEO)
        _video.write(vis)
        _video_n += 1
    except Exception as _e:
        print("[GRABAR] se apaga por error: %s" % _e)
        globals()["RUTA_VIDEO"] = ""


# =========================================================================
#  LINEA PERDIDA DE VERDAD, y el log por frame
#
#  EL BUG QUE ESTO MIDE:  min_line_size = 1 sobre una mascara de 0/255.
#  np.sum(black_mask) < 1 solo se cumple con CERO pixeles negros en todo el
#  ROI, y con el salon en cuadro -zocalo, patas de mesa, sombras- eso casi
#  nunca pasa. Medido sobre los 13.900 frames grabados el 22-ago:
#
#      la rama de perdida se dispara      5,32 % de los frames
#      la linea esta realmente perdida    20,9 %
#
#  Y medido como RECALL, que es la metrica que corresponde: de los frames en
#  que la linea realmente no esta, el robot lo declara en el 13,5 % en
#  hist.avi y el 40,1 % en como_esta.avi. O sea que se entera de una de cada
#  siete perdidas. En las otras seis calcula un atan2 confiado sobre el
#  mobiliario y maneja a 40.
#
#  ESTO NO CAMBIA EL BYTE QUE SE MANDA. A proposito. El criterio nuevo entra
#  primero como INSTRUMENTACION: se loguea y no se actua. Encender la
#  maniobra -green_state=4, que el firmware rutea a retroceder- sin un solo
#  dato de pista sobre ella seria cambiar dos cosas a la vez, y el 22-ago ya
#  se perdieron dos corridas por eso. Con una corrida se sabe si los
#  episodios se sostienen, y recien ahi se decide la maniobra.
#
#  Criterio: no existe componente conexa que toque la ultima fila del ROI con
#  area >= AREA_PERDIDA. Medido en replay: recall 98,4-98,5 % con 0,9 % de
#  falsos positivos, contra el 13,5-40,1 % de hoy.
# =========================================================================
AREA_PERDIDA = float(os.environ.get("AREA_PERDIDA", "30"))
RUTA_LOG     = os.environ.get("LOG", "")
_log_f = None
_log_n = 0
_log_t0 = None


def _perdida_conexa(mask):
    """(perdida, area_de_mi_mancha). `mask` es el ROI ya recortado.

    'Mi linea' es la componente conexa que TOCA LA ULTIMA FILA: es la unica
    que puede estar debajo del robot. Una mancha flotando arriba es el salon.
    Devuelve area 0 si no hay ninguna que toque el fondo.
    """
    try:
        if mask is None or mask.size == 0:
            return True, 0.0
        n, et, est, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
        if n <= 1:
            return True, 0.0
        fondo = et[-1, :]
        mejor = 0.0
        for k in range(1, n):
            if np.any(fondo == k):
                a = float(est[k, cv2.CC_STAT_AREA])
                if a > mejor:
                    mejor = a
        return (mejor < AREA_PERDIDA), mejor
    except Exception:
        # ante cualquier problema, NO declarar perdida: el criterio nuevo no
        # decide nada todavia, y un falso positivo ensucia la medicion.
        return False, -1.0


def _log_frame(mask_roi, ang_crudo, ang_enviado, green_state, silver):
    """Una fila por frame, al lado del AVI. Numero de frame, reloj monotonico,
    angulo crudo y enviado, suma de mascara, area de mi mancha, y si el
    criterio NUEVO habria declarado perdida.

    POR QUE EXISTE: el 22-ago no quedo NINGUNA linea de tiempo del lado de la
    Pi. Cada numero en segundos hubo que reconstruirlo de un MJPEG cuyo fps
    declarado (20,0) era falso -el VideoWriter lo tiene fijo-, y el enganche
    video-telemetria hubo que hacerlo por correlacion: de 60 pares posibles
    engancho UNO. Con esto, el enganche es por numero de frame y el fps sale
    del reloj, no de una constante.
    """
    global _log_f, _log_n, _log_t0
    if not RUTA_LOG:
        return
    try:
        if _log_f is None:
            _log_f = open(os.path.expanduser(RUTA_LOG), "w")
            _log_f.write("frame,t_mono,ang_crudo,ang_enviado,suma_mask,"
                         "area_mancha,perdida_nueva,green_state,silver\\n")
            _log_t0 = time.monotonic()
            import atexit
            atexit.register(_cerrar_log)
        perdida, area = _perdida_conexa(mask_roi)
        _log_f.write("%d,%.4f,%.2f,%d,%d,%.0f,%d,%d,%d\\n" % (
            _log_n, time.monotonic() - _log_t0, float(ang_crudo),
            int(round(ang_enviado)), int(np.sum(mask_roi) // 255) if mask_roi is not None else -1,
            area, 1 if perdida else 0, int(green_state), 1 if silver else 0))
        _log_n += 1
        if _log_n % 100 == 0:
            _log_f.flush()
    except Exception as _e:
        print("[LOG] se apaga por error: %s" % _e)
        globals()["RUTA_LOG"] = ""


def _cerrar_log():
    global _log_f
    try:
        if _log_f is not None:
            _log_f.flush()
            _log_f.close()
            dur = time.monotonic() - _log_t0 if _log_t0 else 0
            print("[LOG] %d frames en %.1f s = %.1f fps REALES" % (
                _log_n, dur, (_log_n / dur) if dur > 0 else 0))
            _log_f = None
    except Exception:
        pass
# =========================================================================
'''

ANCLA_IMPORT = "import threading\nimport queue"

ANCLA_GLOBAL = "def main():\n    global estado, silver_line"
NUEVO_GLOBAL = "def main():\n    global estado, silver_line, _ult_lado, _frames_sin"

# ============================================================================
#  BLOQUE 2 - el calculo del angulo
# ============================================================================
_CUERPO = [
    '            green_state = 0',
    '            x_resultant = np.mean(x_black)',
    '            y_resultant = np.mean(y_black)',
    '            angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90',
    '            speed = 40',
    '',
    '            # ================= PARCHE IITA =================',
    '            # 1. ROI: recortar en el horizonte real en vez de la fila 60.',
    '            _corte = 60',
    '            if ROI_MODO == "auto":',
    '                _corte = _fila_horizonte(frame_resized)',
    '                if _corte < 60:',
    '                    black_mask = cv2.inRange(frame_resized, lower_black, upper_black)',
    '                    black_mask[:_corte, :] = 0',
    '                    x_black = cv2.bitwise_and(x_com, x_com, mask=black_mask)',
    '                    x_black *= (1 - y_com)',
    '                    y_black = cv2.bitwise_and(y_com, y_com, mask=black_mask)',
    '                    x_resultant = np.mean(x_black)',
    '                    y_resultant = np.mean(y_black)',
    '                    angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90',
    '',
    '            _ang_viejo = angle',
    '            _quien = "centroide"',
    '            _r = None',
    '',
    '            # 2. CONTROL: dos terminos de ganancia constante.',
    '            if CTRL == "lineal":',
    '                _al = _angulo_lineal(black_mask, _corte)',
    '                if _al is not None:',
    '                    angle = _al',
    '                    _quien = "lineal"',
    '',
    '            # 3. LINEA PERDIDA. Lo que hace main.py hoy es angle = 0, o sea',
    '            #    SEGUIR DERECHO, y es el peor valor posible: la linea no',
    '            #    desaparece por casualidad, desaparece porque se fue por un',
    '            #    costado. Justo ahi el robot endereza y se va de la pista.',
    '            if RECUP:',
    '                _mm = _solo_mi_linea(black_mask)',
    '                _e = _error_lateral(_mm, 100, 120)',
    '                if _e is None:',
    '                    _e = _error_lateral(_mm, _corte, 120)',
    '                if _e is not None:',
    '                    _frames_sin = 0',
    '                    if abs(_e) > 0.15:',
    '                        _ult_lado = 1.0 if _e > 0 else -1.0',
    '                else:',
    '                    _frames_sin += 1',
    '                    if RETROCEDER:',
    '                        # avisarle al firmware que retroceda un paso corto.',
    '                        # El angulo se manda en 0: durante el retroceso no',
    '                        # tiene sentido pedir giro, y ademas el case 4 del',
    '                        # firmware no lo usa.',
    '                        green_state = GS_LINEA_PERDIDA',
    '                        angle = 0',
    '                        _quien = "retrocede"',
    '                    elif _ult_lado != 0.0:',
    '                        # girar hacia donde estaba, cada vez mas fuerte',
    '                        _k = min(1.0, 0.4 + 0.1 * _frames_sin)',
    '                        angle = -_ult_lado * RECUP_ANG * _k',
    '                        _quien = "buscando"',
    '',
    '            # 4. PLANNER, si se pidio.',
    '            if USAR_PLANNER:',
    '                try:',
    '                    _r = _seguidor.paso(frame_resized, ya_procesado=True)',
    '                    if not MODO_HIBRIDO:',
    '                        angle = _r["angle_filtrado"]',
    '                        _quien = "planner"',
    '                    elif _r.get("ok") and abs(_ang_viejo) >= SATURA_DESDE:',
    '                        angle = _r["angle_filtrado"]',
    '                        _quien = "planner*"',
    '                except Exception as _e2:',
    '                    print("[PLANNER] error, sigo con el centroide: %s" % _e2)',
    '                    _r = None',
    '            # ==============================================',
    '',
]
NUEVO_ANGULO = "".join(l + "\n" for l in _CUERPO)
VIEJO_ANGULO = (
    "            green_state = 0\n"
    "            x_resultant = np.mean(x_black)\n"
    "            y_resultant = np.mean(y_black)\n"
    "            angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90\n"
    "            speed = 40\n"
)

# ============================================================================
#  BLOQUE 3 - la guarda vieja. Con RECUP encendido, poner 0 es exactamente lo
#  que no hay que hacer: pisaria el angulo de busqueda con "derecho".
# ============================================================================
VIEJA_GUARDA = (
    "            if np.sum(black_mask) < min_line_size:\n"
    "                angle = 0\n"
)
NUEVA_GUARDA = (
    "            if (not RECUP) and np.sum(black_mask) < min_line_size:\n"
    "                angle = 0\n"
)

# ============================================================================
#  BLOQUE 4 - la grabacion
# ============================================================================
ANCLA_ENVIO = (
    "            output = send_frame(speed, round(angle), green_state, silver_line)\n"
)
NUEVO_ENVIO = (
    "            output = send_frame(speed, round(angle), green_state, silver_line)\n"
    "            _grabar(frame_resized, _ang_viejo, angle, _r, _quien, _corte)\n"
    "            _log_frame(black_mask, _ang_viejo, angle, green_state, silver_line)\n"
)

CAMBIOS = [
    ("los imports y las funciones nuevas", ANCLA_IMPORT, ANCLA_IMPORT + "\n" + BLOQUE_IMPORT),
    ("los globals de la memoria de direccion", ANCLA_GLOBAL, NUEVO_GLOBAL),
    ("el calculo del angulo", VIEJO_ANGULO, NUEVO_ANGULO),
    ("la guarda de min_line_size", VIEJA_GUARDA, NUEVA_GUARDA),
    ("la grabacion, despues del envio", ANCLA_ENVIO, NUEVO_ENVIO),
]


def leer(ruta):
    with io.open(ruta, encoding="utf-8", newline="") as fh:
        return fh.read()


def escribir(ruta, txt):
    with io.open(ruta, "w", encoding="utf-8", newline="") as fh:
        fh.write(txt)


def main():
    if not os.path.exists(RUTA):
        print("*** No encuentro el main del robot (busque: %s)" % RUTA)
        print("    Copia parche_planner.py a la MISMA carpeta que main.py,")
        print("    o pasale la ruta:  python3 parche_planner.py /ruta/al/main.py")
        return 2

    bak = RUTA + ".bak"

    if "--revertir" in sys.argv:
        if not os.path.exists(bak):
            print("*** No hay %s: no puedo revertir." % os.path.basename(bak))
            return 2
        escribir(RUTA, leer(bak))
        print("Revertido: %s volvio a como estaba." % os.path.basename(RUTA))
        return 0

    s = leer(RUTA).replace("\r\n", "\n")

    if "MEJORAS DE SEGUIMIENTO (parche IITA)" in s:
        print("El parche YA ESTA aplicado.")
        print("Para rehacerlo:  python3 parche_planner.py --revertir && python3 parche_planner.py")
        return 0

    faltan = [nom for nom, viejo, _ in CAMBIOS if viejo not in s]
    if faltan:
        print("*** No encontre estos lugares en %s, NO toco nada:" % os.path.basename(RUTA))
        for f in faltan:
            print("      - " + f)
        return 1

    if "--ver" in sys.argv:
        print("Los %d lugares estan. El parche entraria limpio." % len(CAMBIOS))
        return 0

    if not os.path.exists(bak):
        escribir(bak, leer(RUTA))
        print("backup: %s" % bak)

    for nom, viejo, nuevo in CAMBIOS:
        s = s.replace(viejo, nuevo, 1)
        print("  parchado: %s" % nom)

    escribir(RUTA, s)

    import py_compile
    try:
        py_compile.compile(RUTA, doraise=True)
        print("\n%s compila." % os.path.basename(RUTA))
    except Exception as e:
        print("\n*** NO compila: %s" % e)
        print("    Revirtiendo solo, para no dejarte el robot roto.")
        escribir(RUTA, leer(bak))
        return 1

    print("""
LISTO. Sin variables de entorno NO cambia nada. Lo recomendado para probar:

  sudo systemctl stop iita-robot

  ROI=auto RECUP=1 GRABAR=~/Desktop/a.avi python3 main.py
      tu calculo de siempre, pero viendo mas pista y SIN ENDEREZAR cuando
      pierde la linea, que es lo que hoy lo saca de la pista

  ROI=auto RECUP=1 CTRL=lineal K_CERCA=70 GRABAR=~/Desktop/b.avi python3 main.py
      lo mismo, ademas con ganancia constante

Revertir:  python3 parche_planner.py --revertir
Al final:  sudo systemctl start iita-robot
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
