p = 'simG/main.py'
raw = open(p, 'rb').read(); crlf = b'\r\n' in raw; s = raw.decode('utf-8'); nl = '\r\n' if crlf else '\n'
print('CRLF', crlf)
# 1) valor por defecto del servicio
a = '    "AMBIGUA_GAP": "1",' + nl
assert s.count(a) == 1
s = s.replace(a, a + '    "GUARD_STOP_GAP": "1",' + nl)
# 2) la bandera, junto a AMBIGUA_GAP
a = 'AMBIGUA_GAP = os.environ.get("AMBIGUA_GAP", "0") == "1"' + nl
assert s.count(a) == 1
s = s.replace(a, a + nl.join([
    '# Al cerrar una recuperacion sin encontrar la cinta, en vez de frenar (GS19) sigue derecho como un GAP:',
    '# mismo avance, mismos limites de la Teensy (50 cm / 8 s) y misma recaptura. 0 = frena como antes.',
    'GUARD_STOP_GAP = os.environ.get("GUARD_STOP_GAP", "0") == "1"', '']))
# 3) el punto donde hoy frena
viejo = nl.join([
    '                    angle = _finish_guard["angle"]',
    '                    if _finish_guard["action"] == "STOP":',
    '                        green_state = GS_PERDIDA_FAILSAFE', ''])
assert s.count(viejo) == 1
nuevo = nl.join([
    '                    angle = _finish_guard["angle"]',
    '                    if _finish_guard["action"] == "STOP" and GUARD_STOP_GAP:',
    '                        # Igual que la rama RECTA de la recuperacion. El guard queda limpio: si no,',
    '                        # al recapturar la cinta volveria a pedir STOP.',
    '                        print("[RECUP-GUARD] sin cinta al cerrar la recuperacion -> busqueda GAP derecho (GUARD_STOP_GAP)")',
    '                        _rec_guard.finish_side = 0',
    '                        _rec_guard.search_t = None',
    '                        _rec_guard.stopped = False',
    '                        _gap_activa = True',
    '                        _gap_origen_superado = False',
    '                        _gap_buenos = 0',
    '                        _gap_failsafe = False',
    '                        _loss_curve_sent_ts = 0.0',
    '                        _curve_latched_decision = None',
    '                        _curve_latch_logged = False',
    '                        _side_seen_raw_lateral = set()',
    '                        _recup_activa = False',
    '                        _recup_armada = False',
    '                        _recup_malos = 0',
    '                        green_state = GS_GAP_BUSQUEDA',
    '                        angle = 0.0',
    '                        _quien = "recup-guard-gap"',
    '                    elif _finish_guard["action"] == "STOP":',
    '                        green_state = GS_PERDIDA_FAILSAFE', ''])
s = s.replace(viejo, nuevo)
open(p, 'wb').write(s.encode('utf-8'))
