"""Show print orientations with build Z upward. No geometric changes or inferred supports."""
from design import Model, ROOT, Part
from calibration import print_pose, gauge, tongue
from render import render
from PIL import Image, ImageDraw, ImageFont


def create_atlas():
    items=Model().printed.copy()
    items.update({'09_fit_gauge':gauge(),'10_fit_tongue':tongue()})
    labels={
      '01_frame':'01 枠 ×1', '02_retainer':'02 押さえ ×2',
      '03_jaw':'03 爪 ×2：根元の局所支えが必要', '04_crank':'04 回転板 ×1',
      '05_link':'05 リンク ×2', '06_motor_mount':'06 モーター取付部 ×1',
      '09_fit_gauge':'09 隙間試験片 ×1', '10_fit_tongue':'10 差込み試験片 ×1'}
    font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    canvas=Image.new('RGB',(1600,900),(246,247,250));d=ImageDraw.Draw(canvas)
    d.text((32,18),'PG2 R5 — 印刷姿勢 / 各部品の床面はZ=0',font=ImageFont.truetype(font,27),fill=(34,44,55))
    d.text((32,58),'各図の縮尺は異なります。支えは未描画。追加カメラ・隙間違いの選択品は除外。',font=ImageFont.truetype(font,19),fill=(61,70,80))
    for i,(name,sh) in enumerate(items.items()):
        q=print_pose(name,sh);bb=q.BoundingBox();c=((bb.xmin+bb.xmax)/2,(bb.ymin+bb.ymax)/2,(bb.zmin+bb.zmax)/2)
        color=(.88,.28,.11) if 'jaw' in name else (.21,.63,.48) if 'link' in name else (.3,.33,.37)
        part=Part(name,q,color,'print','printed_polymer','print')
        path=ROOT/'images'/f'print_{name}.png'
        cam=(c[0]+140,c[1]-175,c[2]+155)
        scale=max(14,max(bb.xlen,bb.ylen)*.55+bb.zlen*.45)
        render([part],path,cam=cam,target=c,up=(0,0,1),scale=scale,size=(380,320))
        x=10+(i%4)*400;y=108+(i//4)*390
        canvas.paste(Image.open(path).convert('RGB'),(x,y))
        d.text((x+9,y+326),labels[name],font=ImageFont.truetype(font,18),fill=(34,44,55))
        d.text((x+9,y+352),f'{bb.xlen:.1f} × {bb.ylen:.1f} × {bb.zlen:.1f} mm',font=ImageFont.truetype(font,17),fill=(75,82,90))
    canvas.save(ROOT/'images/print_layout.png')

if __name__=='__main__':create_atlas()
