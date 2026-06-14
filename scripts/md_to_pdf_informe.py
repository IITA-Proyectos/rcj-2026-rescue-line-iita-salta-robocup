# -*- coding: utf-8 -*-
"""Renderizador markdown -> PDF para el informe del coach. reportlab Platypus.
Una sola fuente de verdad (el .md); este script lo formatea en PDF de 7 páginas."""
import re, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, HRFlowable, KeepInFrame)

SRC = sys.argv[1]
OUT = sys.argv[2]

# Paleta
NAVY   = colors.HexColor("#15314f")
BLUE   = colors.HexColor("#1f4e79")
ACCENT = colors.HexColor("#c0392b")
GREY   = colors.HexColor("#555555")
LIGHT  = colors.HexColor("#eef2f6")
RULE   = colors.HexColor("#cbd5e0")

styles = {
 'h1': ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=17, leading=20,
                      textColor=NAVY, spaceAfter=2, alignment=TA_LEFT),
 'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11.5, leading=14,
                      textColor=BLUE, spaceAfter=8),
 'h3': ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=12.5, leading=15,
                      textColor=colors.white, backColor=NAVY, borderPadding=(5,6,5,6),
                      spaceBefore=6, spaceAfter=8, leftIndent=0),
 'h4': ParagraphStyle('h4', fontName='Helvetica-Bold', fontSize=10, leading=13,
                      textColor=ACCENT, spaceBefore=6, spaceAfter=3),
 'body': ParagraphStyle('body', fontName='Helvetica', fontSize=8.7, leading=11.6,
                        alignment=TA_JUSTIFY, spaceAfter=4, textColor=colors.HexColor("#1a1a1a")),
 'bullet': ParagraphStyle('bullet', fontName='Helvetica', fontSize=8.7, leading=11.4,
                          leftIndent=12, bulletIndent=2, spaceAfter=1.5, alignment=TA_LEFT,
                          textColor=colors.HexColor("#1a1a1a")),
 'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8.0, leading=9.8),
 'cellh': ParagraphStyle('cellh', fontName='Helvetica-Bold', fontSize=8.0, leading=9.8,
                         textColor=colors.white),
 'quote': ParagraphStyle('quote', fontName='Helvetica', fontSize=9.2, leading=13,
                         textColor=colors.HexColor("#5a1a12"), alignment=TA_JUSTIFY),
 'foot': ParagraphStyle('foot', fontName='Helvetica', fontSize=7, textColor=GREY),
}

def inline(s):
    s = s.replace('→','->').replace('≥','>=').replace('≤','<=').replace('±','+/-')
    s = s.replace('🟢','§G§').replace('🟡','§Y§').replace('🔴','§R§')
    s = s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    s = s.replace('§G§','<font color="#1a7f37"><b>&bull;</b></font>')
    s = s.replace('§Y§','<font color="#c08400"><b>&bull;</b></font>')
    s = s.replace('§R§','<font color="#cf222e"><b>&bull;</b></font>')
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'`(.+?)`', r'<font face="Courier" size="8">\1</font>', s)
    s = re.sub(r'\*(.+?)\*', r'<i>\1</i>', s)
    return s

lines = open(SRC, encoding='utf-8').read().split('\n')
story = []
i = 0
para_buf = []
USABLE = A4[0] - 3.0*cm

def flush_para():
    global para_buf
    if para_buf:
        txt = ' '.join(para_buf).strip()
        if txt:
            story.append(Paragraph(inline(txt), styles['body']))
        para_buf = []

def is_sep(row):
    return all(re.match(r'^\s*:?-{2,}:?\s*$', c) for c in row if c.strip()!='') and any('-' in c for c in row)

while i < len(lines):
    ln = lines[i]
    s = ln.strip()
    # page break / comments
    if s == '<!-- PAGEBREAK -->':
        flush_para(); story.append(PageBreak()); i+=1; continue
    if s.startswith('<!--'):
        i+=1; continue
    # blank
    if s == '':
        flush_para(); i+=1; continue
    # hr
    if s == '---':
        flush_para(); story.append(Spacer(1,3))
        story.append(HRFlowable(width='100%', thickness=0.6, color=RULE, spaceAfter=4)); i+=1; continue
    # headings
    m = re.match(r'^(#{1,4})\s+(.*)', s)
    if m:
        flush_para()
        lvl = len(m.group(1)); txt = m.group(2)
        key = {1:'h1',2:'h2',3:'h3',4:'h4'}[lvl]
        if lvl==3: story.append(Spacer(1,2))
        story.append(Paragraph(inline(txt), styles[key]))
        i+=1; continue
    # blockquote (collect consecutive >)
    if s.startswith('>'):
        flush_para()
        qbuf=[]
        while i < len(lines) and lines[i].strip().startswith('>'):
            qbuf.append(re.sub(r'^\s*>\s?','',lines[i]).rstrip()); i+=1
        qtext = ' '.join(x for x in qbuf if x!='')
        p = Paragraph(inline(qtext), styles['quote'])
        t = Table([[p]], colWidths=[USABLE])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),colors.HexColor("#fdecea")),
            ('LINEBEFORE',(0,0),(0,-1),3,ACCENT),
            ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ]))
        story.append(t); story.append(Spacer(1,5)); continue
    # table (collect consecutive |...| )
    if s.startswith('|'):
        flush_para()
        rows=[]
        while i < len(lines) and lines[i].strip().startswith('|'):
            cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
            rows.append(cells); i+=1
        if not rows: continue
        # separate header/separator
        header=rows[0]; body=rows[1:]
        if len(rows)>=2 and is_sep(rows[1]):
            body=rows[2:]
        ncol=len(header)
        # column widths by content length
        w=[1]*ncol
        for r in [header]+body:
            for j in range(ncol):
                if j<len(r): w[j]=max(w[j], min(len(r[j]),60))
        tot=sum(w); colw=[max(USABLE*0.07, USABLE*x/tot) for x in w]
        # renormalize
        f=USABLE/sum(colw); colw=[x*f for x in colw]
        data=[]
        data.append([Paragraph(inline(c), styles['cellh']) for c in header])
        for r in body:
            r=(r+['']*ncol)[:ncol]
            data.append([Paragraph(inline(c), styles['cell']) for c in r])
        t=Table(data, colWidths=colw, repeatRows=1)
        ts=[('BACKGROUND',(0,0),(-1,0),NAVY),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ('LINEBELOW',(0,0),(-1,-1),0.4,RULE),
            ('LINEAFTER',(0,0),(-2,-1),0.4,RULE),
            ('BOX',(0,0),(-1,-1),0.6,NAVY)]
        for r in range(1,len(data)):
            if r%2==0: ts.append(('BACKGROUND',(0,r),(-1,r),LIGHT))
        t.setStyle(TableStyle(ts))
        story.append(t); story.append(Spacer(1,6)); continue
    # list items (collect consecutive)
    if re.match(r'^([-*]|\d+\.)\s+', s):
        flush_para()
        while i < len(lines) and re.match(r'^([-*]|\d+\.)\s+', lines[i].strip()):
            it=lines[i].strip()
            mnum=re.match(r'^(\d+)\.\s+(.*)', it)
            if mnum:
                bullet=f"<b>{mnum.group(1)}.</b>"; txt=mnum.group(2)
            else:
                txt=re.sub(r'^[-*]\s+','',it)
                txt=re.sub(r'^\[ \]\s*','',txt)
                bullet="&bull;"
            story.append(Paragraph(inline(txt), styles['bullet'], bulletText=None))
            # prepend bullet manually via leftIndent + bullet glyph
            story[-1]=Paragraph(f'<font color="#1f4e79">{bullet}</font>&nbsp; '+inline(txt), styles['bullet'])
            i+=1
        story.append(Spacer(1,3)); continue
    # default: paragraph buffer
    para_buf.append(s); i+=1

flush_para()

def deco(canvas, doc):
    canvas.saveState()
    # footer rule + text
    canvas.setStrokeColor(RULE); canvas.setLineWidth(0.5)
    canvas.line(1.5*cm, 1.25*cm, A4[0]-1.5*cm, 1.25*cm)
    canvas.setFont('Helvetica', 7); canvas.setFillColor(GREY)
    canvas.drawString(1.5*cm, 0.95*cm, "IITA Salta — RCJ Rescue Line 2026 — Informe del Director para el Coach — CONFIDENCIAL")
    canvas.drawRightString(A4[0]-1.5*cm, 0.95*cm, "Pag. %d / 7" % doc.page)
    canvas.restoreState()

doc = SimpleDocTemplate(OUT, pagesize=A4,
    leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.4*cm, bottomMargin=1.6*cm,
    title="Informe del Director para el Coach - RCJ 2026 IITA Salta",
    author="Gustavo Viollaz (Director)")
doc.build(story, onFirstPage=deco, onLaterPages=deco)
print("PDF OK:", OUT, "| flowables:", len(story))
