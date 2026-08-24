# -*- coding: utf-8 -*-
"""
EMPAQUETAR CONTEXTO - arma UN archivo con el repo para subirlo a una IA externa.

Gemini y compania no pueden clonar el repo. Esto junta el subconjunto que
importa en uno o varios .md, con un manifiesto arriba, y reporta el tamano para
que sepas si entra en la ventana de contexto.

    python3 tools/empaquetar_contexto.py                 # perfil `investigacion`
    python3 tools/empaquetar_contexto.py --perfil todo
    python3 tools/empaquetar_contexto.py --max-mb 8      # parte en varios

PERFILES
  investigacion   lo que hace falta para entender por que el robot no dobla:
                  la candidata, los bancos, el lazo de linea del firmware y los
                  documentos VIGENTES. Es el que conviene por defecto.
  firmware        todo el Teensy.
  vision          todo el Python de la Pi.
  todo            el codigo entero. Grande.

LO QUE NUNCA ENTRA: videos, imagenes, CSV generados, docs/en (es mirror
autogenerado), .pio, __pycache__, y cualquier binario.
"""

import argparse
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXT_TEXTO = {".py", ".cpp", ".h", ".hpp", ".c", ".ini", ".md", ".yml", ".yaml",
             ".json", ".txt", ".cfg"}
NUNCA = ("docs/en/", ".pio/", "__pycache__/", ".git/", "node_modules/",
         "hardware/cad/", "/models/")

PERFILES = {
    "investigacion": [
        # el punto de entrada
        "docs/es/ONBOARDING-IA-EXTERNA.md",
        "CLAUDE.md",
        # la candidata y su linaje
        "software/raspberry/final_rpi/nuevo_code_v2.py",
        "software/raspberry/final_rpi/nuevo_code_v3.py",
        "software/raspberry/final_rpi/nuevo_code_v4.py",
        "software/raspberry/final_rpi/arquitectura_minima.py",
        # como se mide
        "software/raspberry/final_rpi/ab_v2_v3_v4.py",
        "software/raspberry/final_rpi/retro.py",
        "software/raspberry/final_rpi/retro_guard_exp.py",
        "software/raspberry/final_rpi/pursuit.py",
        "software/raspberry/final_rpi/auditoria_fisica.py",
        "software/raspberry/final_rpi/posicion_vs_rumbo.py",
        "software/raspberry/final_rpi/target_fuera_del_path.py",
        "software/raspberry/final_rpi/bench_runtime.py",
        "software/raspberry/final_rpi/shadow_pi.py",
        # el lazo real
        "software/raspberry/final_rpi/Main.py",
        "software/raspberry/final_rpi/camthreader.py",
        "software/raspberry/final_rpi/telemetria_vision.py",
        "software/teensy/firmware/src/priority_fix_flags.h",
        "software/teensy/firmware/src/main.cpp",
        "software/teensy/firmware/lib/drivebase/drivebase.cpp",
        # protocolo del sabado y bancos
        "software/raspberry/final_rpi/PROTOCOLO_SABADO.md",
        "software/raspberry/final_rpi/BENCH_RUNTIME.md",
        "software/raspberry/final_rpi/medir_eje.py",
        "software/raspberry/final_rpi/preflight_sabado.py",
        # las skills nuevas: son el marco conceptual
        ".claude/skills/seguimiento-de-trayectoria/SKILL.md",
        ".claude/skills/geometria-camara-suelo/SKILL.md",
        ".claude/skills/experimento-falsable/SKILL.md",
    ],
    "firmware": ["software/teensy/"],
    "vision": ["software/raspberry/"],
    "todo": ["software/", "docs/es/", ".claude/skills/"],
}


def excluido(rel):
    r = rel.replace("\\", "/")
    return any(n in ("/" + r) or r.startswith(n.lstrip("/")) for n in NUNCA)


def expandir(entradas):
    out = []
    for e in entradas:
        p = os.path.join(RAIZ, e)
        if os.path.isfile(p):
            out.append(e.replace("\\", "/"))
        elif os.path.isdir(p):
            for base, _d, files in os.walk(p):
                for f in sorted(files):
                    fp = os.path.join(base, f)
                    rel = os.path.relpath(fp, RAIZ).replace("\\", "/")
                    if excluido(rel):
                        continue
                    if os.path.splitext(f)[1].lower() in EXT_TEXTO:
                        out.append(rel)
    vistos = set()
    return [x for x in out if not (x in vistos or vistos.add(x))]


def git(args):
    try:
        return subprocess.check_output(["git", "-C", RAIZ] + args,
                                       stderr=subprocess.DEVNULL
                                       ).decode("utf-8", "replace").strip()
    except Exception:
        return "?"


def leer(rel):
    try:
        with open(os.path.join(RAIZ, rel), "r", encoding="utf-8",
                  errors="replace") as f:
            return f.read()
    except Exception as e:
        return "(no se pudo leer: %s)" % e


def lenguaje(rel):
    return {".py": "python", ".cpp": "cpp", ".h": "cpp", ".c": "c",
            ".md": "markdown", ".ini": "ini"}.get(
                os.path.splitext(rel)[1].lower(), "")


CABECERA = """# Contexto del repo — RoboCupJunior Rescue Line, equipo IITA Salta

Empaquetado automatico con `tools/empaquetar_contexto.py`.
Perfil: **%s** · rama **%s** · commit **%s** · %d archivos · parte %d de %d

## Antes de leer nada mas

Este paquete existe para que una IA externa tenga contexto **sin poder clonar el
repo**. Tres reglas:

1. **El idioma fuente es el espanol.** Todo lo que produzcas va en espanol.
2. **No inventes resultados fisicos.** El robot esta disponible pocas horas; si
   algo no esta medido, decilo en vez de estimarlo.
3. **Toda afirmacion nueva necesita un falsador escrito antes de medir.** Ver
   la skill `experimento-falsable` incluida en este paquete: documenta cuatro
   errores estadisticos reales que ya cometimos, para que no se repitan.

El punto de entrada conceptual es `docs/es/ONBOARDING-IA-EXTERNA.md`, incluido
mas abajo si el perfil lo trae.

---

## Manifiesto

%s

---

"""


def main():
    ap = argparse.ArgumentParser(description="Empaquetar el repo para una IA")
    ap.add_argument("--perfil", default="investigacion",
                    choices=sorted(PERFILES))
    ap.add_argument("--max-mb", type=float, default=8.0, dest="max_mb")
    ap.add_argument("--salida", default="contexto_para_ia")
    a = ap.parse_args()

    # Se calcula ANTES de expandir: `expandir` descarta lo que no existe, asi
    # que si se mira despues la lista sale vacia y una omision pasa callada.
    faltan = [e for e in PERFILES[a.perfil]
              if not os.path.exists(os.path.join(RAIZ, e))]
    rels = expandir(PERFILES[a.perfil])

    bloques = []
    for r in rels:
        txt = leer(r)
        bloques.append((r, len(txt), "## `%s`\n\n```%s\n%s\n```\n\n"
                        % (r, lenguaje(r), txt)))

    total = sum(b[1] for b in bloques)
    lim = int(a.max_mb * 1e6)
    partes, actual, acum = [], [], 0
    for b in bloques:
        if acum + b[1] > lim and actual:
            partes.append(actual)
            actual, acum = [], 0
        actual.append(b)
        acum += b[1]
    if actual:
        partes.append(actual)

    rama, sha = git(["rev-parse", "--abbrev-ref", "HEAD"]), git(
        ["rev-parse", "--short", "HEAD"])
    escritos = []
    for k, parte in enumerate(partes, 1):
        man = "\n".join("- `%s` — %d caracteres" % (r, n) for r, n, _ in parte)
        cab = CABECERA % (a.perfil, rama, sha, len(parte), k, len(partes), man)
        nombre = ("%s_%s.md" % (a.salida, a.perfil) if len(partes) == 1
                  else "%s_%s_parte%d.md" % (a.salida, a.perfil, k))
        ruta = os.path.join(RAIZ, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(cab)
            for _r, _n, cuerpo in parte:
                f.write(cuerpo)
        escritos.append((nombre, os.path.getsize(ruta)))

    print("")
    print("  perfil %s   rama %s   commit %s" % (a.perfil, rama, sha))
    print("  %d archivos, %.2f MB de texto" % (len(rels), total / 1e6))
    print("  ~%d k tokens estimados (4 caracteres por token)" % (total / 4000))
    if faltan:
        print("")
        print("  NO ENCONTRADOS (se saltearon):")
        for f in faltan:
            print("    - %s" % f)
    print("")
    for n, s in escritos:
        print("  %-44s %6.2f MB" % (n, s / 1e6))
    print("")
    print("  Los .md generados estan en .gitignore: son derivados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
