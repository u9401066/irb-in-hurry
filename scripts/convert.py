#!/usr/bin/env python3
"""DOCX → PDF → PNG preview pipeline.

Requires:
- LibreOffice (for DOCX→PDF): brew install --cask libreoffice
- poppler (for PDF→PNG): brew install poppler
"""
import os
import sys
import glob
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.docx_utils import load_config
from scripts.workflow_hooks import (
    asset_aware_command,
    asset_aware_timeout,
    conversion_backend,
    expected_pdf_path,
    hook_context,
    run_command,
    run_hooks,
)


def docx_to_pdf(docx_path, output_dir, config=None):
    """Convert DOCX to PDF using LibreOffice headless."""
    backend = conversion_backend(config)
    if backend == "asset_aware_mcp":
        output_path = expected_pdf_path(docx_path, output_dir)
        command = asset_aware_command(config)
        if not command:
            print("  ✗ Asset Aware MCP backend requires automation.conversion.command")
            return None
        try:
            run_command(
                command,
                hook_context(
                    config,
                    input_path=docx_path,
                    output_dir=output_dir,
                    output_path=output_path,
                    pdf_path=output_path,
                ),
                timeout=asset_aware_timeout(config),
            )
        except Exception as e:
            print(f"  ✗ Asset Aware MCP conversion failed for {os.path.basename(docx_path)}: {e}")
            return None
        return output_path if os.path.exists(output_path) else None

    # Try common LibreOffice paths on macOS
    soffice_paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/local/bin/soffice",
        "soffice",
    ]

    soffice = None
    for p in soffice_paths:
        if os.path.exists(p) or p == "soffice":
            soffice = p
            break

    if soffice is None:
        print("⚠ LibreOffice not found. Install: brew install --cask libreoffice")
        return None

    try:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", output_dir, docx_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            basename = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
            return os.path.join(output_dir, basename)
        else:
            print(f"  ✗ PDF conversion failed for {os.path.basename(docx_path)}: {result.stderr}")
            return None
    except FileNotFoundError:
        print("⚠ LibreOffice not found. Install: brew install --cask libreoffice")
        return None
    except subprocess.TimeoutExpired:
        print(f"  ✗ PDF conversion timed out for {os.path.basename(docx_path)}")
        return None


def pdf_to_png(pdf_path, preview_dir, dpi=150):
    """Convert first page of PDF to PNG using pdf2image."""
    try:
        from pdf2image import convert_from_path
        os.makedirs(preview_dir, exist_ok=True)
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=dpi)
        if images:
            basename = os.path.splitext(os.path.basename(pdf_path))[0] + ".png"
            png_path = os.path.join(preview_dir, basename)
            images[0].save(png_path, "PNG")
            return png_path
    except ImportError:
        print("⚠ pdf2image not installed. Run: pip install pdf2image")
    except Exception as e:
        print(f"  ✗ PNG conversion failed for {os.path.basename(pdf_path)}: {e}")
    return None


def main(output_dir="output", config_path="config.yml"):
    """Convert all DOCX files in output_dir to PDF and PNG previews."""
    config = load_config(config_path) if os.path.exists(config_path) else {}
    preview_dir = os.path.join(output_dir, "preview")
    os.makedirs(preview_dir, exist_ok=True)
    run_hooks(
        config,
        "before_convert",
        config_path=config_path,
        output_dir=output_dir,
        preview_dir=preview_dir,
    )

    docx_files = sorted(glob.glob(os.path.join(output_dir, "*.docx")))
    if not docx_files:
        print("No .docx files found in output/")
        return

    print(f"Converting {len(docx_files)} DOCX files...")
    print()

    pdf_count = 0
    png_count = 0

    for docx_path in docx_files:
        basename = os.path.basename(docx_path)

        # DOCX → PDF
        run_hooks(
            config,
            "before_docx_to_pdf",
            config_path=config_path,
            input_path=docx_path,
            output_dir=output_dir,
            preview_dir=preview_dir,
        )
        pdf_path = docx_to_pdf(docx_path, output_dir, config=config)
        if pdf_path:
            print(f"  ■ PDF: {basename}")
            pdf_count += 1
            run_hooks(
                config,
                "after_docx_to_pdf",
                config_path=config_path,
                input_path=docx_path,
                output_dir=output_dir,
                preview_dir=preview_dir,
                output_path=pdf_path,
                pdf_path=pdf_path,
            )

            # PDF → PNG preview
            run_hooks(
                config,
                "before_pdf_to_png",
                config_path=config_path,
                input_path=docx_path,
                output_dir=output_dir,
                preview_dir=preview_dir,
                pdf_path=pdf_path,
            )
            png_path = pdf_to_png(pdf_path, preview_dir)
            if png_path:
                print(f"  ■ PNG: {os.path.basename(png_path)}")
                png_count += 1
                run_hooks(
                    config,
                    "after_pdf_to_png",
                    config_path=config_path,
                    input_path=docx_path,
                    output_dir=output_dir,
                    preview_dir=preview_dir,
                    pdf_path=pdf_path,
                    png_path=png_path,
                    output_path=png_path,
                )
        else:
            print(f"  □ PDF: {basename} — skipped")

    run_hooks(
        config,
        "after_convert",
        config_path=config_path,
        output_dir=output_dir,
        preview_dir=preview_dir,
        pdf_count=pdf_count,
        png_count=png_count,
    )
    print(f"\n{'═' * 40}")
    print(f"  PDFs:     {pdf_count}/{len(docx_files)}")
    print(f"  Previews: {png_count}/{len(docx_files)}")
    print(f"{'═' * 40}")


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yml"
    main(output_dir, config_path)
