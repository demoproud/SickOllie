"""Render the editable JSON manual. Requires reportlab and DejaVu Sans fonts.
Run: python docs/manual-source/render_manual.py
"""
from pathlib import Path
import json,math,html
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
ROOT=Path(__file__).resolve().parents[2]; SRC=Path(__file__).parent
FONT=Path('/usr/share/fonts/truetype/dejavu')
for n,f in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('Mono','DejaVuSansMono.ttf')]:pdfmetrics.registerFont(TTFont(n,str(FONT/f)))
W,H=720,960;M=44;CW=W-M*2
INK='#090a0f';PANEL='#151821';TEXT='#eeeef3';MUTED='#b0b5c3';COLORS=['#35d7ff','#ff4ab8','#f6e65a','#6ee7a2']
styles={k:ParagraphStyle(k,fontName=f,fontSize=size,leading=lead,textColor=HexColor(color),spaceAfter=0) for k,f,size,lead,color in [('body','Body',11.2,17.4,TEXT),('small','Body',9.4,14.2,MUTED),('card','Body',10.5,16,TEXT),('title','Bold',12.5,17,TEXT),('ref','Body',9.4,14,TEXT)]}
pages=json.loads((SRC/'manual-content.json').read_text())
refs=json.loads((SRC/'capability-reference.json').read_text()) if (SRC/'capability-reference.json').exists() else []
refchunks=[];chunk=[];height=0
for r in refs:
 a=Paragraph(html.escape(r['feature']),styles['title']);_,ah=a.wrap(CW-28,800)
 b=Paragraph(html.escape(r['behavior']),styles['ref']);_,bh=b.wrap(CW-28,800)
 rh=ah+bh+27
 if height+rh>650 and chunk:refchunks.append(chunk);chunk=[];height=0
 chunk.append(r);height+=rh
if chunk:refchunks.append(chunk)
if len(refchunks)>1 and len(refchunks[-1])<5:
    moved=refchunks[-2][-3:];refchunks[-2]=refchunks[-2][:-3];refchunks[-1]=moved+refchunks[-1]
TOTAL=3+len(pages)+len(refchunks)
out=ROOT/'docs/SICK-OLLIE-v4-User-Manual.pdf';c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1)
c.setTitle('SICK OLLIE Creator Studio + Toolkit — v4 User Manual');c.setAuthor('SICK OLLIE');c.setSubject('Workflows, creative libraries, LoRA testing and reference')
texture=ROOT/'js/assets/StudioHeaderTexture.png'
page_map={p['id']:i+4 for i,p in enumerate(pages)}
def rect(x,y,w,h,color,r=0):
 c.setFillColor(HexColor(color));c.setStrokeColor(HexColor(color));c.roundRect(x,y,w,h,r,fill=1,stroke=0) if r else c.rect(x,y,w,h,fill=1,stroke=0)
def para(txt,x,top,width,style='body'):
 p=Paragraph(html.escape(txt).replace('\n','<br/>'),styles[style]);_,h=p.wrap(width,900);p.drawOn(c,x,top-h);return h

def base(n,layer,title,deck):
 rect(0,0,W,H,INK);c.drawImage(str(texture),0,H-15,width=W,height=144,mask='auto')
 c.setFont('Bold',8);c.setFillColor(HexColor(COLORS[(n-1)%4]));c.drawString(M,H-48,'SICK OLLIE  /  CREATOR STUDIO + TOOLKIT');c.setFillColor(HexColor(MUTED));c.drawRightString(W-M,H-48,'V4.0.0')
 c.setFont('Bold',9);c.setFillColor(HexColor(COLORS[(n-1)%4]));c.drawString(M,H-90,layer.upper())
 # Title wraps only when it needs to, with bounded editorial height.
 title_style=ParagraphStyle('h',fontName='Bold',fontSize=30,leading=35,textColor=HexColor(TEXT))
 p=Paragraph(html.escape(title),title_style);_,ht=p.wrap(CW,150);p.drawOn(c,M,H-113-ht)
 dh=para(deck,M,H-126-ht,CW,'small')
 c.setStrokeColor(HexColor('#323846'));c.line(M,42,W-M,42)
 c.setFont('Body',8);c.setFillColor(HexColor(MUTED));c.drawString(M,25,'SICK OLLIE  /  USER MANUAL');c.drawRightString(W-M,25,f'{n:02d} / {TOTAL:02d}')
 return H-152-ht-dh

def draw_block(b,y,accent):
 typ=b['type']
 if typ in ['text','callout']:
  pad=15 if typ=='callout' else 0;tw=CW-pad*2
  th=Paragraph(html.escape(b['title']),styles['title']).wrap(tw,900)[1];bh=Paragraph(html.escape(b['body']),styles['body']).wrap(tw,900)[1]
  h=th+bh+11+pad*2
  if typ=='callout':rect(M,y-h,CW,h,PANEL,8);rect(M,y-h,3,h,accent)
  para(b['title'],M+pad,y-pad,tw,'title');para(b['body'],M+pad,y-pad-th-8,tw)
  return y-h-22
 if typ=='pair':
  gap=16;w=(CW-gap)/2;pad=16;heights=[]
  for title,body in [b['left'],b['right']]:heights.append(Paragraph(html.escape(title),styles['title']).wrap(w-2*pad,900)[1]+Paragraph(html.escape(body),styles['card']).wrap(w-2*pad,900)[1]+41)
  h=max(heights)
  for i,(title,body) in enumerate([b['left'],b['right']]):
   x=M+i*(w+gap);rect(x,y-h,w,h,PANEL,8);rect(x,y-3,w,3,COLORS[i]);th=para(title,x+pad,y-pad,w-pad*2,'title');para(body,x+pad,y-pad-th-9,w-pad*2,'card')
  return y-h-22
 if typ=='table':
  th=para(b['title'],M,y,CW,'title');y-=th+12
  for i,(label,body) in enumerate(b['rows']):
   lwidth=178;rwidth=CW-lwidth-44
   lh=Paragraph(html.escape(label),styles['card']).wrap(lwidth,900)[1];bh=Paragraph(html.escape(body),styles['card']).wrap(rwidth,900)[1];h=max(lh,bh)+22
   rect(M,y-h,CW,h,PANEL if i%2==0 else '#10131b',3);para(label,M+12,y-11,lwidth,'card');para(body,M+lwidth+30,y-11,rwidth,'card');y-=h+3
  return y-21
 if typ=='map':
  # Exact graph, six Core stations. Library input paths are explained by the following table.
  h=267;bw=174;bh=49;cols=[M+2,M+CW-176];yy=[y-10,y-104,y-198]
  nodes=[('Loader Core','model',cols[0],yy[0]),('Prompt Core','final_prompt',cols[1],yy[0]),('Generation Core','samples + vae',cols[0],yy[1]),('Output Core','images',cols[1],yy[1]),('Preview Core','compare + save',cols[1],yy[2]),('Image Metadata Core','reuse station',cols[0],yy[2])]
  def arrow(x1,y1,x2,y2):
   c.setStrokeColor(HexColor(MUTED));c.setLineWidth(1.1);c.line(x1,y1,x2,y2);a=math.atan2(y2-y1,x2-x1);path=c.beginPath();path.moveTo(x2,y2);path.lineTo(x2-6*math.cos(a-.5),y2-6*math.sin(a-.5));path.lineTo(x2-6*math.cos(a+.5),y2-6*math.sin(a+.5));path.close();c.setFillColor(HexColor(MUTED));c.drawPath(path,fill=1,stroke=0)
  arrow(cols[0]+bw/2,yy[0]-bh,cols[0]+bw/2,yy[1]);arrow(cols[1]+bw/2,yy[0]-bh,cols[0]+bw-5,yy[1]+5);arrow(cols[0]+bw,yy[1]-bh/2,cols[1],yy[1]-bh/2);arrow(cols[1]+bw/2,yy[1]-bh,cols[1]+bw/2,yy[2])
  for i,(title,sub,x,top) in enumerate(nodes):
   rect(x,top-bh,bw,bh,PANEL,7);rect(x,top-bh,3,bh,COLORS[i%4]);para(title,x+12,top-8,bw-24,'title');para(sub,x+12,top-29,bw-24,'small')
  return y-h-10
 if typ=='trigger-map':
  h=105;labels=['Exact LoRA override','Epoch-family override','Automatic discovery'];gap=10;w=(CW-gap*2)/3
  for i,label in enumerate(labels):
   x=M+i*(w+gap);rect(x,y-49,w,49,PANEL,7);para(str(i+1)+' / '+label,x+10,y-12,w-20,'card')
  para('First available match → resolved Main trigger → Prompt Core placement',M,y-66,CW,'title')
  return y-h-10
 raise ValueError(typ)
# Cover
rect(0,0,W,H,INK);c.drawImage(str(texture),0,415,width=W,height=420,mask='auto',preserveAspectRatio=False)
c.setFillColor(Color(0.03,0.03,0.05,alpha=.1));c.rect(0,415,W,420,fill=1,stroke=0)
c.setFont('Bold',11);c.setFillColor(HexColor(COLORS[0]));c.drawString(M,900,'THE V4 FIELD MANUAL')
c.setFont('Bold',50);c.setFillColor(HexColor(TEXT));c.drawString(M,827,'SICK OLLIE')
for i,(line,size) in enumerate([('CREATOR STUDIO',32),('+ TOOLKIT',32)]):c.setFont('Bold',size);c.drawString(M,781-i*42,line)
rect(M,433,86,29,COLORS[1],5);c.setFont('Bold',12);c.setFillColor(HexColor(INK));c.drawCentredString(M+43,442,'4.0.0')
para('MAKE IT.\nKEEP WHAT WORKS.',M,354,CW,'title')
para('A connected workflow for prompts, LoRAs, outfits and images. Start with one generation. Build a Library you want to return to.',M,296,500)
for i,label in enumerate(['CHOOSE','GENERATE','COMPARE','REUSE']):
 x=M+i*157;rect(x,147,143,43,PANEL,5);c.setFont('Bold',10);c.setFillColor(HexColor(COLORS[i]));c.drawCentredString(x+71.5,164,label)
para('WORKFLOWS FIRST  /  POWER TOOLS WHEN YOU NEED THEM',M,84,CW,'small');c.bookmarkPage('cover');c.addOutlineEntry('Cover','cover');c.showPage()
# Two useful contents pages with clickable page targets.
for n,portion in enumerate([pages[:17],pages[17:]],2):
 y=base(n,'FIND YOUR WAY','Start anywhere.','Read pages 4–6 for the core loop. Follow the full path or jump to the task at hand.')
 for p in portion:
  target=page_map[p['id']];rect(M,y-30,CW,29,PANEL if target%2 else '#10131b',3);c.setFont('Body',11);c.setFillColor(HexColor(TEXT));c.drawString(M+10,y-20,p['title']);c.setFont('Bold',11);c.setFillColor(HexColor(COLORS[target%4]));c.drawRightString(W-M-11,y-20,f'{target:02d}');c.linkRect('',p['id'],(M,y-30,W-M,y),relative=0,thickness=0);y-=34
 if n==3:
  para('CONTROL FINDER',M,y-16,CW,'title');para('The final pages provide a workflow-ordered reference to the useful controls covered in the guide.',M,y-42,CW,'small')
 c.showPage()
for n,p in enumerate(pages,4):
 c.bookmarkPage(p['id']);c.addOutlineEntry(p['title'],p['id'],0)
 y=base(n,p['layer'],p['title'],p['deck'])
 for b in p['blocks']:y=draw_block(b,y,COLORS[(n-1)%4])
 if y<54:raise RuntimeError(f"Page overflow: {p['id']} ends at {y:.1f}")
 c.showPage()
for i,chunk in enumerate(refchunks,4+len(pages)):
 c.bookmarkPage('reference'+str(i));c.addOutlineEntry('Control finder '+str(i-(3+len(pages))),'reference'+str(i),0)
 y=base(i,'CONTROL FINDER','Every useful control','Quick reference. The page number leads back to the relevant workflow.')
 for r in chunk:
  title=r['feature']+'  /  p. '+str(page_map[r['manual_section']]);body=r['behavior'];tw=CW-28
  ah=Paragraph(html.escape(title),styles['title']).wrap(tw,900)[1];bh=Paragraph(html.escape(body),styles['ref']).wrap(tw,900)[1];rh=ah+bh+27
  if y-rh<54:raise RuntimeError(f'Reference overflow {i}')
  rect(M,y-rh,CW,rh-5,PANEL,5);c.linkRect('',r['manual_section'],(M,y-rh,W-M,y),relative=0,thickness=0);para(title,M+12,y-9,tw,'title');para(body,M+12,y-ah-14,tw,'ref');y-=rh
  r['reference_page']=i
 c.showPage()
c.save()
# Editable Markdown has full editorial text and the same precise control descriptions.
md=['# SICK OLLIE Creator Studio + Toolkit v4.0.0 User Manual\n','Choose → Load → Generate → Compare → Save → Reuse.\n']
for p in pages:
 md += [f'<a id="{p["id"]}"></a>',f'## {p["title"]}',f'PDF page {page_map[p["id"]]} · {p["layer"]}\n',p['deck']+'\n']
 for b in p['blocks']:
  if b['type'] in ['text','callout']:md += ['### '+b['title']+'\n',b['body']+'\n']
  elif b['type']=='pair':md += ['| '+b['left'][0]+' | '+b['right'][0]+' |','|---|---|','| '+b['left'][1]+' | '+b['right'][1]+' |\n']
  elif b['type']=='table':md+=['### '+b['title']+'\n','| Control / choice | Behavior |','|---|---|']+['| '+a+' | '+z+' |' for a,z in b['rows']]+['']
  elif b['type']=='map':md+=['```mermaid','flowchart TD',' L["Loader Core"] -->|model| G["Generation Core"]',' P["Prompt Core"] -->|final_prompt| G',' G -->|samples + vae| O["Output Core"]',' O -->|images| V["Preview Core"]',' M["Image Metadata Core"] -.->|prompt text| P',' M -.->|seed| G','```\n']
  elif b['type']=='trigger-map':md+=['Exact LoRA override → matching epoch-family override → automatic discovery. The first available result supplies Main trigger; Prompt Core then applies its chosen placement.\n']
md+=['## Control finder\n']
for r in refs:md += [f"### {r['feature']}\n",r['behavior']+f" Workflow: [{r['manual_section']}](#{r['manual_section']}); PDF reference page {r.get('reference_page','')}.\n"]
(ROOT/'docs/USER_MANUAL.md').write_text('\n'.join(md))
(SRC/'page-map.json').write_text(json.dumps(page_map,indent=2));(SRC/'capability-reference.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2))
print(out);print(TOTAL,'pages')
