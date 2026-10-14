"""Caricature promo, board drawn by Gemini at its final size (no extension):
    python3 build_caricature2.py BASE.png COMIC.png OUT.png "LINE 1|LINE 2|LINE 3"
Comic pasted only inside the white board (flood-fill mask) so the fingers stay
in front, with a white margin under the fingertip; then the speech bubble."""
import sys
from collections import deque
from PIL import Image, ImageDraw, ImageFont, ImageFilter
base, comic_p, out, text = sys.argv[1:5]
im=Image.open(base).convert('RGB'); W,H=im.size; g=im.convert('L'); px=g.load()
seed=next((x,y) for y in range(H-60,H//2,-10) for x in range(60,W//2,10) if px[x,y]>245)
R=set([seed]); q=deque([seed])
while q:
    x,y=q.popleft()
    for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
        if 0<=nx<W and 0<=ny<H and (nx,ny) not in R and px[nx,ny]>225:
            R.add((nx,ny)); q.append((nx,ny))
xs=sorted(p[0] for p in R); ys=sorted(p[1] for p in R)
bx0,bx1=xs[len(xs)//300],xs[-len(xs)//300-1]; by0,by1=ys[len(ys)//300],ys[-1]
tip=max(y for y in range(by0,by0+90) for x in range(bx0+10,bx1-10,2) if px[x,y]<120)
mask=Image.new('L',(W,H),0); mp=mask.load()
for p in R: mp[p]=255
mask=mask.filter(ImageFilter.MaxFilter(3))
comic=Image.open(comic_p).convert('RGB')
top=tip+18; m=10; bw,bh=bx1-bx0-2*m, by1-top-m
s=min(bw/comic.width, bh/comic.height); cw,ch=round(comic.width*s), round(comic.height*s)
layer=Image.new('RGB',(W,H),(255,255,255))
layer.paste(comic.resize((cw,ch),Image.LANCZOS),(bx0+m+(bw-cw)//2, top))
im=Image.composite(layer, im, mask)
S=4; BG=im.getpixel((W//2,20)) if sum(im.getpixel((W//2,20)))>600 else (240,236,226)
# Gemini's faint balloon sits top-left inside the frame: paint it with the paper colour
paper=im.getpixel((W-80,300))
big=im.resize((W*S,H*S),Image.LANCZOS); d=ImageDraw.Draw(big)
d.rectangle((40*S,40*S,min(370,bx1)*S,min(235,by0-10)*S),fill=paper)
F='/Users/rmello/holy-chip/content/pt-br/work/ChakraPetch-Bold.ttf'
# a line starting with "**" is the shout: bigger and heavier than the rest
raw=text.split('|'); lines=[(l[2:], True) if l.startswith('**') else (l, False) for l in raw]
f=ImageFont.truetype(F,40*S)
while max(f.getlength(t)*(1.35 if b else 1) for t,b in lines) > 520*S: f=ImageFont.truetype(F,f.size-S)
fb=ImageFont.truetype(F,int(f.size*1.35))
fnt=lambda b: fb if b else f
lhs=[int(fnt(b).size*1.2) for t,b in lines]
tw=max(fnt(b).getlength(t)+(2*S if b else 0) for t,b in lines)
x0,y0=52*S,52*S; padx,pady=24*S,20*S
x1=x0+tw+2*padx; y1=y0+sum(lhs)+2*pady-8*S
tail=[(x1-150*S,y1-6*S),(x1-80*S,y1-6*S),(505*S,max(305*S, y1+60*S))]
d.polygon(tail,fill=(255,255,255),outline=(0,0,0))
d.line([tail[0],tail[2]],fill=(0,0,0),width=4*S); d.line([tail[1],tail[2]],fill=(0,0,0),width=4*S)
d.rounded_rectangle((x0,y0,x1,y1),radius=26*S,fill=(255,255,255),outline=(0,0,0),width=4*S)
d.polygon([(tail[0][0]+4*S,y1-3*S),(tail[1][0]-4*S,y1-3*S),(tail[2][0],tail[2][1]-14*S)],fill=(255,255,255))
y=y0+pady
for (t,b),lh in zip(lines,lhs):
    d.text(((x0+x1)/2,y),t,font=fnt(b),fill=(0,0,0),anchor="ma",stroke_width=(2*S if b else 0),stroke_fill=(0,0,0)); y+=lh
big.resize((W,H),Image.LANCZOS).save(out)
print('board',bx0,by0,bx1,by1,'tip',tip,'comic',cw,ch)
