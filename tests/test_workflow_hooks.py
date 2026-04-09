"""Tests for optional workflow hooks and conversion backends."""
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.convert import docx_to_pdf
from scripts.docx_utils import load_config
from scripts.generate_all import main as generate_all_main


def write_text_command(target, content):
    return (
        "python -c "
        f"\"from pathlib import Path; Path(r'{target}').write_text(r'{content}', encoding='utf-8')\""
    )


def test_generate_all_runs_configured_hooks(tmp_path):
    """Generate forms with hooks enabled and verify hook outputs."""
    config = load_config("tests/fixtures/sample_retrospective.yml")
    before_marker = tmp_path / "before.txt"
    after_marker = tmp_path / "after.txt"

    config["automation"] = {
        "hooks": {
            "before_generate": [write_text_command(before_marker, "{phase}|{irb_no}")],
            "after_generate": [write_text_command(after_marker, "{generated}|{errors}|{missing}")],
        }
    }

    config_path = tmp_path / "config.yml"
    output_dir = tmp_path / "output"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

    generate_all_main(str(config_path), str(output_dir))

    assert before_marker.read_text(encoding="utf-8") == "new|20250801A"
    assert after_marker.read_text(encoding="utf-8") == "6|0|0"


def test_docx_to_pdf_supports_asset_aware_mcp_backend(tmp_path):
    """Allow custom conversion commands for Asset Aware MCP."""
    docx_path = tmp_path / "IRB_SF001_新案審查送審資料表.docx"
    docx_path.write_bytes(b"placeholder docx")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    config = {
        "automation": {
            "conversion": {
                "backend": "asset_aware_mcp",
                "command": 'python -c "from pathlib import Path; Path(r\'{output_path}\').write_bytes(b\'%PDF-1.4\\n%%EOF\')"',
            }
        }
    }

    pdf_path = docx_to_pdf(str(docx_path), str(output_dir), config=config)

    assert pdf_path == str(output_dir / "IRB_SF001_新案審查送審資料表.pdf")
    assert os.path.exists(pdf_path)
    with open(pdf_path, "rb") as f:
        assert f.read().startswith(b"%PDF-1.4")
