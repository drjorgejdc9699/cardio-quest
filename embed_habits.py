"""Incrusta assets/habits/processed/*.png (arte ukiyo-e de Rutina 4AM) como
data URI dentro de un bloque HABIT_IMAGES en aventura.html. Reemplaza el
bloque si ya existe (re-ejecutable), o lo inserta justo después de
HABIT_CATEGORIES la primera vez."""
import base64, json, os, re

SRC = '/Users/jorgediaz/cardio-quest'
PROC = os.path.join(SRC, 'assets', 'habits', 'processed')
KEYS = ['icon-app','icon-charge','icon-diet','icon-exercise','icon-study','icon-wake',
        'banner-header','banner-chart']
JS_KEYS = {'icon-app':'app','icon-charge':'charge','icon-diet':'diet','icon-exercise':'exercise',
           'icon-study':'study','icon-wake':'wake','banner-header':'bannerHeader','banner-chart':'bannerChart'}

data = {}
for k in KEYS:
    p = os.path.join(PROC, k + '.png')
    with open(p, 'rb') as f:
        raw = f.read()
    data[JS_KEYS[k]] = 'data:image/png;base64,' + base64.b64encode(raw).decode()
    print(f'{k:16s} {len(raw)/1024:6.1f} KB')

total = sum(len(v) for v in data.values())
print(f'\ntotal data URIs: {total/1024:.0f} KB')

order = ['app','charge','diet','exercise','study','wake','bannerHeader','bannerChart']
block = 'const HABIT_IMAGES = {\n' + ''.join(
    f"  {k}: {json.dumps(data[k])},\n" for k in order) + '};'

path = os.path.join(SRC, 'aventura.html')
src = open(path, encoding='utf-8').read()

if 'const HABIT_IMAGES = {' in src:
    new = re.sub(r'const HABIT_IMAGES = \{.*?\n\};', lambda m: block, src, count=1, flags=re.S)
    assert new != src, 'no se pudo reemplazar el bloque HABIT_IMAGES existente'
else:
    anchor = re.search(r"^const HABIT_CATEGORIES = \[.*?\];\n", src, flags=re.M)
    assert anchor, 'no se encontró HABIT_CATEGORIES como ancla'
    insert_at = anchor.end()
    new = src[:insert_at] + '\n' + block + '\n' + src[insert_at:]

open(path, 'w', encoding='utf-8').write(new)
print('aventura.html actualizado:', len(new)/1024, 'KB')
