# El ángulo del planner depende de un número que nadie midió

_26-ago-2026 · sale de la pregunta de Benjamín: «el círculo verde con la X blanca
sigue bien la línea, lo que no sé es si el cálculo del ángulo es el correcto»_

**El target está bien. El ángulo puede no estarlo, y por una razón concreta:
`ψ` depende del campo de visión de la cámara, y ese número está puesto a mano.**

---

## Lo que asume el código

```python
vision_linea.py:111   LEY_HFOV = _envf("LEY_STEER_HFOV", 60.0)
vision_linea.py:217   f_px = (W/2) / tan(radians(60.0/2))     # hardcodeado
ley_steer.py:98       HFOV_NOMINAL = 60.0
curva_cerrada.py:77   HFOV = 60.0
```

Y la proyección al suelo es:

```
f_px = (W/2) / tan(HFOV/2)
X    = (u − CENTER) · Z / f_px        ← todo el lateral pasa por acá
ψ    = atan2(ΔX, ΔZ)
```

**Si `HFOV` está mal, `X` está mal por el mismo factor, y `ψ` con él.**

## Lo que dice el TDP

`docs/tdp/TDP-IITA-2026.md:352`: *"a **140 degree** wide-angle USB camera"*.

## El impacto, con el frame del screenshot

Ese frame da `ψ = +19,3°` **asumiendo 60°**. Con otros HFOV, **el mismo target**:

| HFOV | f_px | X relativo | **ψ** |
|---|---|---|---|
| 45 | 193,1 | 0,72× | 14,1° |
| **60** | 138,6 | 1,00× | **19,3°** ← lo que asume el código |
| 75 | 104,3 | 1,33× | 25,0° |
| 90 | 80,0 | 1,73× | 31,2° |
| 120 | 46,2 | 3,00× | 46,4° |
| **140** | 29,1 | **4,76×** | **59,0°** ← lo que dice el TDP |

**De 19,3° a 59,0°: tres veces más.** El término de rumbo de Stanley se multiplica
por eso.

---

## Lo que esto NO afecta, y es importante

**El `atan2` que corre HOY en el robot no usa el HFOV.** `Main.py:887` trabaja en
píxeles normalizados y **nunca proyecta al suelo**. Por eso, en el screenshot:

- **LEY DE HOY +9,6** → robusta a este problema
- **STANLEY +12,2** → depende enteramente de un número no calibrado

Y eso reordena una prioridad: **encender `LEY_STEER=stanley` antes de calibrar el
HFOV es encender una ley cuyo término principal está escalado por un factor
desconocido entre 0,72 y 4,76.**

---

## El equipo ya lo sabía, y lo dejó escrito

`FALSADOR-STANLEY.md:128`: *"El HFOV **no está calibrado** y `d_eje` **no está
medido**"*. Por eso todo se reportó para la banda **45 / 60 / 75**.

**Pero si el real es 140, los tres puntos de esa banda están fuera**, y el gate
15/15 de Stanley se corrió en un rango que no contiene el valor verdadero.

*(Ojo: `v_h = 9,0`, la fila del horizonte, **sí** está medida — `birdeye.py`, R²
0,982–0,999 en 9 de 11 videos. El problema es sólo el HFOV.)*

---

## Cómo se mide, en 5 minutos y sin robot

No hace falta patrón de calibración ni OpenCV. Una cinta métrica y una foto:

1. Apoyá la cámara mirando a una **pared plana**, perpendicular.
2. Medí con la cinta la **distancia `D`** de la lente a la pared.
3. Marcá en la pared **los dos bordes** de lo que la cámara ve (mirando la imagen
   en vivo, mové un dedo hasta que aparezca justo en el borde izquierdo, marcá; lo
   mismo del derecho).
4. Medí el **ancho `L`** entre las dos marcas.

```
HFOV = 2 · atan( L / (2·D) )
```

**Ejemplo**: si a `D = 50 cm` la cámara abarca `L = 55 cm` → HFOV = 57,7°.
Si abarca `L = 275 cm` → HFOV = 140°. **Son inconfundibles.**

Y de paso sale `f_px = (160/2) / tan(HFOV/2)`, que es lo que el código necesita.

### Después de medirlo

```bash
LEY_STEER_HFOV=<el medido> python3 Main.py     # la variable ya existe
```

Y hay que rehacer la banda del falsador de Stanley alrededor del valor real, no
alrededor de 60.

---

## Lo que NO puedo afirmar

**No sé cuál es el HFOV real.** El TDP dice 140, pero el TDP ya se equivocó dos
veces en cosas verificadas esta semana (dice "60 mm wheel" cuando el efectivo es
68,8, y dice "fixed wheels and omniwheels" cuando hoy son 4 fijas). **No lo tomo
como dato hasta que alguien lo mida.**

Lo único que está establecido es que **el código asume 60 y nadie lo verificó**.
