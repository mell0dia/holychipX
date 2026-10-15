"""Black-and-white image except the red nose: keep the roundest saturated-red blob near (cx, cy)."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
def red_nose_only(src, dst, cx=512, cy=540):
    im = np.asarray(Image.open(src).convert('RGB')).astype(float) / 255
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    sat = (im.max(2) - im.min(2)) / (im.max(2) + 1e-6)
    lab, n = ndimage.label((r > 0.45) & (r > g * 1.6) & (r > b * 1.6) & (sat > 0.45)); best = None
    for k in range(1, n + 1):
        ys, xs = np.where(lab == k)
        if len(xs) < 300: continue
        h = np.ptp(ys) + 1; w = np.ptp(xs) + 1
        if min(h, w) / max(h, w) < 0.65 or len(xs) < 0.5 * h * w: continue   # a nose is round and filled (mouths/bow ties are not)
        score = (xs.mean() - cx) ** 2 + (ys.mean() - cy) ** 2 - 40000 * min(h, w) / max(h, w)
        if best is None or score < best[0]: best = (score, k)
    gray = (0.299 * r + 0.587 * g + 0.114 * b)[..., None].repeat(3, 2)
    out = gray if best is None else np.where(ndimage.binary_dilation(lab == best[1], iterations=3)[..., None], im, gray)
    Image.fromarray((out * 255).astype(np.uint8)).save(dst); return best is not None
if __name__ == '__main__':
    print(red_nose_only(sys.argv[1], sys.argv[2]))


def paint_nose(src, dst, seed, radius=80, tol=38):
    """Hand-placed fix: the whole image grey, then the nose region grown from `seed` painted red (shading kept)."""
    from collections import deque
    im = Image.open(src).convert('RGB'); g = im.convert('L'); px = g.load(); W, H = g.size
    base = px[seed]; reg = {seed}; q = deque([seed])
    while q:
        x, y = q.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= n[0] < W and 0 <= n[1] < H and n not in reg and (n[0] - seed[0]) ** 2 + (n[1] - seed[1]) ** 2 < radius ** 2 \
               and abs(px[n] - base) < tol + (60 if px[n] > base else 0):      # include the bright highlight
                reg.add(n); q.append(n)
    out = Image.merge('RGB', [g, g, g]); op = out.load()
    for x, y in reg:
        L = px[x, y]; op[x, y] = (min(255, 150 + int(L * 0.45)), int(L * 0.18), int(L * 0.18))
    out.save(dst); return len(reg)
