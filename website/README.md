# Research documents on GitHub Pages

The generated site contains the accepted 231-page S04B manuscript, the eight-page plain-language guide and an interactive explorer of accepted S03, S04 observed, S06 and matched-generator S04B results. Calibration conclusions are explained in the guide and manuscript; the explorer does not compare p-values as model-performance scores.

Rebuild from the release directory:

```
python -B website/build_site.py
node website/check_interactions.cjs
```

Python and PyMuPDF are required for the build; the generated site needs only a browser. Rebuild the companion first if its content changes. `document_metadata.json` pins the actual manuscript SHA-256 and page count. Update those fields only after a revised manuscript is accepted. The builder verifies both, refuses to label the archived baseline as final, and replaces only its generated site directory after a successful build. No scientific calculations run during this process.

The explorer keeps study populations separate. Its five S04 procedures share the same 315 targets and fixed baseline; they are not five independent studies. Score-component displays and validation scopes follow the accepted public authorities. Exact aggregate values and source hashes can be downloaded from the site.

Preview locally with `python -m http.server 8000 --directory website/site`, then visit http://localhost:8000. The generated site also supports opening index.html directly.

For GitHub Pages, `.github/workflows/pages.yml` is configured to deploy `website/site` directly from this repository. In Settings, Pages, select GitHub Actions as the source, then manually run **Publish research documents** (`workflow_dispatch`). For a separate standalone Pages repository, copy `website/site/` to its root and `website/pages.yml` to `.github/workflows/pages.yml`. The workflow follows https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages .

Refresh the browser and source validation receipts after any change. The final delivery manifest must be regenerated only through a fresh verified release, never edited in place.

S04B has a separate simulation view: histories are independent within regime and paired across procedures; means are total nats per history. Regimes are not pooled or converted to per-earthquake scores. Scientific and changed-artifact visual reviews are accepted; fresh isolated release validation supplies the final production evidence.
