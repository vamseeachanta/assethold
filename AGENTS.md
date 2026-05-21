---
purpose: Asset portfolio financial analysis — fundamentals, options, modules, analysis pipelines
entry_points: [src/assethold/engine.py, src/assethold/fundamentals.py, src/assethold/analysis/]
test_command: uv run python -m pytest tests/ --noconftest
depends_on: [assetutilities]
maturity: beta
---
# assethold

Contract: ../workspace-hub/AGENTS.md | Source: src/assethold/
Key modules: engine.py, fundamentals.py, fundamentals_report.py, analysis/, modules/, options/
