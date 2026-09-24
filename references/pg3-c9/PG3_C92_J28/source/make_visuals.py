"""Render revised CAD, never substitute a generative concept illustration."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import jaw_revision as j
from jaw_revision import base, ROOT
from render import render
from printing import print_orientation
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)

def caption(image,title,sub):
    out=Image.new('RGB',(image.width,image.height+100),'white');out.paste(image,(0,100));d=ImageDraw.Draw(out)
    d.text((22,12),title,font=font(28,True),fill='#1a303d')
    d.text((22,57),sub,font=font(19),fill='#4d626d');return out

def main():
    im=ROOT/'images';d=j.parts();old=base.parts()
    settings=dict(cam=(125,-180,110),target=(0,-23,-5),scale=57,size=(1000,840))
    render(base.assembled(90,d=old,world_coords=True),im/'before.png',**settings)
    render(j.assembled(90,d=d,world_coords=True),im/'after.png',**settings)
    b=caption(Image.open(im/'before.png'),'C7：爪まで小さくしすぎた前案','爪の前後長12.1 mm / パッド奥行3 mm')
    a=caption(Image.open(im/'after.png'),'C92-J28：本体は維持、把持部を拡張','爪の前後長28 mm / パッド奥行20 mm')
    canvas=Image.new('RGB',(2000,b.height+80),'white');canvas.paste(b,(0,0));canvas.paste(a,(1000,0))
    draw=ImageDraw.Draw(canvas);draw.text((24,b.height+20),'同縮尺・同じ開閉角度。全幅92 mmと最大開口48.9 mmは不変。全奥行は61.8 → 77.7 mm。',font=font(24),fill='#233d4b');canvas.save(im/'comparison.png')
    for angle,name in [(25,'open'),(135,'closed')]:
        render(j.assembled(angle,d=d,world_coords=True),im/(name+'.png'),**settings)
    side=dict(cam=(220,-25,-5),target=(0,-23,-5),scale=46,size=(1100,800))
    render(j.assembled(90,d=d,world_coords=True),im/'side.png',**side)
    items=j.assembled(90,d=d,world_coords=True)
    render(items,im/'front.png',cam=(0,-220,-5),target=(0,0,-5),scale=43,size=(1100,800))
    # This is a geometry-clearance object; it is NOT evidence of load capacity.
    from scipy.optimize import brentq
    angle=brentq(lambda a:base.opening(a,j.P)-25,25,135)
    block=base.world(base.box(-12.5,12.5,-12,12,39.7,59.7))
    its=j.assembled(angle,d=d,world_coords=True)
    its.append(base.Item('25mm_test_block',block,'object','test',(.69,.67,.61)))
    render(its,im/'grasp_space.png',**settings)
    # Four actually changed parts, already placed in their STL printing orientations.
    sheet=Image.new('RGB',(1400,1110),'white');draw=ImageDraw.Draw(sheet)
    draw.text((24,12),'交換する印刷部品：左右の爪と左右のスライダ、各1個',font=font(28,True),fill='#233d4b')
    for k,name in enumerate(j.CHANGED_PARTS):
        pp=print_orientation(name,d[name]);bb=base.bounds(pp)
        fn=im/(name+'_print.png')
        render([base.Item(name,pp,'print','print',base.COLORS['jaw'])],fn,cam=(80,-120,95),
               target=(0,0,(bb[2]+bb[5])/2),scale=32,size=(660,400))
        x=(k%2)*700;y=80+(k//2)*500
        sheet.paste(Image.open(fn),(x+20,y+45));draw.text((x+24,y),name+' ×1',font=font(22,True),fill='#233d4b')
        note='背面を下。浮いた支点根元のみ局所支持。' if 'carriage' in name else '平らな把持面を下。根元の腕には局所支持。'
        draw.text((x+24,y+450),note,font=font(20),fill='#4d626d')
    sheet.save(im/'changed_print_atlas.png')
    frames=[]
    for a in np.linspace(25,135,13):
        fn=im/'tmp.png';render(j.assembled(float(a),d=d,world_coords=True),fn,cam=(125,-180,110),target=(0,-23,-5),scale=57,size=(660,550))
        image=Image.open(fn).copy();draw=ImageDraw.Draw(image);draw.text((16,10),f'C92-J28  開口 {base.opening(a,j.P):.1f} mm',font=font(21,True),fill='#233d4b');frames.append(image)
    seq=frames+frames[-2:0:-1];seq[0].save(im/'motion.gif',save_all=True,append_images=seq[1:],loop=0,duration=170,optimize=True)
    (im/'tmp.png').unlink(missing_ok=True)
    print('VISUALS DONE',flush=True)

if __name__=='__main__':main()
