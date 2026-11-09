"""Reproduce cuadros consecutivos; compara el doble previo y el candidato.
No interpreta el CSV Pi como telemetría de recepción ni como verdad visual.
"""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import cv2
import numpy as np
from doble_temprano import EarlyDouble


class Raw:
    def step(self,state,lab,black,now):return state


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def run(raw,detector,lower,upper,output):
    white=np.full((120,160,3),255,np.uint8)
    previous=detector.double.DoubleData()
    candidate_base=detector.double.DoubleData()
    for state in (previous,candidate_base):
        detector.evaluate(white,lower,upper,True,state)
        state.reset()
    ranges=detector.ranges(lower,upper)[3]
    candidate=EarlyDouble(candidate_base,*ranges)
    raw_detector=Raw()
    result=[]
    with (raw/'cuadros.csv').open() as stream:
        for row in csv.DictReader(stream):
            n=int(row['n']);time=float(row['t'])
            image=cv2.imread(str(raw/f'f_{n:06d}.png'))
            if image is None:continue
            lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
            black=cv2.inRange(image,np.array(detector.black_lower),np.array(detector.black_upper));black[:60]=0
            accepted=detector.evaluate(image,lower,upper,False,raw_detector)
            old=previous.step(accepted,lab,black,time)
            new=candidate.step(accepted,lab,black,time)
            pair=candidate.last_pair
            result.append(dict(n=n,t=time,recorded=int(row['green_state']),raw=accepted,
                               old=old,candidate=new,pair_hits=candidate.hits,
                               separator=round(pair['separator'],3) if pair else '',
                               above_left=round(pair['above'][0],3) if pair else '',
                               above_right=round(pair['above'][1],3) if pair else ''))
    output.parent.mkdir(exist_ok=True,parents=True)
    with output.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    changes=[r for r in result if r['old']!=r['candidate']]
    groups=[]
    for row in changes:
        if not groups or row['n']-groups[-1][-1]['n']>30:groups.append([])
        groups[-1].append(row)
    report=dict(frames=len(result),changed=len(changes),groups=[dict(start=g[0]['n'],end=g[-1]['n'],
                 frames=len(g),transitions=sorted(set(str(r['old'])+'->'+str(r['candidate']) for r in g))) for g in groups],
                scope='Replay con tiempos CSV y estado temporal de doble; sin simular maniobras, bloqueos main ni Teensy')
    output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return result,report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('raw',type=Path)
    parser.add_argument('--main',type=Path,required=True)
    parser.add_argument('--samples',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    tool=module(Path(__file__).resolve().parent.parent/'calibrador_verdes_express_20261102/calibrador_verdes_express.py','calibration')
    detector=tool.Detector(args.main)
    lower,upper=tool.fit(json.loads(args.samples.read_text()))
    _,report=run(args.raw,detector,lower,upper,args.out)
    print(json.dumps(dict(lower=lower,upper=upper,**report)))
