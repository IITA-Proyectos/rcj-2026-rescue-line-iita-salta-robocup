# calibrador_verde_v2.py: el factor del doble sale de DOBLE_SIN_FACTOR, igual que en main.py.
# Uso: python3 parche_calibrador_factor.py calibrador_verde_v2.py
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
a = "FACTOR_DOBLE = 1.2    # main.py: np.sum(green_mask) > 1.2 * min_square_size * 255"
b = ("# main.py: np.sum(green_mask) > FACTOR_DOBLE * min_square_size * 255. 1,2 de siempre, o 1,0 si se corre con\n"
     "# DOBLE_SIN_FACTOR=1 (igual que main.py): correr el calibrador con la misma variable que el robot.\n"
     "FACTOR_DOBLE = 1.0 if os.environ.get(\"DOBLE_SIN_FACTOR\", \"0\") == \"1\" else 1.2")
nl = "\r\n" if "\r\n" in s else "\n"
assert s.count(a) == 1, s.count(a)
s = s.replace(a, b.replace("\n", nl))
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok calibrador factor")
