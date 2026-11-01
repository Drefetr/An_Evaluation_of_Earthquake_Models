Understanding the earthquake research

Read the eight-page PDF or the standalone HTML. The scientific completion edition includes accepted observed LI+ and comparative conditional calibration findings.

Editable content: guide_content.json. Build an isolated copy from the repository root:
  python -B companion/build_guide.py --output build/companion
Requires Python and ReportLab (included in requirements.txt); no fits, simulations
or catalogue downloads run. The output directory must be new. The default output
is build/companion, leaving the accepted companion PDF and HTML unchanged.

Review the output PDF and HTML before promotion. To build and install an accepted
revision explicitly, choose another fresh output and add --install:
  python -B companion/build_guide.py --output build/companion-to-install --install
Then rebuild/review the website and refresh source receipts and payload hashes.

Review and refresh validation after any edit. Sources and checks are in guide_sources.json and guide_validation.json. The website provides section navigation and an interactive findings explorer.
