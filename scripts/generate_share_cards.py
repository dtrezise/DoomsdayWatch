#!/usr/bin/env python3
"""Design-time share-card helper; committed PNGs keep site builds dependency-free."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
FONTS=Path('/System/Library/Fonts/Supplemental')
def font(size,serif=False):
    paths=[FONTS/('Georgia.ttf' if serif else 'Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf' if serif else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in paths:
        if path.exists():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)
def lines(draw,text,face,width):
    result=[];line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if draw.textlength(candidate,font=face)>width and line:result.append(line);line=word
        else:line=candidate
    if line:result.append(line)
    return result

def card(name,title,label,media):
    canvas=Image.new('RGB',(1200,630),'#f8f6f0')
    photo=Image.open(ROOT/'site'/media['path']).convert('RGB')
    if name=='F002':
        fitted=ImageOps.contain(photo,(600,485));canvas.paste(fitted,(600+(600-fitted.width)//2,(540-fitted.height)//2))
    else:
        fitted=ImageOps.fit(photo,(600,540));canvas.paste(fitted,(600,0))
    d=ImageDraw.Draw(canvas)
    d.rectangle((0,0,600,13),fill='#aa442e')
    d.text((40,44),'PREPAREDNESS',font=font(24,True),fill='#18272b')
    d.text((41,78),'OBSERVATORY',font=font(14),fill='#58615e')
    d.text((41,145),label.upper(),font=font(14),fill='#aa442e')
    face=font(43,True)
    while len(lines(d,title,face,515))>5:face=font(face.size-1,True)
    y=195
    for line in lines(d,title,face,515):
        d.text((38,y),line,font=face,fill='#18272b');y+=face.size+13
    d.rectangle((0,540,1200,630),fill='#18272b')
    d.text((40,557),'PREPAREDNESS OBSERVATORY / REPORTING',font=font(17),fill='#f8f6f0')
    credit='Photo: '+media['credit']
    while d.textlength(credit,font=font(12))>1100:credit=credit[:-2]
    d.text((40,590),credit,font=font(12),fill='#d7dcd4')
    canvas.save(ROOT/'site/assets'/f'{name}.png')

if __name__=='__main__':
    media=json.loads((ROOT/'site/media.json').read_text())
    card('share','How governments prepare for the next crisis.','Independent reporting',media['gunston-hall-norway'])
    for f in json.loads((ROOT/'site/findings.json').read_text()):
        if f['publication_status']=='published':card(f['id'],f['title'],f['kicker'],media[f['image_id']])
