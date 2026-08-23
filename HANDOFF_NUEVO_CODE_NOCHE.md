# HANDOFF — Nuevo Code, bloque autónomo de la noche del 2026-08-23

_Rama `collab/nuevo-code` · issue #138 · Claude, trabajo autónomo_

**Nada de V2/V3/V4 fue modificado.** Todos los experimentos los envuelven o los
subclasean. No se tocó hardware, DriveBase, `main` ni `roboliga`, y no se borró
evidencia.

---

## 1. La candidata mínima

> **NUEVO CODE V1 RC = `NuevoCodeV2` + `SpatialTargetGuard`.**
> **`NuevoCodeV3` se elimina, no se reemplaza.**

Medido sobre los 10 videos autónomos (13.900 frames), con `hist_exito` y
`lineal_positivo` como obligatorios:

| variante | disponib. | sin autoridad | huecos | saltos >24 px | inversiones | controles |
|---|---:|---:|---:|---:|---:|---|
| V2 solo | 95,14 % | 675 | 78 | 335 | 416 | PASA |
| V3 | 94,96 % | 701 | 121 | 339 | 396 | PASA |
| V4 completo | 93,76 % | 867 | 278 | **246** | 392 | PASA |
| **V2 + spatial (sin V3)** | **93,78 %** | **864** | **276** | **247** | **392** | **PASA** |

La diferencia entre V4 completo y V2+spatial es **ruido**: +0,02 % de
disponibilidad, −3 frames, −2 huecos, +1 salto, **0 inversiones de diferencia**
sobre 13.900 frames. **V3 no aporta nada medible.**

Archivo que la representa: `software/raspberry/final_rpi/arquitectura_minima.py`,
clase `SinBranch` (neutraliza el branch guard sin tocar `nuevo_code_v3.py`).
Commit de la candidata: **`f06396b`** (ver §7).

### Lo que la candidata NO resuelve

V4 —y por lo tanto la candidata— compra **−89 saltos grandes** al precio de
**+192 frames sin autoridad** respecto de V2 solo. Es un trade-off real, no una
mejora gratis. **Cuál de los dos cuesta más en pista no se puede saber sin el
robot**: un salto de 24+ px es una orden equivocada, un frame sin target es una
orden ausente, y no hay dato offline que los compare.

---

## 2. Hipótesis probadas

| # | hipótesis | estado | el número |
|---|---|---|---|
| H1 | el salto nace en la etapa 1 (`raw`) | **parcial** | `raw` salta >24 px en 46,8 % de los frames de evento contra 4,5 % del control (10,5×), pero es la *primera* etapa en sólo 40,1 % |
| H4 | el salto que ve el guard es la deuda de las capas previas | **refutada como causa / confirmada como efecto secundario** | en 162 de 166 rechazos (98 %) el movimiento real ya superaba 24 px. Pero con deuda >1 px la tasa de rechazo se cuadruplica: 5,4 % contra 1,3 % |
| H5 | los saltos se concentran cuando el esqueleto cruza `LOOKAHEAD=70` | **REFUTADA** | el bin 65-75 es un **mínimo local** (9,3 %) contra 13,2 % en 40-55 y 13,7 % en 75-85 |
| H6 | la ramificación del esqueleto predice el salto | **se sostiene** | controlada por largo: con esqueleto ≥140 px, hojas 0-4 → 3,5 % y hojas 6+ → **17,5 %** (5,0×) |
| H6a | esa ramificación es topología real | **GANA** | acuerdo de posición de las hojas bajo perturbación: **0,917** en frames que saltan |
| H6b | es artefacto de segmentación inestable | **mayormente refutada** | sólo el 11,8 % de los frames que saltan tiene acuerdo <0,60 |
| H7 | podar ramas cortas estabiliza el punto geodésico | **NO DECIDIDA** | la distribución de 39.009 longitudes no es bimodal (p50 48,3, 41,2 % >64 px). Mata *elegir umbral por valle*, no el pruning como clase — corrección de ChatGPT, aceptada |
| — | V4-sostiene (nunca devolver `None`) | **REFUTADA** | 100 % de disponibilidad y 0 huecos, pero **26,2 % de targets fuera de la centerline** y rachas de hasta **124 frames (3,7 s)** siguiendo un fantasma |
| — | V4 sin `reset()` de memoria | **REFUTADA** | falla los obligatorios: `hist_exito` 82/100, `lineal_positivo` 71/73; disponibilidad 73,78 %. **El `reset()` no es un bug: es lo que impide que el guard se trabe** |
| T4 | la conversión `target_x → steer` está mal | **SUSPENDIDA** | falta un dato físico (§6) |

---

## 3. Hallazgos nuevos

1. **El 75,4 % de los huecos los abre un guard, no la percepción.** 166
   `REJECT_SPATIAL` + 43 `REJECT_BRANCH` contra 68 `LOSS_PERCEPTION` sobre 277
   eventos. Reproduce la clasificación independiente de ChatGPT (164/43/69).

2. **En el frame del rechazo, la percepción SÍ había producido evidencia.**
   `target_geometric` existía en el **100 %** de los 209 rechazos, con la
   componente sobreviviendo p50 8 frames y 674 px de área. Pero el salto
   propuesto era genuinamente grande: sólo **2 de 209** estaban bajo 24 px.

3. **El rechazo del guard no mejora el salto.** Rechaza p50 63,0 px y termina
   aceptando 65,4 px, con delta mediano **+0,0**. Corregido en el bloque de A/B:
   globalmente V4 **sí** baja los saltos (335→246), porque el camino
   `SPATIAL_LIMIT` —el que no rechaza— sí limita. Lo que no aporta es el rechazo.

4. **Hay que medir la evidencia en el frame del rechazo, no en el anterior.** En
   el anterior los tres orígenes son indistinguibles (tocaba abajo 53-59 %,
   estable 8-9 frames). Mi primera versión lo medía mal.

5. **`off_path = 0` es una identidad, no una medición**, en las cuatro variantes
   que eligen puntos del esqueleto. Sólo pasa a medir algo en la variante
   «sostiene», y ahí da 26,2 %.

6. **La memoria congelada existe y es chica.** `prev_target` no se resetea en
   PERDIDA (`nuevo_code_v2.py:320-322, 342-344`) y la regla de
   `nuevo_code_v2.py:340` puede rechazar por lejanía contra una referencia vieja:
   20 rachas, 127 de 13.900 frames (**0,91 %**), máximo 660 ms, y el **36,2 %**
   se salvaría con el reset. **No generaliza**: `seguir`, `rumbo` y `con_planner`
   no tienen ni una.

7. **Advertencia de método:** mi test binario preregistrado habría **confirmado
   H5 por error** (12,0 % contra 5,4 %). Sólo la distribución por bins la
   desmiente. Un estadístico puede dar positivo por una razón distinta de la
   hipótesis.

---

## 4. Contradicciones Claude ↔ ChatGPT, y quién ganó según la evidencia

| tema | ChatGPT | Claude | quién gana |
|---|---|---|---|
| clasificación de los huecos | 164/43/69 | 166/43/68 | **empate**, se reproduce mutuamente |
| «si la componente era falsa, el rechazo es legítimo» | su falsador | medí que había target en el 100 % | **Claude**: la evidencia no era falsa. Pero el salto era real, así que su intuición de fondo tampoco cae |
| `bearing_real_deg` no es físico | sí | lo había publicado como «real» | **ChatGPT** |
| falta calibración de cámara | sí | ya existía (`v_h = +9,0`, R² ≥ 0,982) | **Claude** en el dato, **ChatGPT** en la conclusión: la calibración no alcanza, falta el origen del giro |
| H7 «comprometida» por falta de bimodalidad | «no decidida», el pruning no exige bimodalidad | «comprometida» | **ChatGPT**, corregido |
| H6-PERSISTENCE como test | lo propuso | lo había hecho en `topologia.py` | **empate**; su métrica extra (¿el raw cambia de rama entre variantes?) queda pendiente |

---

## 5. Técnicas externas investigadas, y cuáles se descartaron

| fuente | qué aportaba | resultado |
|---|---|---|
| [Skeleton Pruning by Contour Partitioning with DCE](https://cis.temple.edu/~latecki/Papers/skeletonPAMI07.pdf), Latecki PAMI 2007 | poda que preserva el tronco | **no adoptada**: la longitud no separa en nuestros datos |
| [Discrete skeleton evolution](https://en.wikipedia.org/wiki/Discrete_skeleton_evolution) + [implementación](https://github.com/originlake/DSE-skeleton-pruning) | poda iterativa | **no adoptada**, misma razón |
| [Robust Skeletonization for Plant Root Structure](https://arxiv.org/pdf/2010.14440) | eliminar *barbs* por longitud aguas abajo | **medida y descartada como está**: sin umbral natural |
| Pure Pursuit (Coulter, CMU) y Nav2, vía ChatGPT | el goal point va en coordenadas del vehículo | **aceptado como crítica**, motiva §6 |

Ninguna entró al código. Todas se convirtieron en hipótesis falsable primero.

---

## 6. Bloqueos que necesitan el robot

1. **El dato físico del eje de rotación** — la distancia del eje al punto del
   piso que aparece en la fila 119 de la imagen. Robot quieto, una regla. Sin él
   T4 no se decide: el bearing desde el centro óptico y el bearing desde el borde
   del FOV son distintos, y el que importa es desde el eje. **Descartado sacarlo
   de la telemetría**: el robot giró obedeciendo a `steer`, así que
   correlacionarlo con `gz` es circular.
2. **Qué cuesta más: un salto grande o un frame sin autoridad.** Es el trade-off
   central de la candidata y no hay dato offline que lo resuelva.
3. **Si alguno de los 10 videos corresponde a la corrida
   `INVALIDA_ruedas_en_el_aire`.** Hoy no se puede saber: de 60 pares video×CSV
   sólo existe uno enganchado.

---

## 7. Commits de la noche

| SHA | qué |
|---|---|
| `248ac02` | versiona `nuevo_code_v2/v3/v4.py` en la rama, sin modificarlos |
| `91bad09` | `clasificar_huecos.py` — quién abre el hueco |
| `aff50e4` | `atribuir_salto.py` — H1 parcial, H4 refutada |
| `d5497a8` | `bearing_suelo.py` — T4 suspendida |
| `f925a79` | `salto_raw.py` — H5 cae, H6 emerge |
| `033940f`, `7538de5` | `ramas_esqueleto.py` — H7 sin umbral natural |
| `24bfeb1` | `topologia.py` — H6b refutada, las ramas son reales |
| `f06396b` | `ab_v2_v3_v4.py`, `variante_sostiene.py`, `variante_sin_reset.py`, `arquitectura_minima.py` — el A/B y la candidata |

---

## 8. Estado de V2 / V3 / V4

- **`nuevo_code_v2.py`** — sin tocar. Es el núcleo de la candidata. Defectos
  conocidos y medidos: no resetea memoria en PERDIDA (§3.6), `v2:361` falla
  abierto 411 veces, `low_proj` proyecta contra un `last_good_target` que puede
  tener 26 frames.
- **`nuevo_code_v3.py`** — sin tocar. **Candidato a eliminar**: no aporta nada
  medible sobre los 10 videos ni sobre los controles.
- **`nuevo_code_v4.py`** — sin tocar. Su `SpatialTargetGuard` **sí aporta**
  (−89 saltos grandes) y su `reset()`, que parecía un bug, resultó necesario:
  sin él la disponibilidad cae a 73,78 % y fallan los obligatorios.

---

## 9. Qué haría el próximo bloque

1. Medir la métrica que ChatGPT propuso y quedó pendiente: **¿el `raw` cambia de
   rama cuando cambia la topología entre variantes de segmentación?** Es más
   causal que contar hojas.
2. Con H6a ganando, el problema es **selección de rama en el grafo**, no limpieza
   de máscara: probar un criterio de continuidad de rama *dentro* del Dijkstra
   —elegir el camino que más se parece al del frame anterior— en vez de un guard
   posterior.
3. No escribir V5. Si eso funciona, es un cambio *dentro* de la etapa 1.
