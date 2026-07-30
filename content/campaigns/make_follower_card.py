from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
W,H=1080,1080; PAD=60
BG=(248,244,232); FG=(28,28,26); MUTED=(140,140,132)
BUBBLE_BG=(16,16,16); BUBBLE_FG=(245,240,226); REDTXT=(236,84,84)
TOOLS=Path.home()/"holy-chip/tools"; NFT=Path.home()/"holy-chip/nft/collection/assets"
FBODY=str(TOOLS/"fonts/ShareTechMono-Regular.ttf")
REDWORDS={"1,000","fans"}
def wrap_colored(words,f,d,mw):
    spw=d.textbbox((0,0)," ",font=f)[2]; lines=[]; cur=[]; cw=0
    for w,c in words:
        ww=d.textbbox((0,0),w,font=f)[2]; add=ww if not cur else ww+spw
        if cw+add<=mw: cur.append((w,c,ww)); cw+=add
        else: lines.append(cur); cur=[(w,c,ww)]; cw=ww
    if cur: lines.append(cur)
    return lines,spw
def render(phrase,nft_id,out):
    img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    ff=ImageFont.truetype(FBODY,28); fy=H-38; fty=fy-34
    ch=Image.open(NFT/f"{nft_id}.png").convert("RGB")
    for cx,cy in [(0,0),(ch.width-1,0),(0,ch.height-1),(ch.width-1,ch.height-1)]:
        if ch.getpixel((cx,cy))==(255,255,255): ImageDraw.floodfill(ch,(cx,cy),BG,thresh=8)
    th=470; r=th/ch.height; chr=ch.resize((int(ch.width*r),th),Image.LANCZOS)
    cx=(W-chr.width)//2; cy=fty-30-th; img.paste(chr,(cx,cy))
    words=[(w, REDTXT if w in REDWORDS else BUBBLE_FG) for w in phrase.split()]
    bt_top=PAD; bmax=(cy-28)-bt_top; size=50; mw=(W-2*PAD)-56
    while size>=18:
        f=ImageFont.truetype(FBODY,size); lines,spw=wrap_colored(words,f,d,mw)
        lh=int(size*1.42); bh=lh*len(lines)+76
        if bh<=bmax: break
        size-=2
    bb=bt_top+bh
    d.rounded_rectangle([(PAD,bt_top),(W-PAD,bb)],radius=14,fill=BUBBLE_BG)
    tx=W//2; d.polygon([(tx-24,bb),(tx+24,bb),(tx,bb+28)],fill=BUBBLE_BG)
    y=bt_top+38
    for ln in lines:
        total=sum(ww for _,_,ww in ln)+spw*(len(ln)-1); x=W//2-total/2
        for w,col,ww in ln:
            d.text((x,y),w,fill=col,font=f,anchor="la"); x+=ww+spw
        y+=lh
    d.line([(PAD,fty-14),(W-PAD,fty-14)],fill=MUTED,width=1)
    d.text((W//2,fy),"holy-chip.com",fill=FG,font=ff,anchor="md")
    img.save(out,"PNG",optimize=True); print("OK:",out)
FB="We're flattered, a little concerned, and genuinely grateful. 1,000 fans on Facebook in 20 days. Holy Chip!"
XIG="We just hit 1,000 fans on Facebook. Out here on X and Instagram, it's mostly us and the void. If you can read this, wave back."
render(FB,21,"/tmp/hc_1000_fb.png")
render(XIG,13,"/tmp/hc_followers_xig.png")
