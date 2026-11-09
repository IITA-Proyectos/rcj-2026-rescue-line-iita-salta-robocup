from pathlib import Path
B=Path(__file__).resolve().parent
s=(B/'main_base.py').read_text(encoding='utf-8')
def replace(old,new):
    global s
    assert s.count(old)==1,old[:100]
    s=s.replace(old,new)
replace('from verde_oscuro import detectar_verde_oscuro\n',
        'from verde_oscuro import detectar_verde_oscuro\nfrom recuperacion_guard import RecoveryGuard\n_rec_guard = RecoveryGuard()\n')
replace("        while estado == 'linea':", "        _rec_guard.reset()\n        print('[RECUP-GUARD] ' + RecoveryGuard.VERSION)\n\n        while estado == 'linea':")
replace('            if RECUP and RETROCEDER:\n                _now_rec = time.monotonic()',
'''            if RECUP and RETROCEDER:
                _now_rec = time.monotonic()
                if not _recup_activa and not _gap_activa and green_state == 0:
                    _rec_guard.observe(_mm)''')
replace('                if _marca_prioritaria:\n                    _recup_activa = False',
'''                if _marca_prioritaria:
                    _rec_guard.reset()
                    _recup_activa = False''')
replace('                            # REV3: despues de TERM_HARD + SIDE_CHECK, congelar',
'''                            # Contrastar la decision final con evidencia previa al retroceso.
                            if _curve_latched_decision is None:
                                _dec, _guard_change = _rec_guard.decide(
                                    _dec, _term_episode_evidence,
                                    max(0.0, _now_rec - _loss_retro_ts) if _loss_retro_ts else 0.0,
                                    PERDIDA_AMBIGUA_MAX_S)
                                _loss_decision = _dec
                                if _guard_change:
                                    print("[RECUP-GUARD] %s side=%s heading=%s" %
                                          (_guard_change, _dec.get("side"), _dec.get("heading")))

                            # REV3: despues de TERM_HARD + SIDE_CHECK, congelar''')
replace('                                    if _cg is not None:\n                                        _cg.soltar(int(_dec.get("side") or 0), _now_rec)',
'''                                    _rec_guard.begin_finish(int(_dec.get("side") or 0), _now_rec)
                                    if _cg is not None:
                                        _cg.soltar(int(_dec.get("side") or 0), _now_rec)''')
replace('                                _recup_inicio_ts = _now_rec\n                                _loss_retro_done = False',
'''                                _recup_inicio_ts = _now_rec
                                print("[RECUP-GUARD] evidencia=%s" % _rec_guard.freeze())
                                _loss_retro_done = False''')
replace('            output = send_frame(speed, round(angle), green_state, silver_line)',
'''            # Solo el cierre de una recuperacion lateral; GAP y marcas conservan prioridad.
            if RECUP and RETROCEDER and green_state == 0:
                _finish_guard = _rec_guard.finish(time.monotonic(), _mm, black_mask, angle)
                if _finish_guard is not None:
                    angle = _finish_guard["angle"]
                    if _finish_guard["action"] == "STOP":
                        green_state = GS_PERDIDA_FAILSAFE
                        _gap_failsafe = True
                        _recup_activa = False
                        _recup_armada = False
                        _quien = "recup-guard-stop"
                    else:
                        _quien = "recup-guard-completa"

            output = send_frame(speed, round(angle), green_state, silver_line)''')
(B/'main.py').write_text(s,encoding='utf-8',newline='\n')
