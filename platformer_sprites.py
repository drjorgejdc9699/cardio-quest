"""Quita el fondo blanco de los assets del minijuego plataformero (Corazón
Bros), los recorta y los reduce, listos para incrustar como data URI.
Mismo enfoque que sprites.py (flood-fill desde el borde + desflecado +
alfa premultiplicado) pero contra blanco en vez de magenta, porque así
llegaron generadas estas imágenes."""
import base64, io, os
from collections import deque
import numpy as np
from PIL import Image

SRC = '/Users/jorgediaz/cardio-quest/assets'
OUT_DIR = '/Users/jorgediaz/cardio-quest/assets/processed'
os.makedirs(OUT_DIR, exist_ok=True)

def is_white(a, tol=8):
    r, g, b = a[...,0].astype(int), a[...,1].astype(int), a[...,2].astype(int)
    return (r > 255-tol) & (g > 255-tol) & (b > 255-tol)

def flood_bg(mask):
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

def cutout(path):
    """Blanco -> transparente (solo el fondo conectado al borde), desflecado,
    recortado a bbox. Devuelve una imagen RGBA sin canvas fijo todavía."""
    im = Image.open(path).convert('RGBA')
    a = np.array(im)
    bg = flood_bg(is_white(a))
    a[bg] = [0,0,0,0]

    rgb = a[...,:3].astype(float)
    fringe = (~bg) & (a[...,3] > 0)
    r, g, b = rgb[...,0], rgb[...,1], rgb[...,2]
    # halo blanco: canales altos y parejos entre sí (a diferencia del contorno
    # oscuro real del arte, que tiene canales bajos o muy distintos entre sí)
    bright = (r+g+b)/3
    evenness = 255 - (np.maximum(np.maximum(r,g),b) - np.minimum(np.minimum(r,g),b))
    halo = fringe & (bright > 200) & (evenness > 200)
    trans = a[...,3] == 0
    nb = np.zeros_like(trans)
    nb[1:,:] |= trans[:-1,:]; nb[:-1,:] |= trans[1:,:]
    nb[:,1:] |= trans[:,:-1]; nb[:,:-1] |= trans[:,1:]
    kill = halo & nb
    a[kill] = [0,0,0,0]

    im = Image.fromarray(a, 'RGBA')
    bbox = im.getbbox()
    if bbox: im = im.crop(bbox)
    return im

def premultiplied_resize(im, target_w, target_h):
    arr = np.array(im).astype(float)
    al = arr[...,3:4] / 255.0
    arr[...,:3] *= al
    pm = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    pm = pm.resize((target_w, target_h), Image.LANCZOS)
    arr = np.array(pm).astype(float)
    al = arr[...,3:4] / 255.0
    with np.errstate(divide='ignore', invalid='ignore'):
        arr[...,:3] = np.where(al > 0, np.clip(arr[...,:3]/np.maximum(al,1e-6), 0, 255), 0)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')

def fit_on_canvas(im, out, group_scale=None):
    """Reduce manteniendo proporción y lo pega centrado/abajo en un lienzo
    cuadrado `out`x`out`. group_scale, si se da, es un factor de escala común
    (no el 'fit to canvas' individual) para que varios frames del mismo
    personaje/enemigo guarden su tamaño relativo real entre sí."""
    w, h = im.size
    s = group_scale if group_scale is not None else min(out/w, out/h)
    nw, nh = max(1,int(round(w*s))), max(1,int(round(h*s)))
    small = premultiplied_resize(im, nw, nh)
    canvas = Image.new('RGBA', (out, out), (0,0,0,0))
    canvas.paste(small, ((out-nw)//2, out-nh), small)
    return canvas

def save(im, name, colors=64):
    q = im.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.NONE).convert('RGBA')
    # requantize dropped alpha nuances to on/off in some Pillow versions; keep RGBA source alpha
    out = im.copy()
    buf = io.BytesIO()
    out.save(buf, format='PNG', optimize=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, 'wb') as f:
        f.write(buf.getvalue())
    print(f'{name:28s} {out.size} {len(buf.getvalue())/1024:6.1f} KB')
    return buf.getvalue()

# ---- personaje: 4 cuadros, mismo lienzo y misma escala relativa ----
CHAR_FRAMES = ['corazon_quieto','corazon_camina1','corazon_camina2','corazon_salto','corazon_golpeado']
OUT_CHAR = 140
cuts = {k: cutout(os.path.join(SRC, k+'.png')) for k in CHAR_FRAMES}
# escala común: el frame más grande de los 5 debe caber en el lienzo
max_dim = max(max(im.size) for im in cuts.values())
scale = OUT_CHAR / max_dim
for k, im in cuts.items():
    canvas = fit_on_canvas(im, OUT_CHAR, group_scale=scale)
    save(canvas, k+'.png')

# ---- enemigo colesterol: 3 cuadros, mismo lienzo y misma escala ----
ENEMY_FRAMES = ['colesterol_1','colesterol_2']
OUT_ENEMY = 140
cuts_e = {k: cutout(os.path.join(SRC, k+'.png')) for k in ENEMY_FRAMES}
max_dim_e = max(max(im.size) for im in cuts_e.values())
scale_e = OUT_ENEMY / max_dim_e
for k, im in cuts_e.items():
    canvas = fit_on_canvas(im, OUT_ENEMY, group_scale=scale_e)
    save(canvas, k+'.png')
# derrotado es ancho y bajo (aplastado): lienzo propio más ancho que alto
im_d = cutout(os.path.join(SRC, 'colesterol_derrotado.png'))
w, h = im_d.size
s = min(180/w, 60/h)
nw, nh = max(1,int(round(w*s))), max(1,int(round(h*s)))
small_d = premultiplied_resize(im_d, nw, nh)
canvas_d = Image.new('RGBA', (180, 60), (0,0,0,0))
canvas_d.paste(small_d, ((180-nw)//2, 60-nh), small_d)
save(canvas_d, 'colesterol_derrotado.png')

# ---- gloculo: coleccionable pequeño, lienzo cuadrado ----
im_g = cutout(os.path.join(SRC, 'gloculo.png'))
save(fit_on_canvas(im_g, 64), 'gloculo.png')

# ---- meta: asta alta y angosta, conserva proporción vertical ----
im_m = cutout(os.path.join(SRC, 'meta.png'))
w, h = im_m.size
s = 260 / h
nw, nh = max(1,int(round(w*s))), 260
small_m = premultiplied_resize(im_m, nw, nh)
canvas_m = Image.new('RGBA', (nw, nh), (0,0,0,0))
canvas_m.paste(small_m, (0,0), small_m)
save(canvas_m, 'meta.png')

# ---- bloque_plataforma: recorte simple, conserva proporción ----
im_p = cutout(os.path.join(SRC, 'bloque_plataforma.png'))
w, h = im_p.size
s = 220 / w
nw, nh = 220, max(1,int(round(h*s)))
canvas_p = premultiplied_resize(im_p, nw, nh)
save(canvas_p, 'bloque_plataforma.png')

# ---- bloque_suelo: tira ancha, se recorta el margen blanco y se deja tal
# cual para repetirse como patrón (no necesita canvas cuadrado) ----
im_s = cutout(os.path.join(SRC, 'bloque_suelo.png'))
save(im_s, 'bloque_suelo.png')

# ---- fondo_nivel1: fondo de escena, se recorta cualquier margen blanco
# pero se queda opaco (es telón de fondo, no sprite recortado) ----
im_f = Image.open(os.path.join(SRC, 'fondo_nivel1.png')).convert('RGB')
save(im_f.convert('RGBA'), 'fondo_nivel1.png', colors=128)

print('\nListo. Revisa assets/processed/ antes de incrustarlas en aventura.html.')
