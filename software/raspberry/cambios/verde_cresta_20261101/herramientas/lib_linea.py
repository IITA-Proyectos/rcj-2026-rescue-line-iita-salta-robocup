import math, cv2, numpy as np
W, H = 160, 120
cam_x, cam_y = W / 2 - 1, H - 1
jj, ii = np.meshgrid(np.arange(W), np.arange(H))
x_com = (jj - cam_x) / (W / 2); y_com = (cam_y - ii) / H
def ley(mask):
    m = mask > 0
    xb = np.where(m, x_com, 0) * (1 - y_com); yb = np.where(m, y_com, 0)
    return math.degrees(math.atan2(yb.mean(), xb.mean())) - 90
def solo_mi_linea(mask, area_min=200):
    num, et, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    fila = et[H - 2]; suyas = np.unique(fila[fila > 0])
    if not len(suyas): return np.zeros_like(mask)
    if max(int(st[i, cv2.CC_STAT_AREA]) for i in suyas) < area_min: return np.zeros_like(mask)
    return (np.isin(et, suyas) * 255).astype(np.uint8)
def cuadro_chico(f):
    """Del cuadro 640x240 del video GRABAR, el 160x120 que vio la Pi."""
    return f[1::2, 1:320:2][:H, :W]
def mascara_negra(small):
    bm = cv2.inRange(small, np.array([0, 0, 0]), np.array([90, 90, 90])); bm[:60] = 0
    return bm
