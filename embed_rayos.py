"""Procesa assets/rayos/*.png (arte ukiyo-e del juego Rayos) y los incrusta
como data URIs dentro de un bloque RAYOS_IMAGES en aventura.html. Reemplaza
el bloque si ya existe (re-ejecutable), igual que embed_habits.py."""
import base64, os, re
from PIL import Image

SRC = '/Users/jorgediaz/cardio-quest'
RAW = os.path.join(SRC, 'assets', 'rayos')
OUT = os.path.join(RAW, 'processed')
os.makedirs(OUT, exist_ok=True)

TARGETS = {
    'cardBack': ('card-back.png', 220),   # ancho objetivo en px, alto se ajusta por proporción
    'banner':   ('banner.png', 1400),
}

data = {}
for key, (fname, target_w) in TARGETS.items():
    im = Image.open(os.path.join(RAW, fname)).convert('RGB')
    w, h = im.size
    target_h = round(h * target_w / w)
    im = im.resize((target_w, target_h), Image.LANCZOS)
    im = im.quantize(colors=256, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG)
    out_path = os.path.join(OUT, fname)
    im.save(out_path, optimize=True)
    raw = open(out_path, 'rb').read()
    data[key] = 'data:image/png;base64,' + base64.b64encode(raw).decode()
    print(f'{key:10s} {target_w}x{target_h}  {len(raw)/1024:6.1f} KB')

total = sum(len(v) for v in data.values())
print(f'\ntotal data URIs: {total/1024:.0f} KB')

block = 'const RAYOS_IMAGES = {\n' + ''.join(f"  {k}: {data[k]!r},\n" for k in data) + '};'
# json.dumps sería más seguro que repr para JS, pero estas cadenas son puro
# base64 (sin comillas ni backslashes), así que repr() produce JS válido.
block = block.replace("'", '"')

path = os.path.join(SRC, 'aventura.html')
src = open(path, encoding='utf-8').read()
pattern = r'const RAYOS_IMAGES = \{.*?\};'
assert re.search(pattern, src, flags=re.S), 'no se encontró el placeholder RAYOS_IMAGES'
new_src = re.sub(pattern, lambda m: block, src, count=1, flags=re.S)
assert new_src != src
open(path, 'w', encoding='utf-8').write(new_src)
print('aventura.html actualizado:', len(new_src)/1024, 'KB')
