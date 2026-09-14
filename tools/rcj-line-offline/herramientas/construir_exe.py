"""Arma dist/RCJ-Line-Offline.exe (Windows) con PyInstaller.

Copia a build/app solo lo que la app necesita para funcionar (sin tests/, herramientas/ ni cambios/)
y lo empaqueta junto con herramientas/lanzador.py en un único .exe que no requiere Python instalado.

Uso (desde cualquier carpeta):
    python tools/rcj-line-offline/herramientas/construir_exe.py
    python tools/rcj-line-offline/herramientas/construir_exe.py --python C:/ruta/venv/Scripts/python.exe

--python: intérprete que tiene PyInstaller instalado (por defecto, el que ejecuta este script).
"""
import argparse
import os
import shutil
import subprocess
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETAS = ['components', 'javascripts', 'stylesheets', 'templates', 'images', 'sounds',
            'scoresheet_generation', 'lang', 'data', 'local', 'icons']
NOMBRE = 'RCJ-Line-Offline'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--python', default=sys.executable)
    args = ap.parse_args()

    build = os.path.join(APP, 'build')
    staging = os.path.join(build, 'app')
    shutil.rmtree(build, ignore_errors=True)
    os.makedirs(staging)
    for carpeta in CARPETAS:
        shutil.copytree(os.path.join(APP, carpeta), os.path.join(staging, carpeta))
    for nombre in os.listdir(APP):
        if nombre.endswith('.html') or nombre.startswith('LICENSE') or nombre in ('manifest.webmanifest', 'sw.js'):
            shutil.copy2(os.path.join(APP, nombre), staging)

    cmd = [args.python, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console',
           '--name', NOMBRE,
           '--add-data', f'{staging}{os.pathsep}app',
           '--distpath', os.path.join(APP, 'dist'),
           '--workpath', os.path.join(build, 'pyinstaller'),
           '--specpath', build]
    icono = os.path.join(APP, 'images', 'favicon.ico')
    with open(icono, 'rb') as f:
        if f.read(4) == b'\x00\x00\x01\x00':
            cmd += ['--icon', icono]
    cmd.append(os.path.join(APP, 'herramientas', 'lanzador.py'))

    print('Ejecutando:', ' '.join(cmd), flush=True)
    subprocess.check_call(cmd)
    exe = os.path.join(APP, 'dist', NOMBRE + '.exe')
    print(f'\nListo: {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
