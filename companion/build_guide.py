"""Build the plain-language PDF and HTML from editable JSON; no experiments."""
from pathlib import Path
import argparse, html, json, math, shutil
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String, Line, PolyLine, Path as VPath
from reportlab.graphics import renderSVG

ROOT=Path(__file__).resolve().parent
NAVY=colors.HexColor('#183449'); TEAL=colors.HexColor('#166C72')
INK=colors.HexColor('#26343D'); MUTED=colors.HexColor('#54636D')
PALE=colors.HexColor('#EDF5F4'); LINE=colors.HexColor('#CDD9DE')
AMBER=colors.HexColor('#986027'); WIDTH=A4[0]-108

def fonts():
    base=Path(reportlab.__file__).resolve().parent/'fonts'
    for name,file in [('Guide','Vera.ttf'),('GuideBold','VeraBd.ttf'),('GuideItalic','VeraIt.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(base/file)))
    pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='GuideBold',italic='GuideItalic',boldItalic='GuideBold')

def text(d,x,y,value,size=10,color=INK,font='Guide'):
    d.add(String(x,y,value,fontName=font,fontSize=size,fillColor=color))

def arrow(d,x1,y,x2,color=TEAL):
    d.add(Line(x1,y,x2,y,strokeColor=color,strokeWidth=1.3))
    d.add(PolyLine([x2-5,y+3,x2,y,x2-5,y-3],strokeColor=color,strokeWidth=1.3,fillColor=None))

def diagram(name):
    if name=='ingredients':
        d=Drawing(WIDTH,112); gap=10; w=(WIDTH-2*gap)/3
        cards=[('Background','Activity not assigned','to earlier recorded events'),('Triggering','Earlier events raise','the modelled rate'),('Inhibition','A proposed reduction','in part of the rate')]
        for i,(title,a,b) in enumerate(cards):
            x=i*(w+gap);d.add(Rect(x,23,w,80,rx=5,ry=5,fillColor=PALE,strokeColor=LINE,strokeWidth=.6))
            text(d,x+11,82,title,12,TEAL,'GuideBold');text(d,x+11,59,a,9);text(d,x+11,44,b,9)
        text(d,0,6,'Different models combine these ingredients in different ways.',9,MUTED)
    elif name=='memory':
        d=Drawing(WIDTH,132); x=27;y=26;right=WIDTH-15
        d.add(Line(x,y,right,y,strokeColor=LINE));d.add(Line(x,y,x,114,strokeColor=LINE))
        p=VPath(strokeColor=TEAL,strokeWidth=2.4,fillColor=None);p.moveTo(x,105);p.curveTo(x+28,33,x+55,29,right,27);d.add(p)
        p=VPath(strokeColor=AMBER,strokeWidth=2.4,fillColor=None);p.moveTo(x,105);p.curveTo(x+120,89,x+230,46,right,35);d.add(p)
        text(d,165,105,'Longer persistence',10,AMBER);text(d,103,40,'Faster fading',10,TEAL)
        text(d,0,119,'Influence',9,MUTED);text(d,right-109,9,'Time since the event',9,MUTED)
        text(d,0,-5,'Schematic only. These are not fitted curves or earthquake observations.',8.6,MUTED)
    else:
        d=Drawing(WIDTH,89);mid=WIDTH*.51
        d.add(Rect(0,27,mid-17,40,rx=4,ry=4,fillColor=PALE,strokeColor=None))
        d.add(Rect(mid+17,27,WIDTH-mid-17,40,rx=4,ry=4,fillColor=colors.HexColor('#F3EEE7'),strokeColor=None))
        text(d,13,50,'Earlier observations',10,TEAL,'GuideBold');text(d,13,35,'Used to fit the model',9,INK)
        text(d,mid+30,50,'Later observations',10,AMBER,'GuideBold');text(d,mid+30,35,'Used to score the forecast',9,INK)
        arrow(d,mid-12,47,mid+12);text(d,mid-17,74,'Origin',9,MUTED)
        text(d,0,7,'Illustrative split. Window lengths and study designs vary.',8.6,MUTED)
    return d

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT.parent/'build/companion',help='Fresh output directory (default: build/companion)')
    parser.add_argument('--install',action='store_true',help='Also install the successfully built PDF/HTML in companion/. Requires review and manifest refresh.')
    a=parser.parse_args();a.output=a.output.resolve()
    if a.output.is_relative_to(ROOT) or ROOT.is_relative_to(a.output):
        parser.error('output must be a fresh directory outside companion/')
    data=json.loads((ROOT/'guide_content.json').read_text(encoding='utf-8'));a.output.mkdir(parents=True,exist_ok=False);fonts()
    styles={
      'body':ParagraphStyle('body',fontName='Guide',fontSize=10.5,leading=15,textColor=INK,spaceAfter=8),
      'lead':ParagraphStyle('lead',fontName='Guide',fontSize=12.2,leading=17.3,textColor=NAVY,spaceAfter=11),
      'h1':ParagraphStyle('h1',fontName='GuideBold',fontSize=22,leading=27,textColor=NAVY,spaceAfter=13),
      'h2':ParagraphStyle('h2',fontName='GuideBold',fontSize=12.2,leading=16,textColor=TEAL,spaceBefore=7,spaceAfter=5,keepWithNext=True),
      'title':ParagraphStyle('title',fontName='GuideBold',fontSize=26,leading=31,textColor=NAVY,spaceAfter=9),
      'subtitle':ParagraphStyle('subtitle',fontName='Guide',fontSize=12.2,leading=17,textColor=MUTED,spaceAfter=9),
      'kicker':ParagraphStyle('kicker',fontName='GuideBold',fontSize=9,leading=12,textColor=TEAL,spaceAfter=9),
      'note':ParagraphStyle('note',fontName='Guide',fontSize=9,leading=12.5,textColor=MUTED,spaceBefore=5,spaceAfter=9),
      'cell':ParagraphStyle('cell',fontName='Guide',fontSize=9.7,leading=13.6,textColor=INK),
      'footer':ParagraphStyle('footer',fontName='Guide',fontSize=8.1,leading=10.5,textColor=MUTED),
    }
    P=lambda value,style='body':Paragraph(html.escape(value),styles[style])
    story=[];html_pages=[]
    for index,page in enumerate(data['pages']):
        if index:story.append(PageBreak())
        web=[]
        if index==0:
            story.extend([P(data['title'],'title'),P(data['subtitle'],'subtitle'),P(data['edition'],'kicker'),P(data['status'],'note'),Spacer(1,3)])
            web.extend([f'<h1>{html.escape(data["title"])}</h1>',f'<p class="subtitle">{html.escape(data["subtitle"])}</p>',f'<p class="edition">{html.escape(data["edition"])}</p>',f'<p class="status">{html.escape(data["status"])}</p>',f'<h2>{html.escape(page["title"])}</h2>'])
        else:
            story.extend([P(page['kicker'],'kicker'),P(page['title'],'h1')]);web.append(f'<p class="edition">{html.escape(page["kicker"])}</p><h2>{html.escape(page["title"])}</h2>')
        for b in page['blocks']:
            kind=b['type']
            if kind in ['p','lead','note','h2']:
                style={'p':'body','lead':'lead','note':'note','h2':'h2'}[kind];story.append(P(b['text'],style));tag='h3' if kind=='h2' else 'p';web.append(f'<{tag} class="{kind}">{html.escape(b["text"])}</{tag}>')
            elif kind=='callout':
                content=[P(b['title'],'h2'),P(b['text'])];t=Table([[content]],colWidths=[WIDTH]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.6,LINE),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.extend([Spacer(1,4),t,Spacer(1,10)]);web.append(f'<aside><h3>{html.escape(b["title"])}</h3><p>{html.escape(b["text"])}</p></aside>')
            elif kind=='diagram':
                d=diagram(b['name']);story.extend([d,Spacer(1,13)]);svg=renderSVG.drawToString(d);svg=svg[svg.find('<svg'):];svg=svg.replace('font-family: GuideBold','font-family: sans-serif').replace('font-family: Guide','font-family: sans-serif');web.append(f'<figure role="img" aria-label="{html.escape(b["alt"],quote=True)}">{svg}<figcaption>{html.escape(b["alt"])}</figcaption></figure>')
            else:
                rows=[[Paragraph('<b>'+html.escape(x)+'</b>',styles['cell']),P(y,'cell')] for x,y in b['rows']];widths=[121,WIDTH-121] if kind=='glossary' else [WIDTH-116,116];t=Table(rows,colWidths=widths,hAlign='LEFT');t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.4,LINE)]));story.extend([t,Spacer(1,8)]);web.append('<table>'+''.join('<tr><th scope="row">'+html.escape(x)+'</th><td>'+html.escape(y)+'</td></tr>' for x,y in b['rows'])+'</table>')
        web.append('<p class="source">'+html.escape(page['source'])+'</p>');html_pages.append('<section id="page-'+str(index+1)+'">'+''.join(web)+'</section>')
    def decoration(canvas,doc):
        canvas.saveState();canvas.setTitle(data['title']);canvas.setAuthor('Research companion to the open research monograph');canvas.setSubject(data['subtitle']);canvas.setFont('GuideBold',8.1);canvas.setFillColor(TEAL);canvas.drawString(54,A4[1]-25,'EARTHQUAKE MODELLING  /  PLAIN LANGUAGE COMPANION');canvas.setStrokeColor(LINE);canvas.setLineWidth(.5);canvas.line(54,A4[1]-34,A4[0]-54,A4[1]-34)
        if doc.page<=len(data['pages']):
            p=P(data['pages'][doc.page-1]['source'],'footer');_,height=p.wrap(WIDTH-22,38);p.drawOn(canvas,54,30)
        canvas.setFont('Guide',8.1);canvas.setFillColor(MUTED);canvas.drawString(54,16,data['edition']);canvas.drawRightString(A4[0]-54,16,str(doc.page));canvas.restoreState()
    pdf=a.output/'lay_guide_to_the_research.pdf';doc=SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=54,rightMargin=54,topMargin=52,bottomMargin=62,title=data['title'],author='Research companion to the open research monograph');doc.build(story,onFirstPage=decoration,onLaterPages=decoration)
    css='''body{font:17px/1.65 system-ui,Arial,sans-serif;color:#26343d;background:#e8eff1;margin:0}main{max-width:850px;margin:auto}section{background:white;margin:25px 0;padding:45px 55px;box-shadow:0 2px 8px #18344912}h1{font-size:2.2rem;line-height:1.15;color:#183449}h2{font-size:1.8rem;line-height:1.3;color:#183449}h3{font-size:1.12rem;color:#166c72;margin-bottom:.3em}.lead{font-size:1.2rem;color:#183449}.edition,.source,.note,.status,figcaption{font-size:.86rem;color:#54636d}.edition{font-weight:bold;color:#166c72}.status,aside{background:#edf5f4;padding:15px 20px}aside p{margin-bottom:0}table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{padding:10px 14px 10px 0;text-align:left;vertical-align:top;border-bottom:1px solid #cdd9de}th{width:28%}svg{width:100%;height:auto}figure{margin:20px 0}.source{border-top:1px solid #cdd9de;padding-top:12px}a{color:#166c72}@media(max-width:600px){section{padding:25px}h1{font-size:1.9rem}}@media print{body{background:white;font-size:11pt}section{box-shadow:none;margin:0;padding:0;break-after:page}main{max-width:none}}'''
    document='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(data['title'])+'</title><style>'+css+'</style></head><body><main>'+''.join(html_pages)+'</main></body></html>'
    (a.output/'lay_guide_to_the_research.html').write_text(document,encoding='utf-8')
    if a.install:
        for filename in ['lay_guide_to_the_research.pdf','lay_guide_to_the_research.html']:
            shutil.copyfile(a.output/filename,ROOT/filename)
    print(pdf)

if __name__=='__main__':main()
