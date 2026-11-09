# Seguir derecho en vez de frenar al cerrar una recuperación — 8-nov-2026

**Estado:** instalado en la Pi el 8-nov (`main.py` `ff6d0c9289ff2875…`). **Falta probarlo en pista.**

## Qué cambia

Cuando una recuperación termina sin encontrar la cinta, el robot antes se frenaba (`recup-guard-stop`, GS 19) y quedaba quieto. Ahora sigue derecho como en un GAP (GS 18):

- avanza recto a la velocidad de GAP;
- cuando ve la cinta conectada, vuelve al seguimiento normal;
- si no la encuentra, frena en el límite que la Teensy ya tiene para el GAP: 50 cm u 8 s.

Es solo `main.py` en la Pi. La Teensy no cambia. La búsqueda previa de 1 s (reenganche) sigue igual, y el GS 19 por agotar un GAP también.

En el log aparece: `[RECUP-GUARD] sin cinta al cerrar la recuperacion -> busqueda GAP derecho (GUARD_STOP_GAP)`.

## Comprobación

Simulador por tramos, contra lo instalado antes de este cambio (con el arreglo del verde ya incluido):

| Datos | Cuadros | Tramos | Resultado |
|---|---:|---:|---|
| 14 corridas (31-oct a 8-nov) | 167.772 | 285 | 230 tramos idénticos. En los 55 restantes, el primer cuadro distinto es siempre ese freno convertido en avance |

- De esos 55, en 40 el robot real estaba en GS 19 en ese mismo cuadro.
- Prueba de la transición completa: pérdida, freno convertido en GAP, aviso de origen, recaptura y seguimiento normal, sin volver a pedir el freno.
- El calibrador de ChatGPT sigue reconociendo el archivo.

El simulador es a lazo abierto: confirma qué decide la Pi, pero no por dónde va a ir el robot. Eso solo se ve en pista.

## Qué mirar en pista

- Las esquinas donde se quedaba quieto: tiene que seguir derecho.
- Entrada al plateado: 14 de los 55 casos son de la prueba del 7-nov 18:41. Si queda mirando la pared, ahora avanza contra la pared hasta el límite, en vez de quedarse quieto.

## Volver atrás

```bash
cp -p /home/iita/Desktop/respaldo_gap_tras_stop_20261108/main.py /home/iita/Desktop/
```

O solo para una corrida a mano: `GUARD_STOP_GAP=0 python3 -u main.py`.
