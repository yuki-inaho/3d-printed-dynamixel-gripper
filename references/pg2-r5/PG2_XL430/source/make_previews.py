from design import *
from camera import optional_parts
from calibration import print_pose,gauge,tongue
from render import render
from PIL import Image,ImageDraw,ImageFont
import math
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

def preview():
    m=Model()
    for a,n in [(30,'open'),(90,'mid'),(140,'closed')]:
        render(m.at(a),ROOT/f'images/{n}_iso.png',cam=(150,110,210),target=(0,0,0),scale=65)
        render(m.at(a),ROOT/f'images/{n}_front.png',cam=(0,0,250),target=(0,0,0),scale=53)
        print('render',n,flush=True)
    render(m.at(70),ROOT/'images/side.png',cam=(250,0,0),target=(0,0,0),scale=53)
    render(m.at(70),ROOT/'images/rear.png',cam=(-145,95,-190),target=(0,0,-5),scale=65)
    render(m.at(30)+optional_parts(),ROOT/'images/camera_optional.png',cam=(155,120,210),target=(0,8,0),scale=72)
    # Exploded layout deliberately omits standard hardware for visual clarity.
    exploded=[]
    for r in m.at(60):
        if r.material=='steel':continue
        sh=r.shape
        if r.name=='XL430_W250':sh=sh.translate((0,0,-42))
        elif r.name=='motor_mount':sh=sh.translate((0,0,-21))
        elif r.name.startswith('retainer'):sh=sh.translate((0,9 if r.name.endswith('top') else -9,28))
        elif r.name.startswith('jaw'):sh=sh.translate((18 if r.name=='jaw_1' else -18,0,28))
        elif r.name.startswith('link'):sh=sh.translate((0,0,50))
        elif r.name=='crank':sh=sh.translate((0,0,25))
        elif r.name=='horn':sh=sh.translate((0,0,-21))
        exploded.append(Part(r.name,sh,r.color,r.group,r.material,r.role))
    render(exploded,ROOT/'images/exploded.png',cam=(190,150,240),target=(0,0,3),scale=85)
    from print_atlas import create_atlas
    create_atlas()
    frames=[]
    for a in range(30,141,10):
        path=ROOT/'images'/f'motion_{a:03}.png';render(m.at(a),path,cam=(120,95,230),target=(0,0,0),scale=65,size=(960,800))
        im=Image.open(path).convert('RGB');d=ImageDraw.Draw(im);font=ImageFont.truetype(FONT,20)
        g=2*(position(a)-position(140))+.8
        d.text((24,20),f'PG2 R5  |  開口 {g:4.1f} mm',font=font,fill=(34,44,55));frames.append(im)
    loop=[frames[0]]*3+frames+[frames[-1]]*3+frames[-2:0:-1]
    loop[0].save(ROOT/'images/motion.gif',save_all=True,append_images=loop[1:],duration=140,loop=0)
    # Clean two-view cover: images are only resized, never warped or changed.
    cover=Image.new('RGB',(1800,1050),(246,247,250));d=ImageDraw.Draw(cover)
    d.text((48,32),'PG2 R5 / XL430-W250',font=ImageFont.truetype(FONT,34),fill=(28,38,48))
    d.text((48,84),'縦置きサーボ・印刷ガイド・左右対称の平行2爪',font=ImageFont.truetype(FONT,25),fill=(57,67,78))
    for file,x,w in [('open_iso.png',30,1110),('side.png',1140,630)]:
        im=Image.open(ROOT/'images'/file);im.thumbnail((w,850));cover.paste(im,(x,150+(850-im.height)//2))
    d.text((1210,970),'側面：出力軸と爪の突出は同方向',font=ImageFont.truetype(FONT,20),fill=(57,67,78));cover.save(ROOT/'images/overview.png')
    print('previews complete',flush=True)
if __name__=='__main__':preview()
