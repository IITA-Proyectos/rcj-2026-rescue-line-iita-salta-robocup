# Corridas del 2026-08-22 — las primeras que corrieron en el robot

Hasta este día **nada de todo el diagnóstico había corrido en el robot**: 9 entornos que
compilaban y 9 herramientas que parseaban, y nada más. Estas son las primeras mediciones
reales. Se guardan crudas y con su procedencia adentro (la línea `# hz=... commit=...`),
que es lo que permite comparar una corrida de hoy contra una de dentro de dos meses.

| archivo | qué es |
|---|---|
| `2026-08-22_banco_piso_historico.csv` | **la línea de base.** Barrido completo, 24 segmentos, lazo histórico (`fix_lazo=0`), cuatro ruedas sobre la pista |
| `2026-08-22_banco_piso_con_fixes.csv` | el mismo barrido con `FIX_LAZO_MOTOR` y `FIX_CURVA_CONTINUA`. 16 segmentos: el grabador enganchó a mitad de la secuencia |
| `2026-08-22_INVALIDA_ruedas_en_el_aire.csv` | **no usar para concluir.** El barrido arrancó solo al bootear con el switch en ON y el robot no estaba apoyado. Se guarda porque es un buen ejemplo de cómo se ve una corrida en el aire: giroscopio en 0,0 d/s y ruedas a 145-195 rpm (velocidad libre) |
| `2026-08-22_PARCIAL_solo_la_cola.csv` | sólo `rotation` 0,85 y 1,00. Se guarda como ejemplo de corrida incompleta |

## Lo que dijeron

    python tools/analizar_barrido.py corridas/2026-08-22_banco_piso_historico.csv

                              sin fixes   con fixes
    rendimiento rot <= 0,50     0,871       0,874
    rendimiento 0,50 - 0,95     0,906       0,884
    rendimiento rot  = 1,00     0,904       0,902
    ruido del banco             0,046       0,045
    colapso                     ninguno     ninguno

**El rendimiento de giro es PLANO**, o sea que por cada unidad de consigna el robot entrega
el mismo giro en todo el rango, con carga y sobre la pista. Eso mata las dos hipótesis que
venían de junio:

- **PID ciego al signo**: ninguna rueda colapsó en ningún segmento de ninguna corrida. La
  rueda interna sigue su consigna: en `rot=0,85` pide 31 rpm y mide 31; en `rot=1,00` pide
  45 y mide 45.
- **Techo de par**: el giro escala con `rotation` y con la velocidad. De 25 a 70 rpm el
  rendimiento cambia 0 %.

Y los dos fixes son **neutros**: no mejoran la actuación —no había nada que mejorar— pero
tampoco la degradan, así que `competencia_fix` no rompe nada.

El piso anti-coast se ve funcionando: en `rot=0,40` el PWM mínimo pasa de 0 (histórico) a
20 (con fix), que es exactamente `MOTO_PWM_ANTICOAST`, sin distorsionar el giro.

## Dónde quedó el problema

Si la actuación es fiel, el problema está **aguas arriba de los motores**: en qué `rotation`
se le pide. Lo que sigue es una corrida de pista con la cámara, mirando las columnas
`rxsteer` (el ángulo que mandó la Raspberry) contra `rot` (lo que decidió el drivebase).

## Cómo NO medir

Tres formas de arruinar una corrida, las tres pasadas hoy:

1. **Con las ruedas en el aire.** Se detecta solo: el giroscopio da ~0 y las ruedas van a
   velocidad libre. El analizador se niega a dar veredicto.
2. **Enganchando la cola de un barrido anterior.** El archivo parece completo pero le
   faltan las rotations bajas. El grabador ahora exige empezar por una `rotation` baja.
3. **Midiendo un binario que no es el que se creía haber subido.** `pio run --target upload`
   reporta **SUCCESS aunque el Teensy no haya entrado en modo programación**. Hay que
   apretar el pulsador de la placa y después verificar contra la línea de procedencia que
   emite la propia Teensy, no contra el mensaje del cargador.
