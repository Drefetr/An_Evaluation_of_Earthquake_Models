# Research documents on GitHub Pages

The generated site contains the accepted 231-page S04B manuscript, the eight-page plain-language guide and an interactive explorer of accepted S03, S04 observed, S06 and matched-generator S04B results. Calibration conclusions are explained in the guide and manuscript; the explorer does not compare p-values as model-performance scores.

Build an isolated preview from the repository root. Output directories must be new:

```
python -B website/build_site.py --output build/site
node website/check_interactions.cjs build/site
```

Python and PyMuPDF are required for the build; Node.js 22 is used for interaction checks. Install Python dependencies with `python -m pip install -r requirements.txt`. The generated site needs only a browser. The default output is `build/site`; ordinary builds leave the committed bundle and source documents unchanged. `document_metadata.json` pins the actual manuscript SHA-256 and page count. Update those fields only after a revised manuscript is accepted. The builder verifies both and refuses to label the archived baseline as final. No fits, simulations or catalogue downloads run during this process.

To preview an edited companion, first run `python -B companion/build_guide.py --output build/companion`, then pass `--companion build/companion` to the site builder with a fresh site output directory. Otherwise the site uses the accepted PDF and HTML in `companion/`.

The explorer keeps study populations separate. Its five S04 procedures share the same 315 targets and fixed baseline; they are not five independent studies. Score-component displays and validation scopes follow the accepted public authorities. Exact aggregate values and source hashes can be downloaded from the site.

Preview locally with `python -m http.server 8000 --directory build/site`, then visit http://localhost:8000. The generated site also supports opening index.html directly.

For GitHub Pages, `.github/workflows/pages.yml` builds a fresh bundle from the accepted documents, exercises its interactions and deploys `build/site`. In Settings, Pages, select GitHub Actions as the source, then manually run **Publish research documents** (`workflow_dispatch`). For a separate standalone Pages repository, copy the completed bundle as a `site/` directory and `website/pages.yml` to `.github/workflows/pages.yml`; that template uploads `site/` without requiring Python sources. The workflow follows https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages .

The canonical document files are `paper/manuscript_unified.pdf` and `companion/lay_guide_to_the_research.pdf`. Files under `website/site/downloads/` are intentional generated deployment copies; `documents.json` records their hashes. The committed `website/site/` is a reviewed offline snapshot. After reviewing an isolated output, use `python -B website/build_site.py --output build/site-to-install --install` to promote a fresh bundle to that snapshot, then refresh verification receipts and the canonical payload manifest. The install step replaces only the known generated site tree. `website/findings.html` is the editable template; `website/site/findings.html` is generated from it and the accepted authorities.

S04B has a separate simulation view: histories are independent within regime and paired across procedures; means are total nats per history. Regimes are not pooled or converted to per-earthquake scores. Scientific and changed-artifact visual reviews are accepted; fresh isolated release validation supplies the final production evidence.
