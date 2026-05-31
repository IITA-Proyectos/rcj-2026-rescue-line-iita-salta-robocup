## Resiliencia R-V08 — `cx_black` sin inicializar: crash 100% reproducible en competencia

**Origen:** auditoría de resiliencia 2026-05-18 (commit `c42e535`). Track B (visión/RPi). Severidad: **ALTA** (crash determinista, no probabilístico).

### Modo de falla
`software/raspberry/final_rpi/Main.py:769-780`: `cx_black` solo se asigna si `np.sum(black_mask[90:, :])` es verdadero. Si hay **verde en pantalla pero sin línea negra en la mitad inferior** (escenario NORMAL en cualquier intersección con verde), `cx_black` queda sin definir y la línea 778 la referencia → `UnboundLocalError`. El loop `while estado == 'linea'` no tiene `try/except`; el `while True` exterior tampoco → **el proceso muere**.

### ¿Se recupera solo HOY?
**NO.** Excepción sube sin captura, mata el proceso. Combinado con la ausencia de systemd (R-V01) = game over de la corrida. **Es 100% reproducible con la pista correcta.**

### Qué falta para self-healing
1. Inicializar `cx_black = width // 2` (valor neutral) antes del bloque condicional.
2. `try/except` en el loop de línea que loguee y continúe (no mate el proceso).

### Test plan (banco)
Poner el robot frente a una zona con marca verde pero sin línea negra en el tercio inferior del frame → con el bug crashea; con el fix sigue operando (va al centro por defecto).

**Régimen:** Track B (visión) — push libre ≤2026-06-11. Fix chico (~2 líneas) pero alto impacto. **Asignar:** @luciouriel2011 @benjaminvillagran @gviollaz.
