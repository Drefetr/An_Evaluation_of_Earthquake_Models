"""Build an allowlisted, dependency-free GitHub Pages bundle from reviewed documents."""
from pathlib import Path
import hashlib
import html
import json
import shutil
import argparse
import tempfile
import pymupdf
from build_findings import build as build_findings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'site'
def document_contract(config):
    state=config['status']
    if state not in ['draft','published_research']:raise ValueError('explicit document status required')
    d=config['document'];source=(ROOT/d['source']).resolve()
    source.relative_to(ROOT.resolve())
    if not isinstance(d['pages'],int) or d['pages']<=0:raise ValueError('positive actual page count required')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=d['sha256']:raise ValueError('document hash mismatch')
    with pymupdf.open(source) as pdf:
        if len(pdf)!=d['pages']:raise ValueError('document page count mismatch')
    if state=='published_research':
        if d['sha256']=='a84d3030497459b0b442b1dfa328294e4066089f49a62e2cb49981742a0184e6':raise ValueError('baseline cannot be labelled final')
        if config.get('production_checked') is not True:raise ValueError('production checks required')
        filename='final-monograph.pdf';label='Current research monograph'
    else:filename='candidate-monograph.pdf';label='Research manuscript draft'
    return source,filename,label

def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata',type=Path,default=ROOT/'website/document_metadata.json')
    parser.add_argument('--output',type=Path,default=OUT,help='Fresh output directory (default: build/site)')
    parser.add_argument('--companion',type=Path,default=ROOT/'companion',help='Guide PDF/HTML/content directory; defaults to the accepted companion/')
    parser.add_argument('--install',action='store_true',help='Install a repository preview in website/site/ linking canonical PDFs without duplicate downloads. Requires review and manifest refresh.')
    a=parser.parse_args()
    config=json.loads(a.metadata.read_text(encoding='utf-8'));baseline,filename,label=document_contract(config)
    target=a.output.resolve()
    if target==ROOT.resolve() or target==baseline.parent:raise ValueError('unsafe output directory')
    if target.exists():raise FileExistsError('output must be fresh')
    target.parent.mkdir(parents=True,exist_ok=True)
    OUT=Path(tempfile.mkdtemp(prefix='site-build-',dir=target.parent))
    companion = a.companion.resolve()
    data = json.loads((ROOT/'companion/guide_content.json').read_text(encoding='utf-8'))
    OUT.mkdir(parents=True, exist_ok=True)
    downloads = OUT / 'downloads'
    downloads.mkdir(exist_ok=True)
    shutil.copyfile(companion / 'lay_guide_to_the_research.pdf', downloads / 'research-guide.pdf')
    shutil.copyfile(baseline, downloads / filename)
    css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2f6f6;color:#26343d;font:18px/1.65 system-ui,sans-serif}a{color:#166c72;text-underline-offset:3px}a:focus-visible{outline:3px solid #b76628;outline-offset:4px}.skip{position:absolute;left:-10000px}.skip:focus{left:12px;top:12px;background:white;padding:12px;z-index:10}.site-nav{display:flex;flex-wrap:wrap;gap:24px;padding:18px max(24px,calc((100% - 960px)/2));background:#183449;color:white}.site-nav a{color:white}.wrap{max-width:960px;margin:auto;padding:50px 24px}h1{font-size:clamp(2rem,5vw,3.4rem);line-height:1.13;color:#183449;max-width:780px}h2{color:#183449;line-height:1.3}.eyebrow{color:#166c72;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:.8rem}.intro{font-size:1.2rem;max-width:730px}.notice{border-left:4px solid #b76628;background:#fff6e9;padding:18px 24px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin:32px 0}.card{background:white;padding:28px;border:1px solid #d6e1e3;border-radius:8px}.button{display:inline-block;background:#166c72;color:white;padding:10px 18px;border-radius:4px;text-decoration:none}footer{border-top:1px solid #cdd9de;margin-top:40px;padding-top:20px;font-size:.9rem}.contents{max-width:850px;margin:24px auto;background:white;padding:24px 30px}.contents ol{columns:2;column-gap:30px}.contents li{break-inside:avoid;margin-bottom:8px}@media(max-width:600px){.contents ol{columns:1}.wrap{padding-top:25px}}@media print{.site-nav,.skip,.contents{display:none}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'''
    (OUT / 'site.css').write_text(css, encoding='utf-8')
    nav = '<a class="skip" href="#main">Skip to content</a><nav class="site-nav" aria-label="Main"><a href="index.html">Research home</a><a href="guide.html">Read the guide</a><a href="findings.html">Explore findings</a><a href="index.html#documents">Documents</a></nav>'
    esc = html.escape
    toc = '<nav class="contents" aria-label="Guide sections"><strong>In this guide</strong><ol>' + ''.join(f'<li><a href="#page-{i}">{esc(p["title"])}</a></li>' for i,p in enumerate(data['pages'],1)) + '</ol><a href="downloads/research-guide.pdf">Download the guide as a PDF</a></nav>'
    guide = (companion / 'lay_guide_to_the_research.html').read_text(encoding='utf-8')
    guide = guide.replace('</head>', '<link rel="stylesheet" href="site.css"></head>').replace('<body>', '<body>'+nav+toc).replace('<main>', '<main id="main">')
    (OUT / 'guide.html').write_text(guide, encoding='utf-8')
    landing = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="A plain-language companion and reviewed manuscript on earthquake triggering, inhibition and forecasting."><title>Earthquake modelling  -  Research and documents</title><link rel="stylesheet" href="site.css"></head><body>{nav}<main id="main" class="wrap"><p class="eyebrow">Research companion</p><h1>Understanding the earthquake research</h1><p class="intro">How can we tell whether an earthquake encourages or discourages later activity - and whether modelling that distinction improves forecasts?</p><p>This collection explains the research in everyday language and provides the mathematical manuscript for readers who want the details.</p><div class="notice"><strong>{esc(config['collection_label'])}</strong><p>{esc(data['status'])}</p></div><div class="cards" id="documents"><article class="card"><h2>Start with the guide</h2><p>Eight illustrated sections cover the question, models, evidence and limitations. No equations are needed.</p><p><a class="button" href="guide.html">Read online</a></p><p><a href="downloads/research-guide.pdf">Download the eight-page PDF</a></p><small>{esc(data['edition'])}</small></article><article class="card"><h2>{esc(label)}</h2><p>{config['document']['pages']}-page document.</p><p><a class="button" href="downloads/{filename}">Read the manuscript PDF</a></p><p>{esc(config['document_note'])}</p></article></div><h2>What the evidence means</h2><p>The guide distinguishes mathematical validity, what can be learned from data, and performance on later observations. A good fit to past earthquakes does not by itself establish better forecasts.</p><h2>The revised release</h2><p>{esc(config['release_note'])}</p><p><a href="https://github.com/Drefetr/An_Evaluation_of_Earthquake_Models/tree/main/reproduction">Open the data and replay instructions</a></p><footer>Research comparisons using historical catalogues and simulations. This project has not established an operational earthquake forecasting service.<p><a href="documents.json">Document versions and SHA-256 checksums</a></p></footer></main></body></html>'''
    (OUT / 'index.html').write_text(landing, encoding='utf-8')
    (OUT / '.nojekyll').write_text('')
    inputs = {filename:baseline,'research-guide.pdf':companion/'lay_guide_to_the_research.pdf'}
    records = []
    for p in sorted(downloads.glob('*.pdf')):
        source=inputs[p.name].resolve()
        repository_source=source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else None
        records.append({'path':p.relative_to(OUT).as_posix(),'repository_source':repository_source,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    (OUT / 'documents.json').write_text(json.dumps({'edition':data['edition'],'status':config['status'],'bundle_kind':'self_contained_deployment','baseline_is_revised_release':False,'document_kind':('research_edition' if config['status']=='published_research' else 'draft'),'manuscript_pages':config['document']['pages'],'documents':records},indent=2)+'\n',encoding='utf-8')
    build_findings(OUT)
    OUT.rename(target)
    if a.install:
        install_bundle(target)
    print(target)

def install_bundle(source):
    """Promote a repository preview that shares the canonical repository PDFs."""
    website=(ROOT/'website').resolve();destination=website/'site'
    old=website/'site.previous-build';new=website/'site.next-build'
    if old.exists() or new.exists():raise FileExistsError('previous site promotion directories must be reviewed before installing')
    # All removal/rename targets are fixed children of website/, never user output.
    for path in [destination,old,new]:
        if path.resolve().parent!=website:raise ValueError('unsafe site promotion path')
    new.mkdir()  # establish this invocation's ownership before any partial copy
    try:
        shutil.copytree(source,new,dirs_exist_ok=True)
        make_repository_preview(new)
    except BaseException:
        if new.resolve().parent!=website:raise ValueError('unsafe site staging cleanup path')
        shutil.rmtree(new)
        raise
    if destination.exists():destination.rename(old)
    try:new.rename(destination)
    except BaseException:
        if old.exists():old.rename(destination)
        raise
    if old.exists():shutil.rmtree(old)

def make_repository_preview(bundle):
    """Retarget PDF links and metadata without changing scientific HTML prose."""
    metadata_path=bundle/'documents.json'
    metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
    replacements={}
    for record in metadata['documents']:
        source_name=record.get('repository_source')
        if not source_name:
            raise ValueError('Install canonical PDF sources in paper/ or companion/ before installing the repository preview')
        source=(ROOT/source_name).resolve()
        relative=source.relative_to(ROOT.resolve())
        if relative.parts[0] not in {'paper','companion'} or not source.is_file():
            raise ValueError('Repository preview PDFs must use canonical paper/ or companion/ sources')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Repository preview canonical PDF identity differs')
        old_path=record['path'];download=(bundle/old_path).resolve()
        if download.parent!=(bundle/'downloads').resolve():raise ValueError('Unexpected deployment PDF path')
        preview_path=(Path('../..')/relative).as_posix()
        replacements[old_path]=preview_path;record['path']=preview_path
        download.unlink()
    downloads=bundle/'downloads'
    if downloads.exists():downloads.rmdir()  # refuse unexpected undeclared downloads
    for page in bundle.rglob('*.html'):
        text=page.read_text(encoding='utf-8')
        for old_path,new_path in replacements.items():
            text=text.replace('href="'+old_path+'"','href="'+new_path+'"')
        page.write_text(text,encoding='utf-8')
    metadata['bundle_kind']='repository_preview'
    metadata_path.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')

if __name__ == '__main__':
    main()
