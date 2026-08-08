"""Quita el fondo magenta de los sprites, los recorta, los reduce y los
incrusta como data URI dentro de SPRITE_IMAGES en aventura.html."""
import base64, io, os, re, json
from collections import deque
import numpy as np
from PIL import Image

SRC = '/Users/jorgediaz/cardio-quest'
KEYS = ['vanguardia','corsario','oraculo','guardabosques','forjador','trotamundos',
        'lvl1','lvl2','lvl3','lvl4','lvl5','lvl6','lvl7','lvl8','lvl9','lvl10']
OUT = 128  # lienzo final

def is_magenta(a):
    """Máscara de 'magenta-ish': rojo y azul altos, verde bajo."""
    r, g, b = a[...,0].astype(int), a[...,1].astype(int), a[...,2].astype(int)
    return (r > 150) & (b > 150) & (g < 110) & (r - g > 70) & (b - g > 70)

def flood_bg(mask):
    """Relleno por inundación desde el borde: solo el fondo CONECTADO se
    vuelve transparente, así los morados/rosas dentro del sprite se salvan."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h-1):
            if mask[y,x] and not seen[y,x]: seen[y,x]=True; q.append((y,x))
    for y in range(h):
        for x in (0, w-1):
            if mask[y,x] and not seen[y,x]: seen[y,x]=True; q.append((y,x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny, nx = y+dy, x+dx
            if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                seen[ny,nx] = True; q.append((ny,nx))
    return seen

def process(path):
    im = Image.open(path).convert('RGBA')
    a = np.array(im)
    bg = flood_bg(is_magenta(a))
    a[bg] = [0,0,0,0]

    # Desflecado: los píxeles del contorno mezclados con el magenta quedan
    # rosados; se atenúan quitándoles el exceso de rojo/azul y su opacidad.
    rgb = a[...,:3].astype(float)
    fringe = (~bg) & (a[...,3] > 0)
    r, g, b = rgb[...,0], rgb[...,1], rgb[...,2]
    tint = np.minimum(r - g, b - g)
    halo = fringe & (tint > 55) & (g < 120)
    # vecino transparente => es contorno real
    trans = a[...,3] == 0
    nb = np.zeros_like(trans)
    nb[1:,:] |= trans[:-1,:]; nb[:-1,:] |= trans[1:,:]
    nb[:,1:] |= trans[:,:-1]; nb[:,:-1] |= trans[:,1:]
    kill = halo & nb
    a[kill] = [0,0,0,0]

    im = Image.fromarray(a, 'RGBA')
    bbox = im.getbbox()
    if bbox: im = im.crop(bbox)

    # Reducción con alfa premultiplicado para que el borde no se ensucie.
    arr = np.array(im).astype(float)
    al = arr[...,3:4] / 255.0
    arr[...,:3] *= al
    pm = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    w, h = pm.size
    s = min(OUT / w, OUT / h)
    nw, nh = max(1,int(round(w*s))), max(1,int(round(h*s)))
    pm = pm.resize((nw, nh), Image.LANCZOS)
    arr = np.array(pm).astype(float)
    al = arr[...,3:4] / 255.0
    with np.errstate(divide='ignore', invalid='ignore'):
        arr[...,:3] = np.where(al > 0, np.clip(arr[...,:3]/np.maximum(al,1e-6), 0, 255), 0)
    small = Image.fromarray(arr.astype(np.uint8), 'RGBA')

    # Lienzo cuadrado, apoyado abajo: todos los personajes comparten suelo.
    canvas = Image.new('RGBA', (OUT, OUT), (0,0,0,0))
    canvas.paste(small, ((OUT-nw)//2, OUT-nh), small)

    # Paleta reducida + alfa binario => PNG pequeño.
    q = canvas.quantize(colors=64, method=Image.FASTOCTREE, dither=Image.NONE)
    buf = io.BytesIO()
    q.save(buf, format='PNG', optimize=True)
    return buf.getvalue()

data = {}
for k in KEYS:
    p = os.path.join(SRC, k + '.png')
    png = process(p)
    data[k] = 'data:image/png;base64,' + base64.b64encode(png).decode()
    print(f'{k:14s} {len(png)/1024:6.1f} KB')

total = sum(len(v) for v in data.values())
print(f'\ntotal data URIs: {total/1024:.0f} KB')

# Inyectar en aventura.html
p = os.path.join(SRC, 'aventura.html')
src = open(p, encoding='utf-8').read()
block = 'const SPRITE_IMAGES = {\n' + ''.join(
    f"  {k}: {json.dumps(data[k])},\n" for k in KEYS) + '};'
new = re.sub(r'const SPRITE_IMAGES = \{.*?\n\};', lambda m: block, src, count=1, flags=re.S)
assert new != src, 'no se encontró el bloque SPRITE_IMAGES'
open(p, 'w', encoding='utf-8').write(new)
print('aventura.html actualizado:', len(new)/1024, 'KB')
