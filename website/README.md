# Research documents on GitHub Pages

The generated site contains the current monograph, the plain-language guide and an interactive explorer of S03, S04 observed, S06 and matched-generator S04B results. It separately reports the joint temporal-backbone comparison, including unavailable outcomes. Exact page counts and document identities are recorded in document_metadata.json. Calibration conclusions are explained in the guide and manuscript; the explorer does not compare p-values as model-performance scores.

Build an isolated preview from the repository root. Output directories must be new:

```
python -B website/build_site.py --output build/site
node website/check_interactions.cjs build/site
```

Python and PyMuPDF are required for the build; Node.js 22 is used for interaction checks. Install Python dependencies with `python -m pip install -r requirements.txt`. The generated site needs only a browser. The default output is `build/site`; ordinary builds leave the committed bundle and source documents unchanged. `document_metadata.json` pins the actual manuscript SHA-256 and page count. Update those fields only after a revised manuscript is accepted. The builder verifies both and refuses to label the archived baseline as final. No fits, simulations or catalogue downloads run during this process.

To preview an edited companion, first run `python -B companion/build_guide.py --output build/companion`, then pass `--companion build/companion` to the site builder with a fresh site output directory. Otherwise the site uses the accepted PDF and HTML in `companion/`.

The explorer keeps study populations separate. Its five S04 procedures share the same 315 targets and fixed baseline; they are not five independent studies. Score-component displays and validation scopes follow the accepted public authorities. Exact aggregate values and source hashes can be downloaded from the site.

Preview locally with `python -m http.server 8000 --directory build/site`, then visit http://localhost:8000. The generated site also supports opening index.html directly.

The [research website](https://drefetr.github.io/An_Evaluation_of_Earthquake_Models/) updates automatically after pushes to `main`. `.github/workflows/pages.yml` verifies the source/payload bindings, builds the standalone site, exercises the explorer selector combinations, and publishes the verified bundle at the root of the dedicated `gh-pages` branch. The source branch keeps the research code and documentation; `docs/` remains the documentation directory. Publication does not add or replace a source-branch `index.html`.

In repository Settings, Pages, set **Source: GitHub Actions**. The same workflow explicitly uploads and deploys the published artifact using Pages/OIDC permissions; pushing `gh-pages` with `GITHUB_TOKEN` alone does not trigger a Pages build. GitHub documents this restriction under [configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). To publish manually, run **Publish research documents** from the Actions tab with branch `main` selected. Pull-request runs and manual runs from other branches cannot publish.

`scripts/publish_pages.py` records the source `main` commit and generated content tree in `publication.json`. It uses a separate temporary Git index, creates a normal child of the observed `gh-pages` tip, and requires an exact remote-tip lease. Repeating the same source and bundle reuses the existing publication commit. A stale source or concurrent publication fails rather than overwriting another update. The workflow exports that exact published tree to `build/pages-published`, packages it with GitHub's official `upload-pages-artifact` action, and checks every archived public file against the export before deployment. The official packager omits the empty `.nojekyll` marker, which remains on `gh-pages` for branch-based builds; Actions deployment skips Jekyll. No other missing, extra, changed, duplicate or linked file is accepted. The build/publication job has repository write permission; the separate deployment job has only repository read, Pages write and OIDC permissions. Workflow runs are serialized for this site.

For a separate standalone Pages repository, copy a generated deployment bundle as a `site/` directory and `website/pages.yml` to `.github/workflows/pages.yml`; that template uploads `site/` without requiring Python sources. The committed repository preview described below is a different layout and depends on its canonical document paths.

The canonical document files are `paper/manuscript_unified.pdf` and `companion/lay_guide_to_the_research.pdf`. Generated deployment bundles copy these PDFs into `downloads/` so they remain self-contained when deployed to Pages or copied to a standalone `site/` repository. The deployment `documents.json` records the actual copied paths and hashes, with `bundle_kind` set to `self_contained_deployment`.

The committed `website/site/` is a repository preview that links the canonical PDFs using `../../paper/` and `../../companion/`; it contains no PDF copies. Its `documents.json` identifies those actual relative paths and hashes with `bundle_kind` set to `repository_preview`. To preview it with working document links, serve the repository root with `python -m http.server 8000 --directory .` and visit http://localhost:8000/website/site/. Copying only this preview directory to a standalone host would omit its canonical documents; use a generated deployment bundle for that purpose.

After reviewing an isolated output, use `python -B website/build_site.py --output build/site-to-install --install` to refresh the repository preview, then refresh verification receipts and the canonical payload manifest. The install step replaces only the known generated site tree, rewrites PDF links to canonical sources, and omits duplicate PDF copies. Install an accepted edited companion in `companion/` first; a repository preview cannot depend on ignored `build/` files or external candidate documents. `website/findings.html` is the editable template; `website/site/findings.html` is generated from it and the accepted authorities.

S04B has a separate simulation view: histories are independent within regime and paired across procedures; means are total nats per history. Regimes are not pooled or converted to per-earthquake scores. Scientific and changed-artifact visual reviews are accepted; fresh isolated release validation supplies the final production evidence.
