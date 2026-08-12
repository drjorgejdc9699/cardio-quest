"""Incrusta assets/processed/*.png del minijuego 'Corazón Bros' como data URI
dentro de un bloque PLATFORMER_IMAGES en aventura.html. Reemplaza el bloque
si ya existe (re-ejecutable), o lo inserta justo después de SPRITE_IMAGES la
primera vez."""
import base64, json, os, re

SRC = '/Users/jorgediaz/cardio-quest'
PROC = os.path.join(SRC, 'assets', 'processed')
KEYS = ['corazon_quieto','corazon_camina1','corazon_camina2','corazon_salto','corazon_golpeado',
        'colesterol_1','colesterol_2','colesterol_derrotado',
        'bloque_suelo','bloque_plataforma','gloculo','meta','fondo_nivel1']

data = {}
for k in KEYS:
    p = os.path.join(PROC, k + '.png')
    with open(p, 'rb') as f:
        raw = f.read()
    data[k] = 'data:image/png;base64,' + base64.b64encode(raw).decode()
    print(f'{k:22s} {len(raw)/1024:6.1f} KB')

total = sum(len(v) for v in data.values())
print(f'\ntotal data URIs: {total/1024:.0f} KB')

block = 'const PLATFORMER_IMAGES = {\n' + ''.join(
    f"  {k}: {json.dumps(data[k])},\n" for k in KEYS) + '};'

path = os.path.join(SRC, 'aventura.html')
src = open(path, encoding='utf-8').read()

if 'const PLATFORMER_IMAGES = {' in src:
    new = re.sub(r'const PLATFORMER_IMAGES = \{.*?\n\};', lambda m: block, src, count=1, flags=re.S)
    assert new != src, 'no se pudo reemplazar el bloque PLATFORMER_IMAGES existente'
else:
    anchor = re.search(r'^const SPRITE_IMAGES = \{.*?\n\};\n', src, flags=re.S | re.M)
    assert anchor, 'no se encontró el bloque SPRITE_IMAGES como ancla'
    insert_at = anchor.end()
    new = src[:insert_at] + '\n' + block + '\n' + src[insert_at:]

open(path, 'w', encoding='utf-8').write(new)
print('aventura.html actualizado:', len(new)/1024, 'KB')
