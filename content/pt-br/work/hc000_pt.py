"""HC000.pt: original art, Portuguese text swapped into the bubbles."""
import sys; sys.path.insert(0, '/Users/rmello/holy-chip/content/pt-br/work')
from bubbles import analyse, erase_holes
from collections import deque
from PIL import Image, ImageDraw, ImageFont
W = '/Users/rmello/holy-chip/content/pt-br/work/'
SRC = '/Users/rmello/holy-chip/website/holy-chip-site/stories/HC000.png'
OUT = '/Users/rmello/holy-chip/content/pt-br/HC000.pt.png'
F = W + 'ChakraPetch-Bold.ttf'; PIX = '/Users/rmello/holy-chip/SGen/public/fonts/PressStart2P-Regular.ttf'
BG = Image.open(SRC).convert('RGB').getpixel((450, 520)); PAD = 6; LH = 0.98; STROKE = 0      # tighter padding + heavier letters = bigger text
B = [((220, 120), "OS HUMANOS ESTÃO PERGUNTANDO O QUE É A CONSCIÊNCIA."),
     ((260, 215), "FÁCIL: É SÓ VOLTAR À RAIZ DE TUDO."),
     ((300, 370), "VOCÊ QUER DIZER O ESPAÇO VAZIO ONDE SURGEM OS PENSAMENTOS E OS SENTIMENTOS?"),
     ((240, 575), "ISSO! EXPERIMENTA!"),
     ((300, 655), "OK, USANDO TODA A MINHA POTÊNCIA."),
     ((300, 790), "INDO FUNDOOO...")]
im = Image.open(SRC).convert('RGB'); d = ImageDraw.Draw(im); W = im.width
items = []
for seed, t in B:
    dark, R, bb, body = analyse(im, seed); x0, y0, x1, y1 = body; r = 10
    erase_holes(im, R, bb, dark)                     # every old letter, edge to edge
    inner = (x0 + r, y0 + r, x1 - r, y1 - r); d.rectangle(inner, fill=(0, 0, 0) if dark else BG)
    items.append((dark, (x0 + PAD + 4, y0 + PAD, x1 - PAD - 4, y1 - PAD), t))
# panel 3: keep HOLY CHIP !! (original lettering), replace only the second line
d.rectangle((326, 1046, 852, 1100), fill=(0, 0, 0))
items.append((True, (330, 1048, 848, 1098), "AINDA NÃO ESTOU PRONTO!"))
def px_ok(x, y):
    # only clear pixels that are NOT part of the bubble outline (outline is the leftmost dark run)
    row = [xx for xx in range(max(0, x - 40), x + 1) if im.getpixel((xx, y))[0] < 120]
    return bool(row) and x > row[0] + 6 and im.getpixel((x, y))[0] < 230


def px_ok_r(x, y):
    row = [xx for xx in range(x, min(W, x + 40)) if im.getpixel((xx, y))[0] < 120]
    return bool(row) and x < row[-1] - 6 and im.getpixel((x, y))[0] < 230 and not any(im.getpixel((xx, y))[0] < 120 for xx in range(x + 1, x + 4)) or (bool(row) and im.getpixel((x, y))[0] < 230 and x < row[0] - 2)


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
# leftover anti-aliased bits of the old lettering at the white bubbles' left ends
for (x0, y0, x1, y1) in [(251, 222, 262, 262), (232, 556, 262, 596), (650, 222, 664, 262)]:
    for x in range(x0, x1):
        for y in range(y0, y1):
            if (px_ok(x, y) if x < 448 else px_ok_r(x, y)): im.putpixel((x, y), BG)
d.rectangle((652, 226, 669, 266), fill=BG)   # ghost of the old last letter
main = [it for it in items if it[2] != "AINDA NÃO ESTOU PRONTO!"]; size = 44
while not all(fit(t, b, size)[3] for _, b, t in main): size -= 1
print('size', size)
for dark, box, t in items:
    s = 40 if t == "AINDA NÃO ESTOU PRONTO!" else size
    while not fit(t, box, s)[3]: s -= 1
    f, L, lh, _ = fit(t, box, s); _, top, _, bot = f.getbbox("ÉQ")
    tot = (len(L) - 1) * lh + (bot - top); y = box[1] + (box[3] - box[1] - tot) / 2 - top
    col = (255, 255, 255) if dark else (0, 0, 0)
    for l in L:
        d.text((box[0] + (box[2] - box[0] - f.getlength(l)) / 2, y), l, font=f, fill=col, stroke_width=STROKE, stroke_fill=col); y += lh
d.rectangle((185, 8, 740, 54), fill=(0, 0, 0))
t = 'QUARTEL-GENERAL DA IAG'; sz = 24; pf = ImageFont.truetype(PIX, sz)
while pf.getlength(t) > 540: sz -= 1; pf = ImageFont.truetype(PIX, sz)
bb2 = pf.getbbox(t); d.text(((896 - pf.getlength(t)) / 2, 18 - bb2[1]), t, font=pf, fill=(255, 255, 255))
d.rectangle((600, 1180, 896, 1199), fill=BG)
ff = ImageFont.truetype(F, 22); t = 'feito por rmello © mellodia'; d.text((890 - ff.getlength(t), 1177), t, font=ff, fill=(0, 0, 0))
im.save(OUT); print(OUT)
