"""Calibracion auxiliar desde regiones etiquetadas. No abre camara ni motores.

Manifest: [{image, label: silver|negative, roi:[x,y,w,h], split: fit|test}].
Los cuadros son BGR de OpenCV; el perfil usa LAB OpenCV de 8 bits, NO los
rangos numericos LAB de OpenMV. Cambiar el perfil no cambia el seguidor.
"""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np


def fit(samples):
    patches = []
    for sample in samples:
        if sample['split'] == 'fit' and sample['label'] == 'silver':
            im = cv2.imread(sample['image'])
            if im is None:
                raise ValueError(sample['image'])
            x, y, w, h = sample['roi']
            if min(x, y) < 0 or min(w, h) < 1 or x+w > im.shape[1] or y+h > im.shape[0]:
                raise ValueError('ROI fuera de imagen')
            patches.append(cv2.cvtColor(im, cv2.COLOR_BGR2LAB)[y:y+h, x:x+w].reshape(-1, 3))
    if len(patches) < 2:
        raise ValueError('Usar al menos dos muestras de plateado para ajustar')
    pixels = np.concatenate(patches)
    return dict(version='SILVER-LAB-CALIBRATION-1', enabled_for_control=False,
                color_space='OpenCV LAB uint8',
                lower=np.floor(np.percentile(pixels, 2, axis=0)-5).clip(0,255).astype(int).tolist(),
                upper=np.ceil(np.percentile(pixels, 98, axis=0)+5).clip(0,255).astype(int).tolist(),
                fit_pixels=len(pixels), scope='Solo mascara auxiliar; no identifica material por si sola')


def mask(image, profile):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    return cv2.inRange(lab, np.array(profile['lower'],np.uint8), np.array(profile['upper'],np.uint8))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    samples=json.loads(args.manifest.read_text(encoding='utf-8'))
    profile=fit(samples)
    args.out.mkdir(exist_ok=True,parents=True)
    results=[]
    for i,sample in enumerate(samples):
        im=cv2.imread(sample['image'])
        if im is None:raise ValueError(sample['image'])
        x,y,w,h=sample['roi']
        for gain in [0.6,0.8,1.,1.2,1.4]:
            changed=(im.astype(float)*gain).clip(0,255).astype(np.uint8)
            m=mask(changed,profile)
            results.append(dict(sample=i,label=sample['label'],split=sample['split'],
                                synthetic_gain=gain,accepted_fraction=float(np.mean(m[y:y+h,x:x+w]>0))))
        m=mask(im,profile)
        vis=im.copy();cv2.rectangle(vis,(x,y),(x+w-1,y+h-1),(0,0,255),1)
        cv2.imwrite(str(args.out/f'muestra_{i:02d}.png'),np.hstack([cv2.resize(vis,(480,360)),cv2.resize(cv2.cvtColor(m,cv2.COLOR_GRAY2BGR),(480,360))]))
    profile['manifest']=str(args.manifest.resolve())
    (args.out/'perfil.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    (args.out/'validacion.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(profile,indent=2))
    for r in results:
        if r['split']=='test':print(r)


if __name__=='__main__':main()
