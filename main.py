#!/usr/bin/env python3
"""A deterministic newspaper, drawn and PNG-encoded using only Python's stdlib."""
import hashlib
import math
import os
from pathlib import Path
import struct
import zlib

WIDTH = HEIGHT = 1024
SS = 2  # Render at twice the size for crisp, antialiased geometric lettering.
PAPER = (247, 243, 232)
INK = (25, 27, 27)
RED = (156, 32, 40)
WHITE = (255, 253, 246)

# Original 5 x 7 bitmap alphabet. Glyphs are trimmed horizontally for proportional
# spacing; lowercase has its own drawings rather than being silently uppercased.
GLYPHS = {}
UPPER = {
'A':'01110/10001/10001/11111/10001/10001/10001',
'B':'11110/10001/10001/11110/10001/10001/11110',
'C':'01111/10000/10000/10000/10000/10000/01111',
'D':'11110/10001/10001/10001/10001/10001/11110',
'E':'11111/10000/10000/11110/10000/10000/11111',
'F':'11111/10000/10000/11110/10000/10000/10000',
'G':'01111/10000/10000/10111/10001/10001/01111',
'H':'10001/10001/10001/11111/10001/10001/10001',
'I':'111/010/010/010/010/010/111',
'J':'00111/00010/00010/00010/10010/10010/01100',
'K':'10001/10010/10100/11000/10100/10010/10001',
'L':'10000/10000/10000/10000/10000/10000/11111',
'M':'10001/11011/10101/10101/10001/10001/10001',
'N':'10001/11001/11001/10101/10011/10011/10001',
'O':'01110/10001/10001/10001/10001/10001/01110',
'P':'11110/10001/10001/11110/10000/10000/10000',
'Q':'01110/10001/10001/10001/10101/10010/01101',
'R':'11110/10001/10001/11110/10100/10010/10001',
'S':'01111/10000/10000/01110/00001/00001/11110',
'T':'11111/00100/00100/00100/00100/00100/00100',
'U':'10001/10001/10001/10001/10001/10001/01110',
'V':'10001/10001/10001/10001/10001/01010/00100',
'W':'10001/10001/10001/10101/10101/11011/10001',
'X':'10001/10001/01010/00100/01010/10001/10001',
'Y':'10001/10001/01010/00100/00100/00100/00100',
'Z':'11111/00001/00010/00100/01000/10000/11111',
'0':'01110/10001/10011/10101/11001/10001/01110',
'1':'010/110/010/010/010/010/111',
'2':'01110/10001/00001/00010/00100/01000/11111',
'3':'11110/00001/00001/01110/00001/00001/11110',
'4':'00010/00110/01010/10010/11111/00010/00010',
'5':'11111/10000/10000/11110/00001/00001/11110',
'6':'01110/10000/10000/11110/10001/10001/01110',
'7':'11111/00001/00010/00100/01000/01000/01000',
'8':'01110/10001/10001/01110/10001/10001/01110',
'9':'01110/10001/10001/01111/00001/00001/01110',
}
LOWER = {
'a':'00000/00000/01110/00001/01111/10001/01111',
'b':'10000/10000/11110/10001/10001/10001/11110',
'c':'00000/00000/01111/10000/10000/10000/01111',
'd':'00001/00001/01111/10001/10001/10001/01111',
'e':'00000/00000/01110/10001/11111/10000/01111',
'f':'00110/01000/11100/01000/01000/01000/01000',
'g':'00000/00000/01111/10001/10001/10001/01111/00001/01110',
'h':'10000/10000/11110/10001/10001/10001/10001',
'i':'1/0/1/1/1/1/1',
'j':'001/000/001/001/001/101/010',
'k':'10000/10000/10010/10100/11000/10100/10010',
'l':'10/10/10/10/10/10/01',
'm':'00000/00000/11010/10101/10101/10101/10101',
'n':'00000/00000/11110/10001/10001/10001/10001',
'o':'00000/00000/01110/10001/10001/10001/01110',
'p':'00000/00000/11110/10001/10001/10001/11110/10000/10000',
'q':'00000/01111/10001/10001/01111/00001/00001',
'r':'0000/0000/1011/1100/1000/1000/1000',
's':'00000/00000/01111/10000/01110/00001/11110',
't':'0100/0100/1111/0100/0100/0100/0011',
'u':'00000/00000/10001/10001/10001/10001/01111',
'v':'00000/00000/10001/10001/10001/01010/00100',
'w':'00000/00000/10001/10001/10101/10101/01010',
'x':'00000/00000/10001/01010/00100/01010/10001',
'y':'00000/10001/10001/01111/00001/10001/01110',
'z':'00000/00000/11111/00010/00100/01000/11111',
}
PUNCT = {
'.':'0/0/0/0/0/0/1', ',':'00/00/00/00/00/01/10',
':':'0/0/1/0/1/0/0', ';':'00/00/01/00/01/01/10',
"'":'1/1/0/0/0/0/0', '-':'000/000/000/111/000/000/000',
'—':'00000/00000/00000/11111/00000/00000/00000',
'/':'00001/00001/00010/00100/01000/10000/10000',
'%':'11001/11010/00010/00100/01000/01011/10011',
}
for ch, pattern in (UPPER | LOWER | PUNCT).items():
    rows = pattern.split('/')
    occupied = [x for x in range(len(rows[0])) if any(r[x] == '1' for r in rows)]
    GLYPHS[ch] = [r[min(occupied):max(occupied)+1] for r in rows]


def text_width(text, sx, bold=False):
    """Exact advance and ink width, shared by layout and drawing."""
    if not text:
        return 0
    return (sum(3 if c == ' ' else len(GLYPHS[c][0]) + 1 for c in text)
            - 1 + (0.22 if bold else 0)) * sx


def wrap(text, width, sx, bold=False):
    """Wrap only at word boundaries. Oversized individual words are errors."""
    lines, line = [], ''
    for word in text.split():
        if text_width(word, sx, bold) > width:
            raise ValueError('Word exceeds text zone: ' + word)
        candidate = (line + ' ' + word).strip()
        if text_width(candidate, sx, bold) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


class Canvas:
    def __init__(self):
        self.width = WIDTH * SS
        self.pixels = bytearray(bytes(PAPER) * (self.width * HEIGHT * SS))

    def rect(self, x, y, w, h, color=INK):
        x0, y0 = max(0, round(x * SS)), max(0, round(y * SS))
        x1, y1 = min(self.width, round((x+w)*SS)), min(HEIGHT*SS, round((y+h)*SS))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1-x0)
        for yy in range(y0, y1):
            start = (yy*self.width+x0)*3
            self.pixels[start:start+len(row)] = row

    def poly(self, points, color=INK):
        points = [(x*SS, y*SS) for x, y in points]
        for yy in range(max(0, math.floor(min(y for _, y in points))),
                        min(HEIGHT*SS, math.ceil(max(y for _, y in points)))):
            scan = yy + .5
            cuts = []
            for (x1,y1),(x2,y2) in zip(points, points[1:]+points[:1]):
                if min(y1,y2) <= scan < max(y1,y2):
                    cuts.append(x1+(scan-y1)*(x2-x1)/(y2-y1))
            cuts.sort()
            for a,b in zip(cuts[::2],cuts[1::2]):
                self.rect(a/SS, yy/SS, (b-a)/SS, 1/SS, color)

    def line(self, x1, y1, x2, y2, thickness=3, color=INK):
        dx,dy = x2-x1,y2-y1
        length = math.hypot(dx,dy)
        if not length:
            return
        nx,ny = -dy/length*thickness/2,dx/length*thickness/2
        self.poly([(x1+nx,y1+ny),(x2+nx,y2+ny),
                   (x2-nx,y2-ny),(x1-nx,y1-ny)],color)

    def circle(self, x, y, radius, color=INK):
        self.poly([(x+radius*math.cos(i*math.tau/80),
                    y+radius*math.sin(i*math.tau/80)) for i in range(80)],color)

    def text(self, text, x, y, sx, sy=None, bold=False, color=INK, bounds=None):
        sy = sx if sy is None else sy
        width = text_width(text,sx,bold)
        if bounds is not None:
            bx,by,bw,bh = bounds
            assert x >= bx and y >= by and x+width <= bx+bw+.01 and y+7*sy <= by+bh+.01, (text,bounds)
        cursor = x
        for ch in text:
            if ch == ' ':
                cursor += 3*sx
                continue
            rows = GLYPHS[ch]
            for yy,row in enumerate(rows):
                for xx,bit in enumerate(row):
                    if bit == '1':
                        self.rect(cursor+xx*sx,y+yy*sy,sx*(1.22 if bold else 1),sy,color)
            cursor += (len(rows[0])+1)*sx

    def rgb(self):
        """Box downsample the fixed 2x rendering, using integer arithmetic."""
        result = bytearray(WIDTH*HEIGHT*3)
        src = self.pixels
        stride = self.width*3
        for y in range(HEIGHT):
            for x in range(WIDTH):
                a = y*2*stride+x*6
                b = (y*WIDTH+x)*3
                for c in range(3):
                    result[b+c] = (src[a+c]+src[a+3+c]+src[a+stride+c]+src[a+stride+3+c]+2)//4
        return result


def pictogram(c, kind, x, y, size):
    """Draw the nine pictograms in a common 100-unit reserved square."""
    def r(a,b,w,h,col=INK): c.rect(x+a*size/100,y+b*size/100,w*size/100,h*size/100,col)
    def p(points,col=INK): c.poly([(x+a*size/100,y+b*size/100) for a,b in points],col)
    def l(a,b,d,e,t=4,col=INK): c.line(x+a*size/100,y+b*size/100,x+d*size/100,y+e*size/100,t*size/100,col)
    def o(a,b,rad,col=INK): c.circle(x+a*size/100,y+b*size/100,rad*size/100,col)
    if kind == 'court':
        p([(7,30),(50,7),(93,30)]); r(10,35,80,7)
        for a in (17,36,55,74): r(a,47,9,36)
        r(10,85,80,6); r(5,94,90,5); r(43,22,14,5,RED)
    elif kind == 'tanker':
        p([(5,60),(94,60),(78,79),(21,79)]); r(17,44,60,12); r(70,28,16,28)
        for a in (23,39,55): r(a,35,9,8)
        for a in (12,41,70): l(a,89,a+18,89,4,RED)
        p([(35,31),(27,23),(33,5),(39,19),(44,10),(49,25),(44,31)],RED)
    elif kind == 'drone':
        l(24,28,77,78,7); l(76,28,24,78,7); p([(40,38),(60,38),(65,65),(50,77),(35,65)])
        for a,b in ((22,25),(78,25),(22,80),(78,80)):
            o(a,b,15); o(a,b,10,PAPER); l(a-18,b,a+18,b,3,RED)
    elif kind == 'chip':
        for a in (28,43,58,73):
            r(a,7,4,15); r(a,78,4,15); r(7,a,15,4); r(78,a,15,4)
        r(23,23,54,54); r(32,32,36,36,PAPER); r(40,40,20,20,RED)
    elif kind == 'scales':
        l(50,13,50,85,6); o(50,16,6,RED); l(17,30,83,30,5)
        for a in (23,77):
            l(a,30,a-15,61,2); l(a,30,a+15,61,2)
            p([(a-18,61),(a+18,61),(a+11,73),(a-11,73)])
        r(30,86,40,6); r(22,94,56,4)
    elif kind == 'helicopter':
        l(13,19,88,19,5); l(52,19,52,37,4); l(10,44,36,55,8)
        p([(35,39),(66,39),(84,52),(84,64),(36,64),(25,54)])
        p([(64,43),(77,52),(64,52)],PAPER); r(6,32,6,24)
        l(44,65,40,77,4); l(70,65,74,77,4); l(28,79,87,79,5)
        l(14,87,38,87,3,RED)
    elif kind == 'cart':
        l(6,22,18,22,5); l(18,22,31,70,5); l(31,70,83,70,5)
        p([(23,31),(93,31),(82,59),(30,59)]); r(38,38,36,5,PAPER)
        o(37,84,7); o(76,84,7); r(47,14,23,8,RED)
    elif kind == 'globe':
        o(50,50,42); o(50,50,37,PAPER)
        for a in (-1,1):
            pts=[(50+a*20*math.sin(t*math.pi/30),12+76*t/30) for t in range(31)]
            for (u,v),(w,z) in zip(pts,pts[1:]): l(u,v,w,z,3)
        l(10,50,90,50,3); l(18,31,82,31,3); l(18,69,82,69,3)
        o(50,50,6,RED)
    elif kind == 'trophy':
        # Round, open handles behind a simple tapered cup.
        for a in (28,72):
            o(a,35,19); o(a,35,12,PAPER)
        p([(28,16),(72,16),(68,51),(59,64),(41,64),(32,51)])
        r(46,63,8,21); r(29,84,42,8,RED)
        p([(50,25),(53,33),(62,33),(55,39),(57,48),(50,43),(43,48),(45,39),(38,33),(47,33)],PAPER)


HERO = ('US - CHINA / TECH LAW', 'HUAWEI FOUND GUILTY IN US TRIAL',
        'A New York jury convicts the Chinese tech giant of trade-secret conspiracy and bank fraud — but clears it of racketeering.')
STORIES = [
('MIDDLE EAST / ENERGY','tanker','TANKERS ABLAZE IN THE STRAIT OF HORMUZ','Iran says four tankers struck naval mines in the strait; the claims are unverified, and Tehran bars talks until Washington meets its terms.'),
('EUROPE / WAR','drone',"UKRAINE'S DRONES HIT RUSSIAN SHIPS",'Kyiv strikes Russian vessels in the Gulf of Finland and off Libya, as Poland reports a new airspace violation and NATO watches.'),
('BUSINESS / TECH','chip','NVIDIA BRINGS BACK ITS BOSS','Jensen Huang is reinstated as CEO after Trump steps in — and Wall Street surges, the Nasdaq leaping 6.5%.'),
('ASIA / WORLD COURT','scales','14 NATIONS BACK ROHINGYA GENOCIDE RULING','Countries affirm the ICJ verdict that Myanmar committed genocide, as Malaysia prepares to send 6,803 Rohingya home.'),
('TURKIYE','helicopter','TURKISH HELICOPTER CRASH KILLS FIVE','An air force helicopter goes down seconds after taking off from Eskisehir on a training flight; all five crew die.'),
('LATIN AMERICA','cart','GUNMEN HOLD 25 HOSTAGE IN CARTAGENA','Armed men seize a supermarket in the Colombian city, while a car bomb destroys buildings in Villavicencio.'),
('UNITED NATIONS / AI','globe','UN CHIEF: AI RULES WITHIN A YEAR','Guterres urges governments to agree a global framework to rein in the risks of artificial intelligence.'),
('SPORT','trophy',"SENEGAL ARE AFRICA'S CHAMPIONS AGAIN","The sports court CAS restores Senegal's Cup of Nations title; in Europe, Real Madrid rout PSV 5-1."),
]


def fitted_line(c, text, x, y, width, height, nominal_sx, sy, bold=False, color=INK):
    sx = min(nominal_sx, width / text_width(text,1,bold))
    c.text(text,x,y,sx,sy,bold,color,bounds=(x,y,width,height))


def summary_block(c, text, x, y, width, nominal_sx, sy, leading):
    """Fit complete words into at most two bold, measured lines."""
    sx = nominal_sx
    lines = wrap(text,width,sx,True)
    while len(lines) > 2:
        sx -= .01
        lines = wrap(text,width,sx,True)
    bounds = (x,y,width,leading+7*sy)
    for i,line in enumerate(lines):
        c.text(line,x,y+i*leading,sx,sy,True,bounds=bounds)


def render():
    c = Canvas()
    margin, page_width = 32, 960
    # Masthead and an exceptionally prominent reverse-type date band.
    fitted_line(c,'THE WORLD IN ONE DAY',32,29,960,57,9,7.6,True)
    c.rect(32,104,960,68,RED)
    date = 'TUESDAY 24 NOVEMBER 2026'
    sx = min(5.65,912/text_width(date,1,True))
    c.text(date,512-text_width(date,sx,True)/2,120,sx,5.1,True,WHITE,
           bounds=(44,104,936,68))
    c.rect(32,187,960,3)
    # Hero has a large reserved pictogram square to the left of every text line.
    pictogram(c,'court',42,216,166)
    x, width = 237, 755
    c.text(HERO[0],x,209,1.85,1.8,True,RED,bounds=(x,204,width,20))
    lines = wrap(HERO[1],width,5.8,True)
    assert len(lines) <= 2
    for i,line in enumerate(lines):
        c.text(line,x,242+i*54,5.8,5.8,True,bounds=(x,239,width,108))
    summary_block(c,HERO[2],x,350,width,1.75,1.8,20)
    c.rect(32,395,960,4)
    # Two columns, four rows. The icon square never intersects the text zone.
    # Summaries use the full cell width below the icon and headline, with room
    # for two bold lines at 1.5 times their previous lettering height.
    row_height = 143
    for index,(tag,kind,headline,summary) in enumerate(STORIES):
        row,col = divmod(index,2)
        left,top = 32+col*496,409+row*row_height
        cell_width = 464
        pictogram(c,kind,left+6,top+23,66)
        tx,tw = left+98,cell_width-98
        bounds = (tx,top,tw,122)
        fitted_line(c,tag,tx,top+5,tw,13,1.27,1.27,True,RED)
        scale = 3.0
        lines = wrap(headline,tw,scale,True)
        while len(lines)>2:
            scale -= .05
            lines = wrap(headline,tw,scale,True)
        assert len(lines) <= 2 and scale >= 2.4
        for j,line in enumerate(lines):
            c.text(line,tx,top+31+j*30,scale,3.05,True,bounds=bounds)
        summary_block(c,summary,left,top+96,cell_width,1.8,2.025,20)
        if row < 3:
            c.rect(left,top+138,cell_width,1,INK)
    c.rect(511,410,1,560)
    c.rect(32,984,960,2)
    footer = 'Sources: Reuters - AP - France 24 - The Guardian - IRNA - UKMTO'
    sx = 1.5
    c.text(footer,512-text_width(footer,sx)/2,998,sx,1.35,
           bounds=(32,990,960,25))
    return c.rgb()


def png_bytes(rgb):
    """Encode RGB8, non-interlaced PNG with filter 0 and CRC'd chunks."""
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    scanlines = b''.join(b'\0'+rgb[y*WIDTH*3:(y+1)*WIDTH*3] for y in range(HEIGHT))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR',struct.pack('>IIBBBBB',WIDTH,HEIGHT,8,2,0,0,0))
            + chunk(b'IDAT',zlib.compress(scanlines,9)) + chunk(b'IEND',b''))


def main():
    data = png_bytes(render())
    assert len(data) <= 1024*1024, 'PNG exceeds the competition size limit'
    output_dir = Path(os.environ.get('MAKEFUN_OUTPUT_DIR', '/output'))
    output_dir.mkdir(parents=True,exist_ok=True)
    path = output_dir/'entry.png'
    path.write_bytes(data)
    print(f'{path}: {WIDTH}x{HEIGHT}, {len(data)} bytes, sha256={hashlib.sha256(data).hexdigest()}')


if __name__ == '__main__':
    main()
