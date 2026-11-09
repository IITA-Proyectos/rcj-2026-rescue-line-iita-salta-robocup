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
