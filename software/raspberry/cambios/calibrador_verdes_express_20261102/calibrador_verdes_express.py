"""Calibrador local, sin serial ni motores. Lee el detector elegido sin importar main.

g/n: guardar ROI verde/negativa; 0/1/2/3: escena de prueba independiente.
c: ajustar; s: guardar perfil si pasa; espacio: pausa; z: deshacer; q: salir.
--apply PERFIL: instalar SOLO rangos de color, con respaldo y verificacion de hashes.
"""
import argparse
import ast
import datetime
import csv
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import time
import zipfile
from types import SimpleNamespace

import cv2
import numpy as np

VERSION = 'VERDES-EXPRESS-2'
NAMES = ('main.py', 'verde_oscuro.py', 'doble_dato.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_source(path):
    return path.read_text(encoding='utf-8-sig')


def assignment(tree, name):
    found = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    if len(found) != 1:
        raise ValueError('Se esperaba una asignacion unica: ' + name)
    return found[0]


def constant(tree, name):
    value = assignment(tree, name).value
    if isinstance(value, ast.Call) and ast.unparse(value.func) == 'np.array':
        value = value.args[0]
    return ast.literal_eval(value)


def load_local(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(path.parent.resolve()))
    try:spec.loader.exec_module(module)
    finally:sys.path.pop(0)
    return module


def shadow_floor_node(tree):
    matches=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and ast.unparse(n.func)=='min'
             and len(n.args)==2 and ast.unparse(n.args[0])=='int(lower[0])']
    if len(matches)!=1 or not isinstance(matches[0].args[1],ast.Constant):
        raise ValueError('No se reconoce el limite de sombra; no se modifica el helper')
    return matches[0].args[1]


class Detector:
    def __init__(self, main):
        self.main = main.resolve()
        self.root = self.main.parent
        self.paths = {name: self.root / name for name in NAMES}
        self.paths['main.py'] = self.main
        extra=self.root/'doble_transversal.py'
        if extra.exists() and 'from doble_transversal import EarlyDouble' in read_source(self.paths['doble_dato.py']):
            self.paths['doble_transversal.py']=extra
        self.hashes = {name: digest(path) for name, path in self.paths.items()}
        source = read_source(self.main)
        tree = ast.parse(source)
        self.lower = constant(tree, 'lower_green')
        self.upper = constant(tree, 'upper_green')
        self.black_lower = constant(tree, 'lower_black')
        self.black_upper = constant(tree, 'upper_black')
        self.minimum = constant(tree, 'min_square_size')
        self.guard = constant(tree, 'ENABLE_CX_BLACK_GUARD')
        # Misma opcion de doble que el main elegido, respetando el entorno.
        default = '0'
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == 'DOBLE_SIN_FACTOR':
                        default = ast.literal_eval(value)
        self.factor = 1.0 if os.getenv('DOBLE_SIN_FACTOR', default) == '1' else 1.2
        self.dark = load_local(self.paths['verde_oscuro.py'], '_verde_calibracion')
        shadow_source=textwrap.dedent(inspect.getsource(self.dark.detectar_verde_sombra))
        self.shadow_tree=ast.parse(shadow_source)
        self.base_shadow_floor=int(ast.literal_eval(shadow_floor_node(self.shadow_tree)))
        self.shadow_floor=self.base_shadow_floor
        self.shadow_functions={self.base_shadow_floor:self.dark.detectar_verde_sombra}
        self.double = load_local(self.paths['doble_dato.py'], '_doble_calibracion')
        self.pair_source=textwrap.dedent(inspect.getsource(self.double.DoubleData().visible_pair))
        # Extraer exclusivamente las decisiones de verde del archivo real.
        first = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                 and ast.unparse(n.test).startswith('np.sum(green_mask) > min_square_size')]
        last = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Call)
                and ast.unparse(n.value.func) == '_double_data.step']
        if len(first) != 1 or len(last) != 1:
            raise ValueError('Version de main no reconocida: no se ejecuta ni se modifica')
        lines = source.splitlines()
        body = textwrap.dedent('\n'.join(lines[first[0].lineno-1:last[0].end_lineno]))
        function = ast.parse('def evaluate():\n    green_mask = _initial_green_mask.copy()\n' + textwrap.indent(body, '    ')
                             + '\n    return green_state\n')
        # Quitar solo los mensajes de consola del bloque extraido.
        for node in ast.walk(function):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id == 'print':
                    node.value = ast.Constant(None)
        self.code = compile(ast.fix_missing_locations(function), str(self.main), 'exec')

    def ranges(self, lower, upper, shadow_floor=None):
        low, high = np.array(lower, np.uint8), np.array(upper, np.uint8)
        dark = low.copy(); dark[0] = min(int(low[0]), 100)
        floor=self.shadow_floor if shadow_floor is None else shadow_floor
        shadow = low.copy(); shadow[0] = min(int(low[0]), int(floor))
        shigh = high.copy()
        shigh[1] = max(int(high[1]), 111)
        shigh[2] = max(int(high[2]), 137)
        return [(low, high), (dark, high), (shadow, shigh), (shadow, shigh)]

    def shadow_function(self, proposed):
        floor=self.shadow_floor if proposed else self.base_shadow_floor
        if floor not in self.shadow_functions:
            tree=ast.parse(ast.unparse(self.shadow_tree))
            node=shadow_floor_node(tree)
            node.value=int(floor)
            env=dict(self.dark.__dict__)
            exec(compile(ast.fix_missing_locations(tree),'<sombra-calibrada>','exec'),env)
            self.shadow_functions[floor]=env['detectar_verde_sombra']
        return self.shadow_functions[floor]

    def masks(self, image, lower, upper):
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        result = []
        for i, (lo, hi) in enumerate(self.ranges(lower, upper)):
            mask = np.zeros((120, 160), np.uint8)
            start = 70 if i == 3 else 80
            mask[start:] = cv2.inRange(lab[start:], lo, hi)
            result.append(mask)
        return result

    def evaluate(self, image, lower, upper, proposed=True, double_instance=None, timestamp=None):
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        black = cv2.inRange(image, np.array(self.black_lower), np.array(self.black_upper))
        black[:60] = 0
        double = double_instance if double_instance is not None else self.double.DoubleData()
        if proposed:
            # Probar el MISMO algoritmo de doble con los nuevos colores,
            # sin reemplazar su geometria o sus tiempos.
            tree = ast.parse(self.pair_source)
            candidates = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                          and ast.unparse(n.func) == 'cv2.inRange']
            if len(candidates) != 1:
                raise ValueError('Rango del doble no reconocido')
            lo, hi = self.ranges(lower, upper)[3]
            candidates[0].args[1] = ast.parse('np.array(%r)' % lo.tolist()).body[0].value
            candidates[0].args[2] = ast.parse('np.array(%r)' % hi.tolist()).body[0].value
            tree.body[0].decorator_list = []
            env = dict(cv2=cv2, np=np)
            exec(compile(ast.fix_missing_locations(tree), '<doble-calibrado>', 'exec'), env)
            double.visible_pair = env['visible_pair']
            if hasattr(double,'configure_colors'):
                double.configure_colors(lo,hi)
        clock=time if timestamp is None else SimpleNamespace(monotonic=lambda:timestamp)
        env = dict(cv2=cv2, np=np, time=clock, frame_resized=image, lab=lab,
                   black_mask=black, _initial_green_mask=self.masks(image, lower, upper)[0],
                   lower_green=np.array(lower), upper_green=np.array(upper),
                   min_square_size=self.minimum, FACTOR_DOBLE=self.factor,
                   ENABLE_CX_BLACK_GUARD=self.guard, kernel=np.ones((3,3), np.uint8),
                   detectar_verde_oscuro=self.dark.detectar_verde_oscuro,
                   detectar_verde_sombra=self.shadow_function(proposed),
                   _double_data=double)
        exec(self.code, env)
        return int(env['evaluate']())


def quadrilateral(points):
    coords=np.asarray(points,dtype=np.int32)
    if coords.shape != (4,2) or len(np.unique(coords,axis=0)) != 4:
        raise ValueError('Marcar cuatro esquinas diferentes')
    hull=cv2.convexHull(coords).reshape(-1,2)
    if len(hull)!=4 or cv2.contourArea(hull)<12:
        raise ValueError('El ultimo punto forma un triangulo: elegir una esquina exterior')
    return hull.tolist()


def sample_pixels(image, item):
    """Sólo píxeles dentro del polígono, no su rectángulo envolvente."""
    if image is None:raise ValueError('Imagen de muestra no disponible')
    mask=np.zeros(image.shape[:2],np.uint8)
    if 'polygon' in item:
        points=np.array(quadrilateral(item['polygon']),np.int32)
        if (points<0).any() or (points[:,0]>=image.shape[1]).any() or (points[:,1]>=image.shape[0]).any():
            raise ValueError('Puntos fuera de la imagen')
        cv2.fillConvexPoly(mask,points,255)
    else:
        x,y,w,h=item['roi']
        if x<0 or y<0 or w<1 or h<1 or x+w>image.shape[1] or y+h>image.shape[0]:
            raise ValueError('Rectangulo fuera de la imagen')
        mask[y:y+h,x:x+w]=255
    pixels=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)[mask>0]
    if len(pixels)<16:raise ValueError('Seleccion demasiado pequena: minimo 16 pixeles')
    return pixels


def fit(samples):
    lows, highs = [], []
    for item in samples:
        if item['kind'] != 'green':
            continue
        image = cv2.imread(item['image'])
        pixels = sample_pixels(image,item)
        if len(pixels) < 16:
            raise ValueError('Seleccion verde demasiado pequena')
        lows.append(np.percentile(pixels, 2, axis=0))
        highs.append(np.percentile(pixels, 98, axis=0))
    if len(lows) < 3:
        raise ValueError('Faltan 3 selecciones verdes: luz, sombra y lateral/rampa')
    return (np.floor(np.min(lows,axis=0)-3).clip(0,255).astype(int).tolist(),
            np.ceil(np.max(highs,axis=0)+3).clip(0,255).astype(int).tolist())


def fit_for_detector(samples, detector):
    """Ampliar lo minimo necesario, preservando la prioridad principal/oscuro/sombra."""
    suggested_low,suggested_high=fit(samples)
    low,high=np.array(detector.lower),np.array(detector.upper)
    floor=detector.base_shadow_floor
    positives=[sample_pixels(cv2.imread(s['image']),s) for s in samples if s['kind']=='green']
    negatives=[sample_pixels(cv2.imread(s['image']),s) for s in samples if s['kind']=='negative']
    def score(lo,hi,floor_value):
        ranges=detector.ranges(lo,hi,floor_value)
        coverage=[max(np.mean(np.all((pixels>=a)&(pixels<=b),axis=1)) for a,b in ranges[:3]) for pixels in positives]
        rates=[max(np.mean(np.all((pixels>=a)&(pixels<=b),axis=1))
                   for a,b in ranges) for pixels in negatives]
        cost=int(np.abs(lo-detector.lower).sum()+np.abs(hi-detector.upper).sum()+abs(floor_value-detector.base_shadow_floor))
        return (sum(rate>.02 for rate in rates),sum(rate<.90 for rate in coverage),
                sum(max(0,.90-rate) for rate in coverage),max(rates,default=0),sum(rates),cost)
    for _ in range(8):
        current=score(low,high,floor)
        if current[0]==0 and current[1]==0:break
        best=None
        for value in range(min(suggested_low[0],floor),floor):
            trial=score(low,high,value)
            if trial<current and (best is None or trial<best[0]):best=(trial,low.copy(),high.copy(),value)
        for channel in range(3):
            for upper in (False,True):
                values=(range(int(high[channel])+1,max(int(high[channel]),suggested_high[channel])+1) if upper else
                        range(min(int(low[channel]),suggested_low[channel]),int(low[channel])))
                for value in values:
                    lo,hi=low.copy(),high.copy()
                    (hi if upper else lo)[channel]=value
                    trial=score(lo,hi,floor)
                    if trial>=current:continue
                    if best is None or trial<best[0]:best=(trial,lo,hi,floor)
        if best is None:break
        _,low,high,floor=best
    detector.shadow_floor=int(floor)
    return low.tolist(),high.tolist()


def load_samples(path):
    samples=json.loads(path.read_text(encoding='utf-8'))
    for item in samples:
        if not Path(item['image']).is_absolute():item['image']=str((path.parent/item['image']).resolve())
        for frame in item.get('context',[]):
            if not Path(frame['image']).is_absolute():frame['image']=str((path.parent/frame['image']).resolve())
        for frame in item.get('future',[]):
            if not Path(frame['image']).is_absolute():frame['image']=str((path.parent/frame['image']).resolve())
    return samples


def sample_signature(item):
    shape=tuple(tuple(p) for p in item['polygon']) if 'polygon' in item else tuple(item.get('roi',[]))
    return (item['kind'],item.get('frame_key') or frame_key(cv2.imread(item['image'])),
            item.get('expected'),shape,item.get('assessment','frame'))


def remove_identical_duplicates(samples):
    result=[]
    seen={}
    for item in samples:
        key=sample_signature(item)
        if key in seen:
            original=result[seen[key]]
            if not original.get('source') and item.get('source'):original['source']=item['source']
            continue
        seen[key]=len(result)
        result.append(dict(item))
    return result


def scene_frames(item):
    """Contexto real de la misma fuente, nunca repite el cuadro para inventar confirmacion."""
    if item.get('context'):
        result=[]
        for frame in item['context']:
            image=cv2.imread(frame['image'])
            if image is None:return []
            result.append((image,float(frame['t'])))
        return result
    source=item.get('source',{})
    path=Path(source.get('image',''))
    if source.get('image') and path.exists() and path.stem.startswith('f_') and path.stem[2:].isdigit():
        number=int(path.stem[2:])
        timestamps={}
        log=path.parent/'cuadros.csv'
        if log.exists():
            with log.open() as stream:timestamps={int(r['n']):float(r['t']) for r in csv.DictReader(stream)}
        result=[]
        for n in range(max(1,number-25),number+1):
            image_path=path.with_name('f_%06d.png'%n)
            if not image_path.exists():continue
            image=cv2.imread(str(image_path))
            if image is None:return []
            result.append((image,timestamps.get(n,n/20.)))
        return result if len(result)>=3 else []
    if source.get('video') and Path(source['video']).exists():
        video=VideoFrames(Path(source['video']),source.get('rotate',False))
        try:
            index=int(source['frame'])
            return [(video.read(n),n/video.fps) for n in range(max(0,index-25),index+1)]
        finally:video.release()
    return []


def scene_future(item):
    if item.get('future'):
        result=[]
        for frame in item['future']:
            image=cv2.imread(frame['image'])
            if image is None:return []
            result.append((image,float(frame['t'])))
        return result
    source=item.get('source',{})
    path=Path(source.get('image',''))
    if source.get('image') and path.exists() and path.stem.startswith('f_') and path.stem[2:].isdigit():
        number=int(path.stem[2:]);timestamps={}
        log=path.parent/'cuadros.csv'
        if log.exists():
            with log.open() as stream:timestamps={int(r['n']):float(r['t']) for r in csv.DictReader(stream)}
        result=[]
        for n in range(number+1,number+11):
            candidate=path.with_name('f_%06d.png'%n)
            if not candidate.exists():break
            image=cv2.imread(str(candidate))
            if image is None:break
            result.append((image,timestamps.get(n,n/20.)))
        return result
    if source.get('video') and Path(source['video']).exists():
        video=VideoFrames(Path(source['video']),source.get('rotate',False))
        try:
            index=int(source['frame'])
            return [(video.read(n),n/video.fps) for n in range(index+1,min(video.total,index+11))]
        finally:video.release()
    return []


def classify_scene(detector,image,frames,lower,upper,proposed,assessment='frame'):
    if len(frames)<3:return detector.evaluate(image,lower,upper,proposed)
    state=detector.double.DoubleData()
    result=0
    for frame,timestamp in frames:
        result=detector.evaluate(frame,lower,upper,proposed,state,timestamp)
        if assessment=='entry' and result in (1,2,3):return result
    return result


def validate(detector, samples, lower, upper):
    report, errors = [], []
    negatives = 0
    scenes = set()
    independent_scenes=set()
    fit_keys={frame_key(cv2.imread(s['image'])) for s in samples if s['kind']=='green'}
    color_errors=[]
    decision_errors=[]
    for item in samples:
        image = cv2.imread(item['image'])
        if image is None:
            raise ValueError('No se pudo leer ' + item['image'])
        if item['kind'] == 'scene':
            wanted = item['expected']
            scenes.add(wanted)
            context=scene_frames(item)
            if context and frame_key(context[-1][0])!=frame_key(image):
                raise ValueError('El contexto no termina en la imagen etiquetada: '+Path(item['image']).name)
            assessment=item.get('assessment','frame')
            future=scene_future(item) if assessment=='entry' else []
            frames=context+future if assessment=='entry' else context
            actual=classify_scene(detector,image,frames,lower,upper,True,assessment)
            old=classify_scene(detector,image,frames,detector.lower,detector.upper,False,assessment)
            independent=frame_key(image) not in fit_keys
            if independent:independent_scenes.add(wanted)
            report.append(dict(image=item['image'], expected=wanted, before=old, after=actual,
                               context_frames=len(context),future_frames=len(future),assessment=assessment,independent_frame=independent))
            if assessment=='entry' and (len(context)<3 or not future):
                decision_errors.append('Entrada sin secuencia suficiente: '+Path(item['image']).name)
            if actual != wanted:
                message=('%s %s: esperaba %d, da %d' %
                         ('PROTECCION' if item.get('protected') else 'Escena',Path(item['image']).name,wanted,actual))
                if wanted==3 and len(context)<3 and 'doble_transversal.py' in detector.hashes:
                    message+='; cuadro aislado: falta contexto real para confirmar el doble'
                decision_errors.append(message)
        else:
            lab = sample_pixels(image,item).reshape(-1,1,3)
            rates = [float(np.mean(cv2.inRange(lab, lo, hi)>0))
                     for lo,hi in detector.ranges(lower,upper)]
            report.append(dict(image=item['image'], kind=item['kind'], fractions=rates))
            if item['kind'] == 'negative':
                negatives += 1
                if max(rates) > .02:
                    color_errors.append('Negativo confundido: ' + Path(item['image']).name)
            elif max(rates[:3]) < .90:
                color_errors.append('Verde incompleto: ' + Path(item['image']).name)
    if negatives < 3:
        color_errors.append('Faltan 3 negativos: blanco/reflejo, negro y plateado/otro piso')
    if scenes != {0,1,2,3}:
        decision_errors.append('Faltan pruebas 0=descartar, 1=izq, 2=der, 3=doble')
    if independent_scenes!={0,1,2,3}:
        decision_errors.append('Faltan pruebas nuevas sin reutilizar imagenes del ajuste: '+str(sorted({0,1,2,3}-independent_scenes)))
    errors=color_errors+decision_errors
    return dict(passed=not errors,color_passed=not color_errors,decisions_passed=not decision_errors,
                color_errors=color_errors,decision_errors=decision_errors,errors=errors,samples=report,
                independent_states=sorted(independent_scenes),
                scope='Verdes por cuadro o contexto real disponible; no valida rampa, maniobras ni recepcion Teensy. Imagenes diferentes no garantizan corridas independientes.')


def save_calibration(detector,samples,folder,save_profile=True,guards=None):
    lower,upper=fit_for_detector(samples,detector)
    checked=samples+list(guards or [])
    report=validate(detector,checked,lower,upper)
    profile=dict(version=VERSION,hashes=detector.hashes,lower=lower,upper=upper,
                 shadow_l_min=detector.shadow_floor,
                 minimum_unchanged=detector.minimum,samples=checked,validation=report,
                 enabled_for_control=False,draft=True,
                 camera_environment={k:os.getenv(k,'') for k in ['CAMARA_WB','CAMARA_EXPO','DOBLE_SIN_FACTOR']})
    folder.mkdir(exist_ok=True,parents=True)
    (folder/'validacion.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (folder/'borrador_verdes.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    summary=['COLOR: '+('OK' if report['color_passed'] else 'PENDIENTE'),
             'DECISIONES: '+('OK' if report['decisions_passed'] else 'PENDIENTES'),
             'Area minima y tiempos sin cambiar. Un borrador no se instala.']+report['errors']
    (folder/'validacion.txt').write_text('\n'.join(summary),encoding='utf-8')
    if save_profile or not report['passed']:
        invalidate_profile(folder)
        if save_profile and report['passed']:
            profile.update(enabled_for_control=True,draft=False)
            (folder/'perfil_verdes.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    return lower,upper,report


def export_samples(samples,folder):
    target=folder/('muestras_portables_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip')
    portable=[]
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        stored_context={}
        def store_context(image):
            key=frame_key(image)
            if key not in stored_context:
                name='contexto/c_%05d.png'%len(stored_context)
                ok,encoded=cv2.imencode('.png',image)
                if not ok:raise ValueError('No se pudo exportar contexto')
                archive.writestr(name,encoded.tobytes())
                stored_context[key]=name
            return stored_context[key]
        for index,item in enumerate(samples):
            copy=json.loads(json.dumps(item));relative='imagenes/muestra_%04d.png'%index
            archive.write(item['image'],relative);copy['image']=relative
            if 'source' in copy:copy['original_source']=copy.pop('source')
            if copy['kind']=='scene':
                context=scene_frames(item)
                if context:
                    copy['context']=[]
                    for frame_index,(image,timestamp) in enumerate(context):
                        name=store_context(image)
                        copy['context'].append(dict(image=name,t=timestamp))
                if item.get('assessment')=='entry':
                    future=scene_future(item);copy['future']=[]
                    for frame_index,(image,timestamp) in enumerate(future):
                        name=store_context(image)
                        copy['future'].append(dict(image=name,t=timestamp))
            portable.append(copy)
        archive.writestr('muestras.json',json.dumps(portable,indent=2))
        archive.writestr('LEEME.txt','Descomprimir y abrir el calibrador con --out esta carpeta. Contiene muestras, no una instalacion. Elegir el main real con --main. No incluye ni modifica programas del robot.')
    return target


def replace_node(source, node, replacement):
    lines = source.splitlines(keepends=True)
    start = sum(len(s) for s in lines[:node.lineno-1]) + node.col_offset
    end = sum(len(s) for s in lines[:node.end_lineno-1]) + node.end_col_offset
    return source[:start] + replacement + source[end:]


def apply_profile(detector, path):
    profile = json.loads(path.read_text(encoding='utf-8'))
    if profile.get('draft') or profile.get('enabled_for_control') is False:
        raise ValueError('Es un borrador para revisar, no un perfil aprobado para instalar')
    if profile['version'] != VERSION or profile['hashes'] != detector.hashes:
        raise ValueError('Los programas cambiaron desde la calibracion; repetir con la version actual')
    current_environment = {k:os.getenv(k,'') for k in ['CAMARA_WB','CAMARA_EXPO','DOBLE_SIN_FACTOR']}
    if profile['camera_environment'] != current_environment:
        raise ValueError('Usar el mismo entorno de camara y DOBLE_SIN_FACTOR que al calibrar')
    detector.shadow_floor=int(profile.get('shadow_l_min',detector.base_shadow_floor))
    validation = validate(detector, profile['samples'], profile['lower'], profile['upper'])
    if not validation['passed']:
        raise ValueError('Perfil rechazado: ' + '; '.join(validation['errors']))
    main = read_source(detector.main)
    for name, values in [('lower_green',profile['lower']), ('upper_green',profile['upper'])]:
        node = assignment(ast.parse(main), name).value
        main = replace_node(main, node, 'np.array(%r)' % values)
    double_path = detector.paths['doble_dato.py']
    double = read_source(double_path)
    lo, hi = detector.ranges(profile['lower'],profile['upper'])[3]
    calls = [n for n in ast.walk(ast.parse(double)) if isinstance(n,ast.Call)
             and ast.unparse(n.func) == 'cv2.inRange']
    if len(calls) != 1:
        raise ValueError('No se reconoce el doble: no se modifica nada')
    # Reemplazar desde el final para preservar las posiciones AST.
    for node, value in reversed(list(zip(calls[0].args[1:3], [lo,hi]))):
        double = replace_node(double, node, 'np.array(%r)' % value.tolist())
    # El refuerzo opcional usa los mismos colores que la comprobacion previa.
    for name,value in [('_PAIR_LOWER',lo),('_PAIR_UPPER',hi)]:
        tree=ast.parse(double)
        if any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets) for n in tree.body):
            double=replace_node(double,assignment(tree,name).value,'np.array(%r)'%value.tolist())
    dark_path=detector.paths['verde_oscuro.py']
    dark=read_source(dark_path)
    functions=[n for n in ast.parse(dark).body if isinstance(n,ast.FunctionDef) and n.name=='detectar_verde_sombra']
    if len(functions)!=1:raise ValueError('No se reconoce la funcion sombra')
    dark=replace_node(dark,shadow_floor_node(functions[0]),str(detector.shadow_floor))
    compile(main, str(detector.main), 'exec')
    compile(double, str(double_path), 'exec')
    compile(dark,str(dark_path),'exec')
    backup = detector.root / ('respaldo_verdes_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    for name, target in detector.paths.items():
        if digest(target) != detector.hashes[name]:
            raise ValueError('Archivo cambio mientras se preparaba: ' + name)
        shutil.copy2(target, backup / name)
    shutil.copy2(path, backup / 'perfil.json')
    changes = [(path,source) for path,source in [(detector.main, main), (double_path, double), (dark_path,dark)]
               if read_source(path)!=source]
    try:
        for target, source in changes:
            temp = target.with_name(target.name + '.calibrando')
            newline='\r\n' if b'\r\n' in target.read_bytes() else '\n'
            temp.write_text(source, encoding='utf-8',newline=newline)
            os.replace(temp, target)
    except Exception:
        for name, target in detector.paths.items():
            shutil.copy2(backup / name, target)
        raise
    print('Rangos instalados. Respaldo:', backup)
    print('Se usaran en el proximo arranque; no se inicio el robot.')


def camera_controls(device):
    """Aplicar solo los ajustes ya elegidos para main, nunca inventar otros."""
    settings = []
    if os.getenv('CAMARA_EXPO'):
        settings += ['auto_exposure=1', 'exposure_time_absolute='+str(int(os.environ['CAMARA_EXPO']))]
    if os.getenv('CAMARA_WB'):
        settings += ['white_balance_automatic=0', 'white_balance_temperature='+str(int(os.environ['CAMARA_WB']))]
    for setting in settings:
        subprocess.run(['v4l2-ctl','-d','/dev/video'+str(device),'-c',setting], check=True)
    if settings:
        time.sleep(.5)


def invalidate_profile(folder):
    """Una etiqueta nueva debe impedir instalar por accidente el perfil anterior."""
    path = folder/'perfil_verdes.json'
    if path.exists():
        path.rename(folder/('perfil_anterior_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json'))


def frame_key(frame):
    if frame is None:raise ValueError('No se pudo leer una imagen de las muestras')
    return hashlib.sha256(frame.tobytes()).hexdigest()


def saved_outline(item):
    if 'polygon' in item:return np.array(item['polygon'],np.int32)
    x,y,w,h=item['roi']
    return np.array([[x,y],[x+w-1,y],[x+w-1,y+h-1],[x,y+h-1]],np.int32)


def pick_saved_sample(samples, key, point, tolerance=3):
    hits=[]
    for index,item in enumerate(samples):
        if item.get('frame_key')!=key or 'roi' not in item:continue
        distance=abs(cv2.pointPolygonTest(saved_outline(item),tuple(map(float,point)),True))
        if distance<=tolerance:hits.append((distance,-index,index))
    return min(hits)[2] if hits else None


class ExpressUI:
    """Seleccion y botones separados de la camara y del detector."""
    def __init__(self):
        self.start = None
        self.roi = None
        self.mode = 'rectangle'
        self.points = []
        self.polygon = None
        self.notice = ''
        self.delete_mode = False
        self.delete_click = None
        self.test_mode='frame'
        self.actions = []
        self.freeze_requested = False
        self.can_navigate = False
        self.can_pause = False
        self.buttons = []
        rows = [
            [('Anterior (A)','a'), ('Siguiente (D)','d'), ('Pausa / vivo (P)','p'),
             ('Guardar verde (G)','g'), ('Guardar negativo (N)','n'), ('Ajustar color (C)','c')],
            [('Prueba descarte (0)','0'), ('Prueba izquierda (1)','1'), ('Prueba derecha (2)','2'),
             ('Prueba doble (3)','3'), ('Guardar perfil (S)','s'), ('Deshacer (Z)','z')],
            [('Modo 4 puntos (V)','v'), ('Quitar punto (B)','b'), ('Limpiar seleccion (R)','r'),
             ('Eliminar figura (E)','e'), ('Comprobar (T)','t'), ('Exportar muestras (X)','x')],
        ]
        for row, entries in enumerate(rows):
            for col, (label, action) in enumerate(entries):
                self.buttons.append((10+col*212, 488+row*40, 202, 32, label, action))
        self.buttons.append((432,5,202,28,'Prueba: foto / entrada (F)','f'))

    def enabled(self, action):
        return (self.can_navigate if action in ('a','d') else
                self.can_pause if action == 'p' else True)

    def reset_selection(self):
        self.start = None
        self.roi = None
        self.points = []
        self.polygon = None

    def remove_point(self):
        if self.points:self.points.pop()
        self.polygon=None
        self.roi=None
        self.notice='Punto quitado: %d/4. Elige la esquina que falta.'%len(self.points)

    def add_point(self,x,y):
        if len(self.points)==4:self.reset_selection()
        point=[x,y]
        if point in self.points:
            self.notice='Ese punto ya esta marcado: elige otra esquina.'
            return
        if len(self.points)==3:
            try:self.polygon=quadrilateral(self.points+[point])
            except ValueError:
                self.notice='Cuarto punto dentro del triangulo o alineado: elige otra esquina. B quita un punto.'
                return
        self.points.append(point)
        if self.polygon:
            self.roi=list(cv2.boundingRect(np.array(self.polygon,np.int32)))
            self.notice='Cuadrilatero listo: guarda con G o N. Se mide solo su interior.'
        else:self.notice='Esquinas %d/4: marca las que faltan dentro del material.'%len(self.points)

    def mouse(self, event, x, y, flags=0, param=None):
        if event==cv2.EVENT_RBUTTONDOWN and 0<=x<640 and 0<=y<480 and self.mode=='points':
            self.remove_point()
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            for bx,by,bw,bh,label,action in self.buttons:
                if bx <= x < bx+bw and by <= y < by+bh:
                    if self.enabled(action):self.actions.append(action)
                    return
            if not (0 <= x < 640 and 0 <= y < 480):return
            if self.delete_mode:
                self.delete_click=(x//4,y//4)
                return
            self.freeze_requested = True
            if self.mode=='points':
                self.add_point(x//4,y//4)
                return
            self.start = (x//4,y//4)
            self.roi = [x//4,y//4,1,1]
        elif self.start is not None and event in (cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP):
            # Mantener la seleccion dentro de la imagen aunque el mouse salga.
            px,py = int(np.clip(x//4,0,159)), int(np.clip(y//4,0,119))
            x0,y0 = self.start
            self.roi = [min(px,x0),min(py,y0),abs(px-x0)+1,abs(py-y0)+1]
            if event == cv2.EVENT_LBUTTONUP:self.start = None


class VideoFrames:
    """Video limpio, ya orientado salvo --video-rotate; nunca interpreta un panel como camara."""
    def __init__(self, path, rotate=False):
        self.capture=cv2.VideoCapture(str(path))
        self.rotate=rotate
        self.index=0
        if not self.capture.isOpened():
            self.capture.release()
            raise ValueError('No se pudo abrir el video')
        self.total=int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps=float(self.capture.get(cv2.CAP_PROP_FPS))
        if not 1 <= self.fps <= 240:self.fps=20.
        width=self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        height=self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if height < 120 or width < 160 or abs(width/height-4/3) > .02:
            self.capture.release()
            raise ValueError('Video no crudo 4:3: posiblemente tiene panel de mascaras. Usar --recording con los PNG originales.')

    def read(self, index):
        index=max(0,min(max(0,self.total-1),index))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,image=self.capture.read()
        if not ok:raise ValueError('No se pudo leer el cuadro de video %d'%index)
        self.index=index
        if self.rotate:image=cv2.rotate(image,cv2.ROTATE_180)
        return cv2.resize(image,(160,120),interpolation=cv2.INTER_NEAREST)

    def release(self):self.capture.release()


def render_panel(frame, masks, ui, samples, status, details):
    left = cv2.resize(frame,(640,480),interpolation=cv2.INTER_NEAREST)
    key = frame_key(frame)
    for item in samples:
        if item.get('frame_key') == key and 'roi' in item:
            x,y,w,h = item['roi']
            color = (70,230,70) if item['kind']=='green' else (255,180,40)
            if 'polygon' in item:cv2.polylines(left,[np.array(item['polygon'],np.int32)*4],True,color,2)
            else:cv2.rectangle(left,(x*4,y*4),((x+w)*4-1,(y+h)*4-1),color,2)
            cv2.putText(left,'G OK' if item['kind']=='green' else 'N OK',
                        (max(0,x*4),max(14,y*4-3)),cv2.FONT_HERSHEY_SIMPLEX,.43,color,1)
    cv2.line(left,(0,320),(639,320),(0,255,255),1)
    if ui.mode=='points':
        if ui.polygon:cv2.polylines(left,[np.array(ui.polygon,np.int32)*4],True,(0,0,255),2)
        elif len(ui.points)>1:cv2.polylines(left,[np.array(ui.points,np.int32)*4],False,(0,0,255),1)
        for i,(x,y) in enumerate(ui.points):
            cv2.circle(left,(x*4,y*4),4,(0,0,255),-1)
            cv2.putText(left,str(i+1),(x*4+6,y*4-4),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,255),1)
    elif ui.roi:
        x,y,w,h=ui.roi
        cv2.rectangle(left,(x*4,y*4),((x+w)*4-1,(y+h)*4-1),(0,0,255),2)
    tiles=[]
    for name,mask in zip(['Principal','Oscuro','Sombra','Doble (color)'],masks):
        tile=cv2.cvtColor(cv2.resize(mask,(320,240),interpolation=cv2.INTER_NEAREST),cv2.COLOR_GRAY2BGR)
        cv2.putText(tile,name,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
        tiles.append(tile)
    right=np.vstack([np.hstack(tiles[:2]),np.hstack(tiles[2:])])
    panel=np.vstack([np.hstack([left,right]),np.full((230,1280,3),24,np.uint8)])
    for x,y,w,h,label,action in ui.buttons:
        enabled=ui.enabled(action)
        if action=='v':label='Modo: '+('4 puntos' if ui.mode=='points' else 'rectangulo')+' (V)'
        if action=='e' and ui.delete_mode:label='BORRAR: toca contorno'
        if action=='f':label='Prueba: '+('entrada' if ui.test_mode=='entry' else 'foto')+' (F)'
        cv2.rectangle(panel,(x,y),(x+w,y+h),(65,75,85) if enabled else (35,35,35),-1)
        if action=='e' and ui.delete_mode:cv2.rectangle(panel,(x,y),(x+w,y+h),(0,120,255),2)
        cv2.putText(panel,label,(x+7,y+21),cv2.FONT_HERSHEY_SIMPLEX,.46,
                    (245,245,245) if enabled else (110,110,110),1)
    for i,text in enumerate([status[:150]]+details):
        cv2.putText(panel,text,(10,622+i*24),cv2.FONT_HERSHEY_SIMPLEX,.46,(230,230,230),1)
    return panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, default=Path('/home/iita/Desktop/main.py'))
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--selection',choices=['points','rectangle'],default='points',help='4 esquinas o rectangulo por arrastre')
    images = parser.add_mutually_exclusive_group()
    images.add_argument('--image', type=Path, help='PNG crudo ya orientado; no vuelve a rotarlo')
    images.add_argument('--images', type=Path, help='Carpeta de PNG crudos; A anterior, D siguiente')
    images.add_argument('--recording', type=Path, help='Carpeta crudo_* de una corrida; busca todos sus f_*.png')
    images.add_argument('--video', type=Path, help='Video limpio 4:3, sin overlay ni panel de mascaras')
    parser.add_argument('--video-start',type=float,default=0,help='Segundo inicial del video')
    parser.add_argument('--video-step',type=int,default=1,help='Cuadros por pulsacion A/D en video')
    parser.add_argument('--video-rotate',action='store_true',help='Rotar 180 grados un video sin orientar')
    parser.add_argument('--out', type=Path, default=Path('calibracion_verdes_express'))
    parser.add_argument('--apply', type=Path)
    parser.add_argument('--check', type=Path, help='Validar perfil sin camara ni modificar archivos')
    parser.add_argument('--assess',action='store_true',help='Revisar muestras de --out y guardar borrador/informe sin abrir ventanas')
    parser.add_argument('--guards',type=Path,default=Path(__file__).resolve().parent/'protecciones/muestras.json',
                        help='Escenas correctas protegidas: deben conservar su decision')
    args = parser.parse_args()
    detector = Detector(args.main)
    guards=load_samples(args.guards) if args.guards.exists() else []
    if args.apply:
        apply_profile(detector, args.apply)
        return
    if args.check:
        p = json.loads(args.check.read_text(encoding='utf-8'))
        detector.shadow_floor=int(p.get('shadow_l_min',detector.base_shadow_floor))
        result = validate(detector,p['samples'],p['lower'],p['upper'])
        print(json.dumps(result,indent=2))
        raise SystemExit(0 if result['passed'] else 1)
    if args.assess:
        samples=load_samples(args.out/'muestras.json')
        lower,upper,report=save_calibration(detector,samples,args.out,False,guards)
        print(json.dumps(dict(lower=lower,upper=upper,color_passed=report['color_passed'],
                             decisions_passed=report['decisions_passed'],errors=report['errors']),indent=2))
        raise SystemExit(0 if report['passed'] else 1)
    args.out = args.out.resolve()
    args.out.mkdir(exist_ok=True,parents=True)
    manifest = args.out/'muestras.json'
    samples = load_samples(manifest) if manifest.exists() else []
    unique=remove_identical_duplicates(samples)
    if len(unique)!=len(samples):
        backup=manifest.with_name('muestras_antes_deduplicar_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
        shutil.copy2(manifest,backup)
        samples=unique
        manifest.write_text(json.dumps(samples,indent=2),encoding='utf-8')
    # Recuperar tambien los rectangulos de muestras guardadas con la version anterior.
    for item in samples:
        if 'frame_key' not in item:
            stored=cv2.imread(item['image'])
            if stored is not None:item['frame_key']=frame_key(stored)
    lower, upper = detector.lower, detector.upper
    capture = None
    video = None
    frame = None
    image_paths = (sorted(args.recording.rglob('f_*.png')) if args.recording else
                   sorted(args.images.glob('*.png')) if args.images else ([args.image] if args.image else []))
    if (args.images or args.recording) and not image_paths:
        raise ValueError('La carpeta no contiene imagenes PNG')
    image_index = 0
    paused = bool(image_paths or args.video)
    ui = ExpressUI()
    ui.mode=args.selection
    ui.can_navigate = bool(image_paths or args.video)
    ui.can_pause = not bool(image_paths)
    window = 'Verdes express: A anterior - D siguiente | camara / imagenes'
    status = 'Marca 4 esquinas dentro del verde; G guarda. V cambia entre puntos y rectangulo.'
    if sum(s['kind']=='green' for s in samples) >= 3:
        lower,upper=fit_for_detector(samples,detector)
        status='Muestras y rango de practica recuperados. No se ha instalado ningun cambio.'
    def mouse(event,x,y,flags,param):
        nonlocal paused,status
        ui.mouse(event,x,y,flags,param)
        if ui.freeze_requested:
            ui.freeze_requested=False
            if not paused:
                paused=True
                status='Imagen congelada al dibujar. Guarda con G/N; P reanuda la camara o video.'
        if ui.notice:
            status=ui.notice
            ui.notice=''
    try:
        if image_paths:
            frame = cv2.imread(str(image_paths[image_index]))
            if frame is None or frame.shape[:2] != (120,160):
                raise ValueError('Usar PNG crudo orientado 160x120')
        elif args.video:
            if args.video_step<1:raise ValueError('--video-step debe ser positivo')
            video=VideoFrames(args.video,args.video_rotate)
            frame=video.read(int(max(0,args.video_start)*video.fps))
            status='Video: P reproduce/pausa; A/D avanza cuadros. Usar solamente imagen limpia sin textos.'
        else:
            capture = cv2.VideoCapture(args.camera)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH,160)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT,120)
            if not capture.isOpened():
                raise ValueError('Camara ocupada o no disponible: detener main antes')
            camera_controls(args.camera)
            for _ in range(12):
                capture.read()
        cv2.namedWindow(window)
        cv2.setMouseCallback(window,mouse)
        print('Principal actual:', detector.lower, detector.upper, 'area:',detector.minimum)
        print('No abre serial ni envia comandos. Detener el servicio y usar robot inmovil.')
        last_eval = 0; gs = 0
        while True:
            if not paused:
                if video:
                    if video.index+1>=video.total:
                        paused=True
                        status='Fin del video. A retrocede; las muestras estan conservadas.'
                    else:frame=video.read(video.index+1)
                else:
                    ok, raw = capture.read()
                    if not ok:
                        raise ValueError('Se perdio la camara')
                    frame = cv2.resize(cv2.rotate(raw,cv2.ROTATE_180),(160,120),interpolation=cv2.INTER_NEAREST)
            if time.monotonic()-last_eval > .2:
                gs = detector.evaluate(frame,lower,upper)
                last_eval = time.monotonic()
            masks = detector.masks(frame,lower,upper)
            green_count=sum(s['kind']=='green' for s in samples)
            neg_count=sum(s['kind']=='negative' for s in samples)
            position = (' | imagen %d/%d %s' % (image_index+1,len(image_paths),image_paths[image_index].name)) if image_paths else ''
            if video:position=' | video %.2fs cuadro %d/%d'%(video.index/video.fps,video.index+1,video.total)
            details=['GS visual=%d (sin maniobra/confirmacion temporal) | verdes=%d negativos=%d pruebas=%d | %s' %
                   (gs,green_count,neg_count,sum(s['kind']=='scene' for s in samples),'PAUSA' if paused else 'VIVO'),
                   'LAB %s .. %s | sombra L=%d | area=%d SIN CAMBIAR' % (lower,upper,detector.shadow_floor,detector.minimum)+position,
                   'Rojo=seleccion | Verde=muestra guardada | Azul=negativo guardado | Q salir | No controla motores']
            panel=render_panel(frame,masks,ui,samples,status,details)
            cv2.imshow(window,panel)
            key=cv2.waitKey(max(1,round(1000/video.fps)) if video and not paused else 30)&0xff
            if 65 <= key <= 90:key+=32
            if ui.actions:
                key=ord(ui.actions.pop(0))
            if ui.delete_click is not None:
                index=pick_saved_sample(samples,frame_key(frame),ui.delete_click)
                ui.delete_click=None
                if index is None:
                    status='No hay un borde guardado ahi. Toca el contorno verde/azul; E cancela.'
                else:
                    backup=manifest.with_name('muestras_antes_borrar_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
                    if manifest.exists():shutil.copy2(manifest,backup)
                    removed=samples.pop(index)
                    invalidate_profile(args.out)
                    manifest.write_text(json.dumps(samples,indent=2),encoding='utf-8')
                    if sum(s['kind']=='green' for s in samples)>=3:lower,upper=fit_for_detector(samples,detector)
                    else:lower,upper=detector.lower,detector.upper
                    last_eval=0
                    ui.delete_mode=False
                    status='Figura eliminada: '+removed['kind']+'. Resto de muestras y pruebas conservadas; rango recalculado.'
            if key in (27,ord('q')):break
            if key in (ord(' '),ord('p')) and (capture is not None or video is not None):
                paused=not paused
                ui.reset_selection()
                last_eval=0
                status='Video/camara en marcha: dibuja para congelar.' if not paused else 'Imagen congelada: selecciona un material.'
            try:
                if key==ord('f'):
                    ui.test_mode='entry' if ui.test_mode=='frame' else 'frame'
                    status=('PRUEBA ENTRADA: 0/1/2/3 comprueban el PRIMER dato de la secuencia real.' if ui.test_mode=='entry' else
                            'PRUEBA FOTO: 0/1/2/3 comprueban solamente este cuadro.')
                elif key==ord('e'):
                    ui.delete_mode=not ui.delete_mode
                    ui.reset_selection()
                    if ui.delete_mode:
                        paused=True
                        status='Toca el BORDE de la figura guardada que quieres eliminar. E cancela. Se guarda respaldo.'
                    else:status='Borrado cancelado. Las muestras siguen intactas.'
                elif key==ord('v'):
                    ui.delete_mode=False
                    ui.mode='rectangle' if ui.mode=='points' else 'points'
                    ui.reset_selection()
                    status='Marca 4 esquinas interiores con clics.' if ui.mode=='points' else 'Arrastra un rectangulo dentro del material.'
                elif key==ord('b'):
                    ui.remove_point()
                    status=ui.notice;ui.notice=''
                elif key==ord('r'):
                    ui.reset_selection()
                    status='Seleccion limpia. Las muestras guardadas siguen intactas.'
                elif key in (ord('a'),ord('d'),ord('['),ord(']')) and video:
                    direction=1 if key in (ord('d'),ord(']')) else -1
                    frame=video.read(video.index+direction*args.video_step)
                    paused=True
                    ui.reset_selection()
                    last_eval=0
                    status='Cuadro de video congelado: seleccionar muestras o guardar una prueba'
                elif key in (ord('a'),ord('d'),ord('['),ord(']')) and image_paths:
                    image_index = (image_index + (1 if key in (ord('d'),ord(']')) else -1)) % len(image_paths)
                    frame = cv2.imread(str(image_paths[image_index]))
                    if frame is None or frame.shape[:2] != (120,160):
                        raise ValueError('Usar PNG crudos orientados de 160x120')
                    ui.reset_selection()
                    ui.delete_mode=False
                    last_eval = 0
                    status = 'Imagen cruda: seleccionar muestras o etiquetar una prueba'
                elif key in (ord('g'),ord('n')) or key in map(ord,'0123'):
                    scene=key in map(ord,'0123')
                    if not paused:
                        raise ValueError('Primero ESPACIO para congelar la imagen y seleccionar')
                    if not scene and not ui.roi:
                        raise ValueError('Primero completa 4 esquinas interiores' if ui.mode=='points' else 'Primero arrastra un rectangulo DENTRO del material')
                    if not scene and ui.start is not None:
                        raise ValueError('Primero suelta el mouse para terminar el rectangulo')
                    if not scene:
                        region=dict(roi=ui.roi.copy())
                        if ui.mode=='points':region['polygon']=ui.polygon
                        sample_pixels(frame,region)
                    name=datetime.datetime.now().strftime('muestra_%Y%m%d_%H%M%S_%f.png')
                    target=args.out/name
                    item=dict(image=str(target),kind='scene' if scene else 'green' if key==ord('g') else 'negative',frame_key=frame_key(frame))
                    if video:item['source']=dict(video=str(args.video.resolve()),frame=video.index,seconds=video.index/video.fps,rotate=args.video_rotate)
                    elif image_paths:item['source']=dict(image=str(image_paths[image_index].resolve()))
                    if scene:
                        item['expected']=int(chr(key))
                        item['assessment']=ui.test_mode
                    else:item.update(region)
                    if any(sample_signature(old)==sample_signature(item) for old in samples):
                        status='Esa misma muestra/prueba ya esta guardada. No se duplica al mantener una tecla.'
                        continue
                    if not cv2.imwrite(str(target),frame):raise ValueError('No se pudo guardar imagen')
                    # Cambiar explícitamente FOTO/ENTRADA y pulsar la misma
                    # etiqueta reemplaza esa prueba, sin alterar su clase.
                    if scene:
                        previous=[old for old in samples if old['kind']=='scene' and old.get('frame_key')==item['frame_key']
                                  and old.get('expected')==item['expected'] and old.get('assessment','frame')!=ui.test_mode]
                        if previous:
                            # Una copia suelta de PNG no debe hacer perder
                            # la procedencia real ya comprobada de esa foto.
                            origin=next((old for old in previous if old.get('source') or old.get('context')),None)
                            if origin:
                                for field in ('source','context','future'):
                                    if origin.get(field):item[field]=origin[field]
                            if manifest.exists():shutil.copy2(manifest,manifest.with_name('muestras_antes_cambiar_tipo_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json'))
                            samples=[old for old in samples if old not in previous]
                    samples.append(item)
                    invalidate_profile(args.out)
                    manifest.write_text(json.dumps(samples,indent=2),encoding='utf-8')
                    status=('VERDE GUARDADO OK' if item['kind']=='green' else 'NEGATIVO GUARDADO OK' if item['kind']=='negative'
                            else 'PRUEBA '+('ENTRADA' if ui.test_mode=='entry' else 'FOTO')+' GUARDADA: GS esperado='+str(item['expected']))
                    if not scene:ui.reset_selection()
                elif key==ord('z') and samples:
                    samples.pop()
                    invalidate_profile(args.out)
                    manifest.write_text(json.dumps(samples,indent=2),encoding='utf-8')
                    if sum(s['kind']=='green' for s in samples)>=3:lower,upper=fit_for_detector(samples,detector)
                    else:lower,upper=detector.lower,detector.upper
                    last_eval=0
                    status='Ultima etiqueta eliminada; rango recalculado'
                elif key==ord('c'):
                    lower,upper=fit_for_detector(samples,detector)
                    last_eval=0
                    status='Rango ajustado. Revisar negativos y guardar pruebas NUEVAS con 0/1/2/3'
                    print('Rango propuesto:',lower,upper)
                elif key in (ord('s'),ord('t')):
                    lower,upper,report=save_calibration(detector,samples,args.out,key==ord('s'),guards)
                    last_eval=0
                    status=('COLOR '+('OK' if report['color_passed'] else 'PENDIENTE')+
                            ' | DECISIONES '+('OK' if report['decisions_passed'] else 'PENDIENTES'))
                    status+=(' | Perfil guardado, NO instalado.' if key==ord('s') and report['passed'] else
                             ' | Borrador guardado; detalles en validacion.txt.')
                    print(status)
                    print('\n'.join(report['errors']))
                elif key==ord('x'):
                    target=export_samples(samples,args.out)
                    status='Muestras exportadas para otra computadora/Raspberry: '+target.name
                    print(status,target)
            except (ValueError,KeyError) as exc:
                status=str(exc)
                print(status)
    finally:
        if capture is not None:capture.release()
        if video is not None:video.release()
        cv2.destroyAllWindows()


if __name__=='__main__':
    main()
