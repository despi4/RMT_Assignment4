"""Create the three vector plots used in the paper from audited summary.json.

Optional formatting dependency: reportlab==4.4.9. Numerical analysis itself
continues to require only the standard library. No inference or data changes.
"""
from pathlib import Path
import argparse,json
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

ROOT=Path(__file__).resolve().parents[1]
LABELS={'clean':'Clean','irrelevant_4':'Unrelated 4','similar_4':'Similar 4',
        'irrelevant_16':'Unrelated 16','similar_16':'Similar 16'}

def chart(path,labels,values,intervals=None):
    width,height=490,92+42*len(labels)
    c=canvas.Canvas(str(path),pagesize=(width,height),invariant=1)
    c.setTitle(path.stem);c.setFont('Helvetica',18)
    for tick in [0,25,50,75,100]:
        x=122+tick*3.05;c.setStrokeColor(HexColor('#dddddd'));c.line(x,40,x,height-20)
        c.setFillColor(HexColor('#111111'));c.drawCentredString(x,24,str(tick)+'%')
    for i,(label,value) in enumerate(zip(labels,values)):
        y=height-50-i*42;c.setFillColor(HexColor('#111111'));c.drawRightString(115,y+7,label)
        c.setFillColor(HexColor('#306a91'));c.rect(122,y,value*3.05,24,fill=1,stroke=0)
        if intervals:
            low,high=intervals[i];c.setStrokeColor(HexColor('#111111'));c.setLineWidth(1.2)
            c.line(122+low*3.05,y+12,122+high*3.05,y+12)
            for endpoint in [low,high]:c.line(122+endpoint*3.05,y+7,122+endpoint*3.05,y+17)
        c.setFillColor(HexColor('#111111'))
        c.drawString(128+(intervals[i][1] if intervals else value)*3.05,y+5,f'{value:.2f}')
    c.save()

def render(summary_path,out):
    data=json.loads(Path(summary_path).read_text(encoding='utf8'));out=Path(out);out.mkdir(parents=True,exist_ok=True)
    supported=[r for r in data['tables'] if r['condition'] in LABELS]
    chart(out/'accuracy.pdf',[LABELS[r['condition']] for r in supported],
          [r['accuracy_pct'] for r in supported],[(r['ci_low'],r['ci_high']) for r in supported])
    chart(out/'position.pdf',[r['position'].capitalize() for r in data['positions']],
          [r['accuracy_pct'] for r in data['positions']])
    by_condition={r['condition']:r for r in data['tables']}
    chart(out/'abstention.pdf',['No context','16 distractors'],
          [by_condition[k]['expected_pct'] for k in ['closed_book','target_absent_16']])
    return [out/(name+'.pdf') for name in ['accuracy','position','abstention']]

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary',type=Path,default=ROOT/'results/final_paper/summary.json')
    p.add_argument('--out',type=Path,default=ROOT/'results/paper_figures')
    a=p.parse_args()
    for path in render(a.summary,a.out):print(path)
