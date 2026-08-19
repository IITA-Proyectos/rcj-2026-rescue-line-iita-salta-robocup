# ============================================================================
#  git_commit.py - inyecta el sha corto del commit en el binario, como
#                  -DTLM_COMMIT="afeb995"  (un string literal de C)
#
#  PARA QUE: que cada corrida grabada sepa con QUE firmware se hizo. Sin esto,
#  dos corridas de dos sabados distintos no se pueden comparar: no hay forma de
#  saber si el cambio de comportamiento vino del codigo o de la pista.
#
#  REGLA DE ORO: este script NUNCA puede romper el build. Si git no esta en el
#  PATH, si el repo no aparece, si algo explota -> define "nogit" y sigue. Es
#  preferible una telemetria sin sha antes que no poder compilar en la sede.
#  Por eso TODO esta envuelto en try/except: una excepcion sin capturar tira
#  el build entero.
#
#  Se engancha desde platformio.ini con:  extra_scripts = pre:git_commit.py
#  El prefijo "pre:" es obligatorio (corre antes de compilar).
# ============================================================================
Import("env")

import re
import subprocess

FALLBACK = "nogit"        # que se manda cuando no se pudo averiguar el commit
LARGO_SHA = 7             # + "-s" si el arbol esta sucio => 9 caracteres maximo
ES_SHA = re.compile(r"^[0-9a-f]{4,40}$")   # nada raro entra al JSON de telemetria


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )


def sha_del_commit(proyecto_dir):
    try:
        # git sube solo hasta encontrar el .git (que aca esta 4 niveles arriba,
        # y ademas es un worktree). Por eso alcanza con cwd=proyecto_dir y no
        # hay que hardcodear ../../../.. : si maniana mueven la carpeta del
        # firmware, esto sigue andando.
        r = _git(["rev-parse", "--short=%d" % LARGO_SHA, "HEAD"], proyecto_dir)
        if r.returncode != 0:
            return FALLBACK
        sha = r.stdout.decode("ascii", "ignore").strip()
        if not ES_SHA.match(sha):
            return FALLBACK
        sha = sha[:LARGO_SHA]

        # "-s" = sucio: hay cambios sin commitear DENTRO de la carpeta del
        # firmware. Tocar docs/ no cambia el binario, asi que no ensucia.
        # Un sha que miente es peor que no tener el campo.
        s = _git(["status", "--porcelain", "--", "."], proyecto_dir)
        if s.returncode != 0 or s.stdout.strip():
            sha += "-s"
        return sha
    except Exception:
        return FALLBACK


try:
    sha = sha_del_commit(env.subst("$PROJECT_DIR"))
except Exception:
    sha = FALLBACK

# StringifyMacro se encarga del escape de comillas (en Windows es distinto).
# Como TLM_COMMIT queda siendo un string LITERAL, en main.cpp se concatena
# dentro del format string del snprintf y no gasta ningun argumento variadico:
# es la unica parte del frame v2 que sale gratis en tiempo de ejecucion.
env.Append(CPPDEFINES=[("TLM_COMMIT", env.StringifyMacro(sha))])
print("[git_commit] TLM_COMMIT = %s" % sha)
