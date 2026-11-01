#!/usr/bin/env python3
"""Optional design-time helper; PNGs are committed, so site builds need no Pillow."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
FONTS=Path('/System/Library/Fonts/Supplemental')
def font(size,serif=False):
    candidates=[FONTS/('Georgia.ttf' if serif else 'Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf' if serif else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in candidates:
        if path.exists(): return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)
def lines(draw,text,face,width):
    result=[];line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if draw.textlength(candidate,font=face)>width and line:
            result.append(line);line=word
        else: line=candidate
    if line:result.append(line)
    return result

def card(name,title,summary,label):
    image=Image.new('RGB',(1200,630),'#f5f3ec');d=ImageDraw.Draw(image)
    d.rectangle((0,0,1200,19),fill='#285649')
    d.text((60,54),'PREPAREDNESS / OBSERVATORY',font=font(22),fill='#285649')
    d.text((60,112),label.upper(),font=font(17),fill='#53625e')
    titlefont=font(52,True)
    while len(lines(d,title,titlefont,1065))>3:
        titlefont=font(titlefont.size-2,True)
    y=165
    for line in lines(d,title,titlefont,1065):
        d.text((58,y),line,font=titlefont,fill='#172c2c');y+=64
    y+=20
    for line in lines(d,summary,font(23),1065)[:3]:
        d.text((60,y),line,font=font(23),fill='#53625e');y+=33
    d.line((60,542,1140,542),fill='#cbd2c8',width=2)
    d.text((60,565),'PUBLIC EVIDENCE. MEASURED CONTEXT.',font=font(18),fill='#285649')
    d.text((700,565),'dtrezise.github.io/Preparedness',font=font(18),fill='#53625e')
    image.save(ROOT/'site/assets'/f'{name}.png')

if __name__=='__main__':
    card('share','Read the signals. Question the pattern.','An open investigation into government preparedness and potential global threats. Sources and uncertainty stay together.','Public-source research')
    for f in json.loads((ROOT/'site/findings.json').read_text()):
        if f['publication_status']=='published':
            card(f['id'],f['title'],f['boundary'],f['id']+' / Verified documentary record')
