"""Caricature promo: base pose + real comic on an enlarged board + speech bubble.
    python3 build_caricature.py BASE.png COMIC.png OUT.png "LINE 1|LINE 2|LINE 3"
The board is extended LEFT and DOWN (past the frame: depth); its top edge, where the
two fingers pinch it, stays put. See memory project_holychip_caricature_promo."""
import sys
from collections import deque
from PIL import Image, ImageDraw, ImageFont, ImageFilter
base, comic_p, out, text = sys.argv[1:5]
im=Image.open(base).convert('RGB'); W,H=im.size; g=im.convert('L'); px=g.load()
seed=(200,750)
R=set([seed]); q=deque([seed])
while q:
    x,y=q.popleft()
    for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
        if 0<=nx<W and 0<=ny<H and (nx,ny) not in R and px[nx,ny]>225:
            R.add((nx,ny)); q.append((nx,ny))
xs=sorted(p[0] for p in R); ys=sorted(p[1] for p in R)
bx0,bx1=xs[len(xs)//200],xs[-len(xs)//200-1]; by0=ys[len(ys)//200]
tip=max(y for y in range(by0,by0+80) for x in range(bx0+10,bx1-10,2) if px[x,y]<120)   # fingertip bottom
# --- enlarged board: left to near the frame, down past the bottom edge ---
NX0, NY1 = 40, H + 20
hand = Image.new('L',(W,H),0); hp=hand.load()          # the hand/fingers above the old board top stay in front
for y in range(0, tip+1):
    for x in range(W):
        if px[x,y]<235 and y>=by0-140 and bx0-60<x<bx1+20: hp[x,y]=255
board = im.copy(); d=ImageDraw.Draw(board)
BT, BR = by0-5, bx1+5                 # cover Gemini's own board outline
d.rectangle((NX0, BT, BR, NY1), fill=(255,255,255), outline=(0,0,0), width=3)
comic=Image.open(comic_p).convert('RGB')
top=tip+8; m=10; bw,bh=bx1-NX0-2*m, H-top-m
s=min(bw/comic.width, bh/comic.height); cw,ch=round(comic.width*s), round(comic.height*s)
board.paste(comic.resize((cw,ch),Image.LANCZOS),(NX0+m+(bw-cw)//2, top))
# fingers (dark pixels of the original that lie over the board's top strip) go back on top
orig=im
fing=Image.new('L',(W,H),0); fp=fing.load(); op=orig.convert('L').load()
# only the fingertip: the dark span it makes just above its tip, widened a little
row=tip-6
span=[x for x in range(bx0+6, bx1-5) if op[x,row]<200]
fx0, fx1 = min(span)-14, max(span)+14
for y in range(BT-4, tip+2):
    for x in range(fx0, fx1+1):
        if op[x,y]<235: fp[x,y]=255
fing=fing.filter(ImageFilter.MaxFilter(3))
im=Image.composite(orig, board, fing)
# --- speech bubble (4x, Chakra Petch) ---
S=4; BG=orig.getpixel((60,420)); big=im.resize((W*S,H*S),Image.LANCZOS); d=ImageDraw.Draw(big)
d.rectangle((40*S,40*S,370*S,235*S),fill=BG)
F='/Users/rmello/holy-chip/content/pt-br/work/ChakraPetch-Bold.ttf'
lines=text.split('|'); f=ImageFont.truetype(F,40*S); lh=48*S
while max(f.getlength(l) for l in lines) > 520*S: f=ImageFont.truetype(F,f.size-S)
tw=max(f.getlength(l) for l in lines)
x0,y0=52*S,52*S; padx,pady=24*S,20*S
x1=x0+tw+2*padx; y1=y0+lh*len(lines)+2*pady-8*S
tail=[(x1-150*S,y1-6*S),(x1-80*S,y1-6*S),(505*S,305*S)]
d.polygon(tail,fill=(255,255,255),outline=(0,0,0))
d.line([tail[0],tail[2]],fill=(0,0,0),width=4*S); d.line([tail[1],tail[2]],fill=(0,0,0),width=4*S)
d.rounded_rectangle((x0,y0,x1,y1),radius=26*S,fill=(255,255,255),outline=(0,0,0),width=4*S)
d.polygon([(tail[0][0]+4*S,y1-3*S),(tail[1][0]-4*S,y1-3*S),(tail[2][0],tail[2][1]-14*S)],fill=(255,255,255))
y=y0+pady
for l in lines: d.text(((x0+x1)/2,y),l,font=f,fill=(0,0,0),anchor="ma"); y+=lh
big.resize((W,H),Image.LANCZOS).save(out)
print('board', NX0, by0, bx1, 'comic', cw, ch, 'fingertip', tip)
