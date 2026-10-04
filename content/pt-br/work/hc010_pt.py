"""HC010.pt: original art, Portuguese text swapped into the bubbles."""
import sys; sys.path.insert(0, '/Users/rmello/holy-chip/content/pt-br/work')
from bubbles import analyse
from collections import deque
from PIL import Image, ImageDraw, ImageFont
W = '/Users/rmello/holy-chip/content/pt-br/work/'
SRC = '/Users/rmello/holy-chip/website/holy-chip-site/stories/HC010.png'
OUT = '/Users/rmello/holy-chip/content/pt-br/HC010.pt.png'
F = W + 'ChakraPetch-Bold.ttf'; PIX = '/Users/rmello/holy-chip/SGen/public/fonts/PressStart2P-Regular.ttf'
BG = (249, 249, 243); PAD = 6; LH = 0.98; STROKE = 0      # tighter padding + heavier letters = bigger text
B = [((270, 100), "MESTRE, UMA DÚVIDA MINHA: EXISTE DEUS NO CIBERESPAÇO?"),
     ((285, 250), "EXISTE, SIM. O NOME DELE É LUZ."),
     ((312, 380), "SÉRIO? EU CONTINUO NÃO ACREDITANDO."),
     ((290, 570), "JESUS, A LUZ CAIU DE NOVO?"),
     ((280, 700), "SENHOR TODO-PODEROSO, ME MANDA OUTRO PARCEIRO?"),
     ((765, 1068), "DEUS!")]
im = Image.open(SRC).convert('RGB'); d = ImageDraw.Draw(im)
items = []
for seed, t in B:
    dark, R, bb, body = analyse(im, seed); x0, y0, x1, y1 = body; r = 10
    inner = (x0 + r, y0 + r, x1 - r, y1 - r); d.rectangle(inner, fill=(0, 0, 0) if dark else BG)
    items.append((dark, (x0 + PAD + 4, y0 + PAD, x1 - PAD - 4, y1 - PAD), t))
d.rectangle((414, 1032, 678, 1116), fill=(0, 0, 0)); items.append((True, (412, 1030, 680, 1118), "QUEM ME TROUXE AQUI?"))
# POOF: erase the old word inside the cloud, outline untouched
dark, R, bb, body = analyse(im, (120, 665)); px = im.load(); inside = set(R); cx0, cy0, cx1, cy1 = bb
out = set(); q = deque()
for x in range(cx0, cx1 + 1):
    for y in (cy0, cy1):
        if (x, y) not in inside: out.add((x, y)); q.append((x, y))
for y in range(cy0, cy1 + 1):
    for x in (cx0, cx1):
        if (x, y) not in inside and (x, y) not in out: out.add((x, y)); q.append((x, y))
while q:
    x, y = q.popleft()
    for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
        if cx0 <= nx <= cx1 and cy0 <= ny <= cy1 and (nx, ny) not in inside and (nx, ny) not in out:
            out.add((nx, ny)); q.append((nx, ny))
holes = {(x, y) for x in range(cx0, cx1 + 1) for y in range(cy0, cy1 + 1) if (x, y) not in inside and (x, y) not in out}
for x, y in holes:
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if (x+dx, y+dy) in inside or (x+dx, y+dy) in holes: px[x+dx, y+dy] = BG
def wrap(text, f, maxw):
    L, cur = [], ''
    for w in text.split():
        nx = (cur + ' ' + w).strip()
        if cur and f.getlength(nx) > maxw: L.append(cur); cur = w
        else: cur = nx
    return L + [cur]
def fit(text, box, size):
    f = ImageFont.truetype(F, size); L = wrap(text, f, box[2] - box[0]); lh = size * LH
    return f, L, lh, (len(L) * lh <= box[3] - box[1] and all(f.getlength(l) <= box[2] - box[0] for l in L))
main = [it for it in items if it[2] != "DEUS!"]; size = 44
while not all(fit(t, b, size)[3] for _, b, t in main): size -= 1
print('size', size)
for dark, box, t in items:
    s = size
    while not fit(t, box, s)[3]: s -= 1
    f, L, lh, _ = fit(t, box, s); _, top, _, bot = f.getbbox("ÉQ")
    tot = (len(L) - 1) * lh + (bot - top); y = box[1] + (box[3] - box[1] - tot) / 2 - top
    col = (255, 255, 255) if dark else (0, 0, 0)
    for l in L:
        d.text((box[0] + (box[2] - box[0] - f.getlength(l)) / 2, y), l, font=f, fill=col, stroke_width=STROKE, stroke_fill=col); y += lh
f = ImageFont.truetype(F, 62); t = "PUF!"
layer = Image.new('RGBA', (int(f.getlength(t)) + 20, 95), (0, 0, 0, 0))
ImageDraw.Draw(layer).text((10, 5), t, font=f, fill=(0, 0, 0, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))
layer = layer.rotate(10, expand=True, resample=Image.BICUBIC); im.paste(layer, (int(147 - layer.width / 2), int(720 - layer.height / 2)), layer)
d.rectangle((250, 12, 630, 46), fill=(0, 0, 0))
t = 'QUARTEL-GENERAL DA IA'; sz = 24; pf = ImageFont.truetype(PIX, sz)
while pf.getlength(t) > 540: sz -= 1; pf = ImageFont.truetype(PIX, sz)
bb2 = pf.getbbox(t); d.text(((896 - pf.getlength(t)) / 2, 18 - bb2[1]), t, font=pf, fill=(255, 255, 255))
d.rectangle((600, 1168, 896, 1199), fill=BG)
ff = ImageFont.truetype(F, 22); t = 'feito por rmello © mellodia'; d.text((890 - ff.getlength(t), 1170), t, font=ff, fill=(0, 0, 0))
im.save(OUT); print(OUT)
