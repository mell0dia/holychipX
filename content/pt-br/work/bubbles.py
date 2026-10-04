from PIL import Image
from collections import deque
def region(im, seed, tol=80):
    g=im.convert('L'); W,H=g.size
    dark = g.getpixel(seed) < 128
    ok = (lambda v: v<128) if dark else (lambda v: v>=128)
    px=g.load(); seen=set([seed]); q=deque([seed])
    while q:
        x,y=q.popleft()
        for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0<=nx<W and 0<=ny<H and (nx,ny) not in seen and ok(px[nx,ny]):
                seen.add((nx,ny)); q.append((nx,ny))
    return dark, seen
def analyse(im, seed):
    dark, R = region(im, seed)
    xs=[p[0] for p in R]; ys=[p[1] for p in R]
    x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
    rowc={}; colc={}
    for x,y in R: rowc[y]=rowc.get(y,0)+1; colc[x]=colc.get(x,0)+1
    mr=max(rowc.values()); mc=max(colc.values())
    by=[y for y,c in rowc.items() if c>=0.75*mr]; bx=[x for x,c in colc.items() if c>=0.75*mc]
    body=(min(bx),min(by),max(bx),max(by))
    return dark, R, (x0,y0,x1,y1), body
def erase_holes(im, R, bbox, dark):
    """Paint everything enclosed by region R (the text) with the region's fill."""
    x0,y0,x1,y1=bbox; px=im.load()
    fill=(0,0,0) if dark else None
    if not dark:
        vals=[px[x,y] for (x,y) in list(R)[:4000]]
        fill=tuple(sorted(v[i] for v in vals)[len(vals)//2] for i in range(3))
    # outside = non-R pixels reachable from the bbox border
    out=set(); q=deque()
    for x in range(x0,x1+1):
        for y in (y0,y1):
            if (x,y) not in R: out.add((x,y)); q.append((x,y))
    for y in range(y0,y1+1):
        for x in (x0,x1):
            if (x,y) not in R and (x,y) not in out: out.add((x,y)); q.append((x,y))
    while q:
        x,y=q.popleft()
        for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if x0<=nx<=x1 and y0<=ny<=y1 and (nx,ny) not in R and (nx,ny) not in out:
                out.add((nx,ny)); q.append((nx,ny))
    n=0
    for x in range(x0,x1+1):
        for y in range(y0,y1+1):
            if (x,y) not in R and (x,y) not in out: px[x,y]=fill; n+=1
    return fill, n
