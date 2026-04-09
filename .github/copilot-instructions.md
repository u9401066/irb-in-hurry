# IRB-in-Hurry Copilot Instructions

Use these repository rules when GitHub Copilot works on IRB-in-Hurry:

- Python is managed with `uv`; run commands with `uv run` or `make`
- Keep `config.yml` as the single source of truth; never hardcode study data
- All generated artifacts belong in `output/`, with previews in `output/preview/`
- Use 標楷體 for generated form text
- Use `■` for checked values and `□` for unchecked values
- Preserve the document pipeline: `config.yml` → `scripts/generate_all.py` → `scripts/convert.py` → `output/*.pdf` and `output/preview/*.png`
- Optional workflow hooks are configured in `automation.hooks` inside `config.yml`
- Optional custom conversion backends are configured in `automation.conversion`; use this for Asset Aware MCP output conversion
- Validate changes with `uv run pytest tests/ -v`
