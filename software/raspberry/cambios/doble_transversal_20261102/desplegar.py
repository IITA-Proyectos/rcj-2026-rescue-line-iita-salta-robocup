"""Instalar con robot detenido. No inicia ni detiene el robot."""
import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def install(desktop):
    here=Path(__file__).resolve().parent
    target=desktop/'doble_dato.py'
    expected=sha(here/'doble_dato_base.py')
    if sha(target)!=expected:
        raise ValueError('El doble_dato.py actual no es la referencia verificada. No se instala ni sobrescribe.')
    tree=ast.parse((desktop/'main.py').read_text(encoding='utf-8-sig'))
    values={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for name in node.targets:
                if isinstance(name,ast.Name) and name.id in ('lower_green','upper_green','upper_black'):
                    values[name.id]=ast.literal_eval(node.value.args[0])
    if values!={'lower_green':[120,90,110],'upper_green':[198,109,134],'upper_black':[90,90,90]}:
        raise ValueError('Los colores de main son distintos de los verificados. No se instala; conservar calibracion actual.')
    names=['doble_dato.py','doble_transversal.py']
    for name in names:compile((here/name).read_text(encoding='utf-8'),name,'exec')
    backup=desktop/('respaldo_doble_transversal_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    existed={name:(desktop/name).exists() for name in names}
    for name in names:
        if existed[name]:shutil.copy2(desktop/name,backup/name)
    (backup/'archivos_previos.json').write_text(json.dumps(existed,indent=2),encoding='utf-8')
    # Comprobar de nuevo para no pisar una edicion que llego durante el respaldo.
    if sha(target)!=expected:raise ValueError('El archivo cambio durante el respaldo; no se instala')
    try:
        for name in names:
            temp=desktop/(name+'.nuevo')
            shutil.copy2(here/name,temp)
            os.replace(temp,desktop/name)
        for name in names:
            if sha(desktop/name)!=sha(here/name):raise ValueError('Verificacion de copia fallo: '+name)
    except Exception:
        for name in names:
            if existed[name]:shutil.copy2(backup/name,desktop/name)
            elif (desktop/name).exists():(desktop/name).unlink()
        raise
    print('Instalado para el proximo arranque. No se modifico main ni se inicio el robot.')
    print('Respaldo:',backup)
    return backup


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop',type=Path,default=Path('/home/iita/Desktop'))
    args=parser.parse_args()
    install(args.desktop.resolve())
