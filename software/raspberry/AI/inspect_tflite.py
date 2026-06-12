# -*- coding: utf-8 -*-
"""
Inspector de modelos TFLite para verificar parametros.
Uso:
    python inspect_tflite.py [ruta1.tflite] [ruta2.tflite] ...
Si no se pasan rutas, inspecciona todos los .tflite del directorio actual y subdirs.
"""
import sys
import os
import hashlib
from pathlib import Path

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter


def sha256_short(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def inspect(path):
    p = Path(path)
    print("\n" + "=" * 70)
    print(f"  ARCHIVO: {p}")
    print("=" * 70)
    if not p.exists():
        print("  [ERROR] no existe")
        return
    print(f"  Tamano:  {p.stat().st_size:,} bytes ({p.stat().st_size/1024/1024:.2f} MB)")
    print(f"  SHA256:  {sha256_short(p)}...  (huella unica)")

    try:
        interp = Interpreter(model_path=str(p))
        interp.allocate_tensors()
    except Exception as e:
        print(f"  [ERROR] no se pudo cargar: {e}")
        return

    inp = interp.get_input_details()
    out = interp.get_output_details()

    print(f"\n  --- INPUTS ({len(inp)}) ---")
    for i, t in enumerate(inp):
        print(f"  [{i}] name='{t['name']}'  shape={list(t['shape'])}  dtype={t['dtype'].__name__}")
        if t.get('quantization', (0.0, 0))[1] != 0 or t.get('quantization', (0.0, 0))[0] != 0.0:
            print(f"      quantization scale={t['quantization'][0]:.6f} zero_point={t['quantization'][1]}")

    print(f"\n  --- OUTPUTS ({len(out)}) ---")
    for i, t in enumerate(out):
        print(f"  [{i}] name='{t['name']}'  shape={list(t['shape'])}  dtype={t['dtype'].__name__}")

    # Numero total de tensores y operaciones
    try:
        # Tensores
        n_tensors = 0
        for i in range(10000):
            try:
                interp.get_tensor_details()
                break
            except Exception:
                pass
        details = interp.get_tensor_details()
        n_tensors = len(details)
        print(f"\n  --- ESTRUCTURA ---")
        print(f"  Total de tensores:  {n_tensors}")
    except Exception:
        pass

    # Inferencia muestra: si la entrada es una imagen estandar, te decimos el tamano
    try:
        if len(inp) == 1 and len(inp[0]['shape']) == 4:
            _, h, w, c = inp[0]['shape']
            print(f"  Imagen esperada:    {h}x{w} px, {c} canal(es)")
    except Exception:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        # Auto-detectar: usa el directorio del script
        here = Path(__file__).parent
        targets = sorted(str(p) for p in here.rglob("*.tflite"))
        print(f"Inspeccionando {len(targets)} modelo(s) bajo {here}/")

    for t in targets:
        inspect(t)
    print("\n" + "=" * 70)
    print("Listo. Si dos modelos tienen el MISMO SHA256, son el mismo archivo.")
    print("=" * 70)
