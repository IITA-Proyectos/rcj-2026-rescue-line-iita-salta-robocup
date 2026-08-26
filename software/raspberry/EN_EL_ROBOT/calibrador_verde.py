# -*- coding: utf-8 -*-
"""
Calibrador de verdes alineado 1:1 con Main.py.

Diferencias clave contra el calibrador viejo:
  1. La recomendacion de min_square_size se mide sobre la MASCARA CRUDA
     (sin morfologia), igual que el gate del Main:
         np.sum(green_mask) > min_square_size * 255
     que equivale a: pixeles_blancos > min_square_size.
  2. Se mide UN solo cuadrado (el blob mas grande), no toda la ROI.
     Si calibras mostrando doble verde, el calibrador viejo recomendaba
     ~1.4x un cuadrado y los verdes simples dejaban de detectarse.
  3. La medicion usa el MISMO rango LAB que corre el Main (constantes
     MAIN_LOWER_GREEN / MAIN_UPPER_GREEN abajo), no el rango recien
     clickeado. Si recalibras color, pega el rango nuevo en Main.py Y aca.
  4. Simula en vivo el green_state EXACTO del Main (ratio 0.32 de negro
     sobre verde, guard de cx_black, gate 1.25x para doble verde) y te
     dice que gate falla cuando da 0.

Teclas:
  click izq  = agregar punto (4 = 1 cuadrado, 8 = 2 cuadrados)
  click der  = borrar ultimo punto
  c = calibrar color LAB con los poligonos clickeados
  u = alternar rango activo (MAIN <-> recien calibrado)
  m = medir cuadrado y recomendar min_square_size
  + / - = subir/bajar min_square_size de a 10 (para probar en vivo)
  r = reset
  q / ESC = salir
"""

import os
import re
import time
import traceback

import cv2
import numpy as np

try:
    from camthreader import WebcamVideoStream
except ImportError:
    WebcamVideoStream = None
except Exception:
    # camthreader existe pero fallo al importar (sintaxis, cv2, etc.):
    # mostrarlo, no tragarlo — el fallback cambia el backend de captura.
    traceback.print_exc()
    WebcamVideoStream = None


# =========================================================
# ESPEJO DE Main.py — mantener SIEMPRE sincronizado a mano.
# Si cambia algo en Main.py, cambiarlo aca tambien.
# =========================================================

# Main.py lineas 70-73
MAIN_LOWER_BLACK = np.array([0, 0, 0])
MAIN_UPPER_BLACK = np.array([90, 90, 90])
MAIN_LOWER_GREEN = np.array([80, 87, 85])    # lab
MAIN_UPPER_GREEN = np.array([205, 123, 120])

# Main.py linea 59
MAIN_MIN_SQUARE_SIZE = 550

# Main.py linea 15
ENABLE_CX_BLACK_GUARD = True

# Geometria de Main.py (lineas 769-786)
WIDTH, HEIGHT = 160, 120
GREEN_ROI_Y = 80      # green_mask[80:, :]
BLACK_TOP_CUT = 55    # black_mask[:55, :] = 0
RATIO_NEGRO_MIN = 0.32
FACTOR_DOBLE = 1.25   # Main.py linea 828 (ojo: Main_challenge.py tambien usa 1.25)

# =========================================================
# CONFIG DEL CALIBRADOR
# =========================================================

USE_IMAGE = False
# OJO: la imagen debe ser un frame CRUDO de la camara (SIN rotar). Una captura
# de las ventanas de debug del Main ya viene rotada: la doble rotacion manda el
# verde arriba de la imagen, fuera de la ROI, y la medicion sale basura.
IMAGE_PATH = "/home/pi/Desktop/xd/img_23.jpg"

# Margen: el Main dispara cuando ve ~70% del cuadrado medido,
# o sea un poco ANTES de la distancia a la que calibraste.
FACTOR_RECOMENDACION = 0.70

# Pisos/techos de sanidad para la medicion (tecla m)
MIN_PX_MEDICION = 200                            # menos = ruido o cuadrado fuera de ROI
ROI_TOTAL_PX = (HEIGHT - GREEN_ROI_Y) * WIDTH    # 40 filas x 160 col = 6400 px
MAX_FRACCION_ROI = 0.35                          # mas = cuadrado demasiado cerca

PADDING_LAB = np.array([5, 5, 5], dtype=np.int32)
MIN_PIXELS = 50

SCALE = 4  # zoom de la ventana (procesamiento sigue en 160x120)

WINDOW = "Calibrador Verde (alineado a Main)"
MASK_WINDOW = "Green mask CRUDA (lo que mide el Main)"


# =========================================================
# PIPELINE — copiado textual de Main.py lineas 769-782
# =========================================================

def construir_mascaras(frame, lower_green, upper_green):
    """Devuelve (frame_resized, green_mask cruda, black_mask) como el Main."""
    frame = cv2.rotate(frame, cv2.ROTATE_180)
    frame_resized = cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_NEAREST)

    lab = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)

    black_mask = cv2.inRange(frame_resized, MAIN_LOWER_BLACK, MAIN_UPPER_BLACK)
    black_mask[:BLACK_TOP_CUT, :] = 0

    green_mask = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    green_mask[GREEN_ROI_Y:, :] = cv2.inRange(lab[GREEN_ROI_Y:, :, :], lower_green, upper_green)

    return frame_resized, lab, green_mask, black_mask


# =========================================================
# SIMULACION DEL green_state — logica exacta de Main.py 802-839
# =========================================================

def simular_green_state(green_mask, black_mask, min_square_size):
    """Devuelve (estado, diag) replicando la decision del Main."""
    kernel = np.ones((3, 3), np.uint8)
    diag = {
        "npx": int(cv2.countNonZero(green_mask)),  # == np.sum(green_mask)/255
        "left": None, "right": None, "centroide": None,
        "cx_black": None, "ratio": None, "n_contornos": None,
        "motivo": "",
    }

    # Gate 1: np.sum(green_mask) > min_square_size * 255
    if not (diag["npx"] > min_square_size):
        diag["motivo"] = f"poco verde: {diag['npx']}px <= min_square_size={min_square_size}"
        return 0, diag

    green_pixels = np.amax(green_mask, axis=0)
    greenIndices = np.where(green_pixels == np.max(green_pixels))
    leftIndex = greenIndices[0][0]
    rightIndex = greenIndices[0][-1]
    greenCentroidX = (rightIndex + leftIndex) / 2
    slicedBlackMaskAboveGreen = black_mask[60:90, leftIndex:rightIndex + 1]
    blackM = cv2.moments(black_mask[90:, :])

    diag["left"], diag["right"] = int(leftIndex), int(rightIndex)
    diag["centroide"] = greenCentroidX

    if ENABLE_CX_BLACK_GUARD:
        cx_black = None
        if np.sum(black_mask[90:, :]) and blackM["m00"] != 0:
            cx_black = int(blackM["m10"] / blackM["m00"])
        valid_green_reference = cx_black is not None
    else:
        cx_black = None
        if np.sum(black_mask[90:, :]):
            cx_black = int(blackM["m10"] / blackM["m00"])
        valid_green_reference = True

    diag["cx_black"] = cx_black

    # ratio de negro en la franja y=60:90 sobre el ancho del verde
    num = float(np.sum(slicedBlackMaskAboveGreen))
    den = 255.0 * 30.0 * (rightIndex - leftIndex)
    ratio = (num / den) if den > 0 else (float("inf") if num > 0 else 0.0)
    diag["ratio"] = ratio

    if not valid_green_reference:
        diag["motivo"] = "sin linea negra abajo (cx_black invalido)"
        return 0, diag

    if not (ratio > RATIO_NEGRO_MIN):
        diag["motivo"] = f"sin negro sobre el verde: ratio {ratio:.2f} <= {RATIO_NEGRO_MIN}"
        return 0, diag

    if cx_black is None:
        # Solo alcanzable con ENABLE_CX_BLACK_GUARD=False y sin negro abajo.
        # Ahi el Main usaria un cx_black VIEJO de otro frame (comportamiento
        # indefinido); aca lo reportamos como 0 en vez de crashear.
        diag["motivo"] = "guard OFF sin negro abajo: Main usaria cx_black viejo (indefinido)"
        return 0, diag

    filtered_green_mask = cv2.erode(green_mask, kernel, iterations=1)
    filtered_green_mask = cv2.dilate(filtered_green_mask, kernel, iterations=2)
    green_contours, _ = cv2.findContours(filtered_green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    diag["n_contornos"] = len(green_contours)

    if (len(green_contours) > 1 and cx_black > leftIndex and cx_black < rightIndex
            and diag["npx"] > FACTOR_DOBLE * min_square_size):
        diag["motivo"] = "doble verde (giro en U)"
        return 3, diag
    elif greenCentroidX < cx_black:
        diag["motivo"] = "verde a la izquierda de la linea"
        return 1, diag
    else:
        diag["motivo"] = "verde a la derecha de la linea"
        return 2, diag


# =========================================================
# MEDICION / RECOMENDACION
# =========================================================

def medir_cuadrado(green_mask):
    """Mide el blob de verde mas grande de la mascara CRUDA.

    Devuelve (px_mayor, n_blobs_grandes, px_suma_grandes) o (None, 0, 0).
    """
    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0, 0

    px_por_blob = []
    for c in contours:
        blob = np.zeros_like(green_mask)
        cv2.drawContours(blob, [c], -1, 255, -1)
        # pixeles crudos reales dentro del contorno (no cv2.contourArea,
        # que subestima, y no cuenta los huecos internos como el Main si los ve)
        px_por_blob.append(cv2.countNonZero(cv2.bitwise_and(green_mask, blob)))

    mayor = max(px_por_blob)
    # blobs comparables al mayor (>=40%) = probables cuadrados verdes reales
    grandes = [p for p in px_por_blob if p >= 0.4 * mayor]
    return mayor, len(grandes), sum(grandes)


def imprimir_recomendacion(green_mask, nombre_rango):
    px, n_grandes, suma_grandes = medir_cuadrado(green_mask)

    print("\n--- Recomendacion min_square_size ---")
    print(f"Rango usado para medir: {nombre_rango}")

    if px is None:
        print("No hay verde en la mascara cruda. Revisa el rango o acerca el cuadrado.")
        print("-------------------------------------\n")
        return None

    fraccion_roi = px / float(ROI_TOTAL_PX)
    print(f"Cuadrado mas grande (mascara CRUDA): {px} px ({fraccion_roi:.0%} de la ROI)")

    if px < MIN_PX_MEDICION:
        print(f"\n*** MEDICION SOSPECHOSA: solo {px}px (< {MIN_PX_MEDICION}). NO pegues este valor. ***")
        print("Causas tipicas: cuadrado por ENCIMA de la linea magenta (fuera de la ROI")
        print("y>=80), rango que no toma bien el verde, o puro ruido de la mascara.")
        print("-------------------------------------\n")
        return None

    if fraccion_roi > MAX_FRACCION_ROI:
        print(f"\n*** CUADRADO DEMASIADO CERCA ({fraccion_roi:.0%} de la ROI). NO pegues este valor. ***")
        print("Con un min_square_size tan alto, el doble verde (estado 3) puede volverse")
        print("inalcanzable: dos cuadrados a distancia real de giro no juntan 1.25x ese")
        print("numero. Aleja el robot a la distancia de decision y volve a medir.")
        print("-------------------------------------\n")
        return None

    if n_grandes >= 2:
        print(f"Se ven {n_grandes} blobs grandes (mayor={px}px, suma={suma_grandes}px):")
        print("- Si mostras DOS cuadrados: OK, se usa solo el mayor (correcto).")
        print("- Si mostras UNO solo: la mascara lo esta PARTIENDO (sombra/brillo) y la")
        print("  recomendacion saldria baja. Revisa la ventana de mascara antes de pegar.")

    rec = int(px * FACTOR_RECOMENDACION)
    print(f"\nmin_square_size = {rec}   # {FACTOR_RECOMENDACION:.0%} de {px}px")
    print("(pegalo en Main.py — y en Main_challenge.py si aplica)")
    print("\nValida el estado 3 EN VIVO: mostra doble verde con su interseccion a la")
    print("distancia de giro y confirma que el HUD marque 3. El gate de pixeles no es")
    print("lo unico: tambien pesan los 2 contornos separados y cx_black entre ellos.")
    print("-------------------------------------\n")
    return rec


# =========================================================
# CALIBRACION DE COLOR (LAB) — misma idea que tu calibrador viejo
# =========================================================

def order_points(pts):
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.int32)


def split_polys(points):
    polys = []
    if len(points) >= 4:
        polys.append(order_points(points[:4]))
    if len(points) >= 8:
        polys.append(order_points(points[4:8]))
    return polys


def calibrar_color_lab(lab, polys):
    all_pixels = []
    for poly in polys:
        mask = np.zeros(lab.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [np.array(poly, dtype=np.int32)], 255)
        pixels = lab[mask == 255]
        if pixels.size < (MIN_PIXELS * 3):
            raise ValueError("Muy pocos pixeles para calibrar. Usa un area mas grande.")
        all_pixels.append(pixels)

    all_pixels = np.vstack(all_pixels)
    lo = np.clip(all_pixels.min(axis=0).astype(np.int32) - PADDING_LAB, 0, 255)
    hi = np.clip(all_pixels.max(axis=0).astype(np.int32) + PADDING_LAB, 0, 255)
    return lo.astype(np.uint8), hi.astype(np.uint8)


# =========================================================
# CHEQUEO DE ESPEJO — detecta desfase con Main.py / Main_challenge.py
# =========================================================

def _leer_constantes_de(src):
    out = {}
    m = re.search(r"^min_square_size\s*=\s*(\d+)", src, re.M)
    if m:
        out["min_square_size"] = int(m.group(1))
    for nombre in ("lower_green", "upper_green"):
        m = re.search(nombre + r"\s*=\s*np\.array\(\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", src)
        if m:
            out[nombre] = tuple(int(g) for g in m.groups())
    m = re.search(r"^ENABLE_CX_BLACK_GUARD\s*=\s*(True|False)", src, re.M)
    if m:
        out["ENABLE_CX_BLACK_GUARD"] = (m.group(1) == "True")
    return out


def chequear_espejo():
    """Compara las constantes espejo de este archivo contra los Main REALES.

    Devuelve lista de desfases (vacia = todo sincronizado). Un numero medido
    con el espejo desfasado NO representa lo que va a correr el robot.
    """
    esperado = {
        "min_square_size": MAIN_MIN_SQUARE_SIZE,
        "lower_green": tuple(int(v) for v in MAIN_LOWER_GREEN),
        "upper_green": tuple(int(v) for v in MAIN_UPPER_GREEN),
        "ENABLE_CX_BLACK_GUARD": ENABLE_CX_BLACK_GUARD,
    }
    avisos = []
    base = os.path.dirname(os.path.abspath(__file__))
    for fname in ("Main.py", "Main_challenge.py"):
        path = os.path.join(base, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reales = _leer_constantes_de(f.read())
        except OSError:
            avisos.append(f"{fname}: no encontrado — espejo SIN verificar")
            continue
        for clave, valor in esperado.items():
            if clave in reales and reales[clave] != valor:
                avisos.append(f"{fname}: {clave}={reales[clave]} vs calibrador={valor}")
    return avisos


# =========================================================
# MAIN
# =========================================================

def main():
    if USE_IMAGE:
        base_img = cv2.imread(IMAGE_PATH)
        if base_img is None:
            raise FileNotFoundError(f"No se pudo leer la imagen: {IMAGE_PATH}")
        vs, use_thread = None, False
    else:
        if WebcamVideoStream is not None:
            vs = WebcamVideoStream(src=0, width=WIDTH, height=HEIGHT).start()
            use_thread = True
        else:
            vs = cv2.VideoCapture(0)
            vs.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            vs.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            use_thread = False

    points = []
    rango_calibrado = None          # (lower, upper) recien calibrado
    usar_rango_calibrado = False    # tecla 'u'
    mss = MAIN_MIN_SQUARE_SIZE      # ajustable con +/- para probar en vivo

    def on_mouse(event, x, y, flags, param):
        # la ventana esta escalada SCALE veces -> volver a coords 160x120
        x, y = x // SCALE, y // SCALE
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 8:
            points.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, on_mouse)

    print(__doc__)
    print(f"Rango MAIN: lower={MAIN_LOWER_GREEN.tolist()} upper={MAIN_UPPER_GREEN.tolist()}")
    print(f"min_square_size inicial (de Main.py): {mss}")

    # Backend de captura: el numero solo vale medido con la camara del robot.
    if USE_IMAGE:
        print("Fuente: imagen en disco (debe ser frame CRUDO pre-rotacion, ver IMAGE_PATH).")
    elif use_thread:
        print("Fuente: WebcamVideoStream (camthreader) — mismo backend que el Main. OK.")
    else:
        w_real = vs.get(cv2.CAP_PROP_FRAME_WIDTH)
        h_real = vs.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"*** Fuente: cv2.VideoCapture directo (camthreader NO importo). ***")
        print(f"*** Resolucion real de camara: {w_real:.0f}x{h_real:.0f}. La medicion SOLO ***")
        print(f"*** vale con la camara del robot montada a su altura de trabajo. ***")

    desfases = chequear_espejo()
    if desfases:
        print("\n*** ESPEJO DESINCRONIZADO — este calibrador NO representa lo que corre: ***")
        for aviso in desfases:
            print(f"  - {aviso}")
        print("Actualiza las constantes MAIN_* de este archivo antes de confiar en nada.\n")

    colores_estado = {0: (128, 128, 128), 1: (0, 255, 255), 2: (255, 255, 0), 3: (0, 0, 255)}

    while True:
        if USE_IMAGE:
            frame = base_img.copy()
        elif use_thread:
            frame = vs.read()
        else:
            ret, frame = vs.read()
            if not ret:
                frame = None

        if frame is None:
            time.sleep(0.01)
            continue

        if usar_rango_calibrado and rango_calibrado is not None:
            lower, upper = rango_calibrado
            nombre_rango = "CALIBRADO (sesion)"
        else:
            lower, upper = MAIN_LOWER_GREEN, MAIN_UPPER_GREEN
            nombre_rango = "MAIN"

        frame_resized, lab, green_mask, black_mask = construir_mascaras(frame, lower, upper)
        estado, diag = simular_green_state(green_mask, black_mask, mss)

        # ---------- display ----------
        display = cv2.resize(frame_resized, (WIDTH * SCALE, HEIGHT * SCALE),
                             interpolation=cv2.INTER_NEAREST)

        # ROI verde y franja del ratio
        cv2.line(display, (0, GREEN_ROI_Y * SCALE), (WIDTH * SCALE, GREEN_ROI_Y * SCALE), (255, 0, 255), 1)
        cv2.line(display, (0, 60 * SCALE), (WIDTH * SCALE, 60 * SCALE), (255, 0, 255), 1)

        # columnas left/right del verde y cx_black
        if diag["left"] is not None:
            cv2.line(display, (diag["left"] * SCALE, GREEN_ROI_Y * SCALE),
                     (diag["left"] * SCALE, HEIGHT * SCALE), (0, 255, 0), 1)
            cv2.line(display, (diag["right"] * SCALE, GREEN_ROI_Y * SCALE),
                     (diag["right"] * SCALE, HEIGHT * SCALE), (0, 255, 0), 1)
        if diag["cx_black"] is not None:
            cv2.line(display, (diag["cx_black"] * SCALE, 90 * SCALE),
                     (diag["cx_black"] * SCALE, HEIGHT * SCALE), (0, 0, 255), 2)

        # puntos y poligonos de calibracion
        for idx, (x, y) in enumerate(points):
            cv2.circle(display, (x * SCALE, y * SCALE), 3, (0, 255, 255), -1)
            cv2.putText(display, str(idx + 1), (x * SCALE + 4, y * SCALE - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        for i, poly in enumerate(split_polys(points)):
            color = (0, 255, 0) if i == 0 else (0, 180, 255)
            cv2.polylines(display, [poly * SCALE], True, color, 1)

        # HUD
        hud = [
            (f"green_state = {estado}  ({diag['motivo']})", colores_estado[estado]),
            (f"verde: {diag['npx']}px | gates: >{mss} simple, >{FACTOR_DOBLE * mss:.0f} doble", (255, 255, 255)),
            (f"rango: {nombre_rango} | ratio negro: "
             + (f"{diag['ratio']:.2f}" if diag['ratio'] is not None else "-")
             + f" (min {RATIO_NEGRO_MIN})", (255, 255, 255)),
            (f"contornos: {diag['n_contornos'] if diag['n_contornos'] is not None else '-'}"
             + f" | cx_black: {diag['cx_black'] if diag['cx_black'] is not None else '-'}", (255, 255, 255)),
            ("c=color  m=medir  u=rango  +/-=mss  r=reset  q=salir", (200, 200, 200)),
        ]
        if desfases:
            hud.insert(0, ("*** ESPEJO DESINCRONIZADO vs Main — ver consola ***", (0, 0, 255)))
        for i, (txt, col) in enumerate(hud):
            cv2.putText(display, txt, (8, 20 + i * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 3)
            cv2.putText(display, txt, (8, 20 + i * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, col, 1)

        cv2.imshow(WINDOW, display)
        cv2.imshow(MASK_WINDOW, cv2.resize(green_mask, (WIDTH * SCALE, HEIGHT * SCALE),
                                           interpolation=cv2.INTER_NEAREST))

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == 27:
            break

        elif key == ord('r'):
            points = []
            rango_calibrado = None
            usar_rango_calibrado = False
            mss = MAIN_MIN_SQUARE_SIZE

        elif key == ord('+') or key == ord('='):
            mss += 10
            print(f"min_square_size (prueba en vivo) = {mss}")

        elif key == ord('-'):
            mss = max(10, mss - 10)
            print(f"min_square_size (prueba en vivo) = {mss}")

        elif key == ord('u'):
            if rango_calibrado is None:
                print("Todavia no calibraste color (tecla c).")
            else:
                usar_rango_calibrado = not usar_rango_calibrado
                print(f"Rango activo: {'CALIBRADO' if usar_rango_calibrado else 'MAIN'}")

        elif key == ord('c'):
            polys = split_polys(points)
            if len(points) not in (4, 8):
                print("Necesitas 4 puntos (1 cuadrado) u 8 puntos (2 cuadrados).")
                continue
            try:
                lo, hi = calibrar_color_lab(lab, polys)
            except ValueError as e:
                print(str(e))
                continue
            rango_calibrado = (lo, hi)
            print("\n--- Calibracion color ---")
            print(f"lower_green = np.array([{lo[0]}, {lo[1]}, {lo[2]}])  # lab")
            print(f"upper_green = np.array([{hi[0]}, {hi[1]}, {hi[2]}])")
            print("Si adoptas este rango, EN ESTE ORDEN:")
            print("  1) tecla u  -> activarlo en vivo y ver que la mascara quede solida")
            print("  2) tecla m  -> medir min_square_size CON este rango (no con el viejo)")
            print("  3) pegar rango + min_square_size en Main.py (y Main_challenge.py),")
            print("     y el rango tambien en MAIN_LOWER/UPPER_GREEN de este archivo.")
            print("-------------------------\n")

        elif key == ord('m'):
            if rango_calibrado is not None and not usar_rango_calibrado:
                print("\nOJO: calibraste un rango nuevo pero estas midiendo con el rango MAIN")
                print("viejo. Si vas a pegar el rango nuevo en Main.py, apreta u primero y")
                print("volve a medir — si no, el numero NO va a corresponder al rango.\n")
            rec = imprimir_recomendacion(green_mask, nombre_rango)
            if rec is not None:
                mss = rec
                print(f"Aplicado en vivo: el HUD ya simula con min_square_size = {rec}"
                      " (+/- para ajustar; el Main sigue con el suyo hasta que lo pegues).")
            if rec is not None and nombre_rango != "MAIN":
                print("OJO: mediste con el rango CALIBRADO de la sesion. Ese numero solo")
                print("vale si pegas el rango nuevo en Main.py. Si no, medi con rango MAIN (tecla u).")

    if not USE_IMAGE:
        if use_thread and WebcamVideoStream is not None:
            vs.stop()
        else:
            vs.release()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
