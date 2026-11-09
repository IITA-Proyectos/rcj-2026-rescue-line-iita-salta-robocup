"""Respaldo conservador: usar solo si el detector principal devuelve cero."""
import cv2
import numpy as np


def detectar_verde_oscuro(lab, black_mask, lower_green, upper_green,
                         min_square_size, factor_doble):
    lower = np.array(lower_green, copy=True)
    lower[0] = min(int(lower[0]), 100)
    mask = np.zeros(black_mask.shape, dtype=np.uint8)
    mask[80:, :] = cv2.inRange(lab[80:, :, :], lower, upper_green)
    area = int(np.count_nonzero(mask))
    # El respaldo conserva el piso validado en la grabacion, incluso si el
    # detector principal fue ajustado a un area menor en pista.
    area_minima = max(600, int(min_square_size))
    if area <= area_minima:
        return 0, None
    xs = np.flatnonzero(np.any(mask, axis=0))
    left, right = int(xs[0]), int(xs[-1])
    if right <= left:
        return 0, None
    moments = cv2.moments(black_mask[90:, :])
    if moments['m00'] == 0:
        return 0, None
    cx = int(moments['m10'] / moments['m00'])
    occupancy = np.count_nonzero(black_mask[60:90, left:right + 1]) / (30.0 * (right - left))
    if occupancy <= 0.32:
        return 0, None
    kernel = np.ones((3, 3), dtype=np.uint8)
    filtered = cv2.dilate(cv2.erode(mask, kernel, iterations=1), kernel, iterations=2)
    contours, _ = cv2.findContours(filtered, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) > 1 and left < cx < right and area > factor_doble * area_minima:
        return 3, mask
    return (1 if (left + right) / 2.0 < cx else 2), mask


VERSION_SOMBRA = 'VERDE-SOMBRA-1'


def _verde_ya_cruzado(lab, mask, left, right):
    """True si el cuadrado tiene la cinta ABAJO y piso limpio ARRIBA: ese travesano ya quedo atras.

    De lejos la parte alta del cuadrado se ve tan oscura que entra en la mascara de negro y cuenta
    como "negro arriba". Aca se mira lo que hay justo afuera del cuadrado, sin contar lo verdoso.
    Si alguna franja no entra en la imagen no se sabe, y la decision queda como estaba.
    """
    columnas = lab[:, left:right + 1]
    verdoso = columnas[..., 1] < 120
    cinta = (columnas[..., 0] < 97) & ~verdoso
    filas = np.flatnonzero(mask[:, left:right + 1].any(axis=1))
    if filas.size == 0:
        return False
    tope, fondo = int(filas[0]), int(filas[-1])
    por_fila = verdoso.mean(axis=1)
    while tope > 0 and por_fila[tope - 1] > 0.15:
        tope -= 1
    while fondo < lab.shape[0] - 1 and por_fila[fondo + 1] > 0.15:
        fondo += 1
    arriba = cinta[max(0, tope - 14):max(0, tope - 2)]
    abajo = cinta[fondo + 3:fondo + 15]
    if arriba.size == 0 or abajo.size == 0:
        return False
    return float(arriba.mean()) < 0.05 and float(abajo.mean()) > 0.8


def detectar_verde_sombra(lab, black_mask, lower_green, upper_green,
                         min_square_size, factor_doble):
    """Solo respaldo de los dos detectores anteriores; misma geometria de cruce."""
    lower = np.array(lower_green, copy=True)
    upper = np.array(upper_green, copy=True)
    lower[0] = min(int(lower[0]), 60)
    upper[1] = max(int(upper[1]), 111)
    upper[2] = max(int(upper[2]), 137)
    mask = np.zeros(black_mask.shape, dtype=np.uint8)
    mask[80:] = cv2.inRange(lab[80:], lower, upper)
    minimum = max(600, int(min_square_size))
    area = int(np.count_nonzero(mask))
    if area <= minimum:
        return 0, None
    xs = np.flatnonzero(mask.any(axis=0))
    left, right = int(xs[0]), int(xs[-1])
    if right <= left:
        return 0, None
    reference = cv2.moments(black_mask[90:])
    if reference['m00'] == 0:
        return 0, None
    cx = int(reference['m10'] / reference['m00'])
    occupancy = np.count_nonzero(black_mask[60:90, left:right + 1]) / (30.0 * (right - left))
    if occupancy <= 0.32:
        return 0, None
    kernel = np.ones((3, 3), dtype=np.uint8)
    filtered = cv2.dilate(cv2.erode(mask, kernel), kernel, iterations=2)
    contours, _ = cv2.findContours(filtered, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sides = set()
    for contour in contours:
        if cv2.contourArea(contour) < 60:
            continue
        moments = cv2.moments(contour)
        if moments['m00']:
            center = moments['m10'] / moments['m00']
            if center < cx - 3:
                sides.add(-1)
            elif center > cx + 3:
                sides.add(1)
    if sides and _verde_ya_cruzado(lab, mask, left, right):
        print("[VERDE-SOMBRA] ignorado: cinta abajo y piso arriba (col %d-%d)" % (left, right))
        return 0, None
    if sides == {-1, 1} and area > factor_doble * minimum:
        return 3, mask
    if sides == {-1}:
        return 1, mask
    if sides == {1}:
        return 2, mask
    return 0, None
