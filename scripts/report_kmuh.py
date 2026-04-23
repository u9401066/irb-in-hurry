#!/usr/bin/env python3
"""Generate a per-phase KMUH report with expected vs generated form coverage."""

from __future__ import annotations

import os
import sys
import yaml
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.form_selector import select_forms
from scripts.institution_profiles import get_phase_name, get_harness_phases
from scripts.docx_utils import load_config


def _normalize_form_id(path):
    """Extract canonical form id from filename."""
    base = os.path.splitext(os.path.basename(path))[0]
    if base.startswith("中文計畫摘要"):
        return "PROPOSAL"
    if base.startswith("proposal"):
        return "PROPOSAL"
    if "_" in base:
        prefix = base.split("_", 1)[0]
    else:
        prefix = base
    if prefix.startswith("SF") and len(prefix) >= 4 and prefix[2:5].isdigit():
        return prefix[:5]
    if prefix.startswith("SF") and len(prefix) >= 5 and prefix[2:6].isdigit():
        return prefix[:6]
    return prefix


def _phase_output_dir(phase, output_root="output"):
    """Return output directory for a phase."""
    path = os.path.join(output_root, phase)
    return path if os.path.isdir(path) else output_root


def _collect_docx_files(output_dir):
    """Collect generated DOCX files for directory (recursive)."""
    return sorted(glob.glob(os.path.join(output_dir, "**", "*.docx"), recursive=True))


def _load_config(config_path):
    config = load_config(config_path)
    return config


def _load_checklist(output_dir):
    path = os.path.join(output_dir, "checklist.md")
    if not os.path.exists(path):
        return None
    return path


def _completion_status(checklist_path):
    if not checklist_path or not os.path.exists(checklist_path):
        return None, None, None
    with open(checklist_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    done = sum(1 for line in lines if line.startswith("■"))
    todo = sum(1 for line in lines if line.startswith("□"))
    total = done + todo
    if total == 0:
        return 0, 0, 0
    return done, todo, total


def main(config_path="config.yml", output_root="output"):
    config = _load_config(config_path)
    phases = get_harness_phases(config)
    profile = {"id": config.get("institution", "kmuh")}

    lines = []
    lines.append("KMUH Phase Coverage Report")
    lines.append("=========================")
    lines.append("")

    all_ok = True

    for phase in phases:
        phase_config = dict(config)
        phase_config["phase"] = phase
        selected = select_forms(phase_config, institution=profile["id"])
        expected = [fid for fid, _ in selected]

        phase_dir = _phase_output_dir(phase, output_root)
        docx_files = _collect_docx_files(phase_dir)
        generated = {_normalize_form_id(f) for f in docx_files}

        missing = [fid for fid in expected if fid not in generated]
        unexpected = [fid for fid in sorted(generated) if fid not in expected]
        ok = len(missing) == 0
        all_ok = all_ok and ok

        phase_name = get_phase_name(phase, profile)

        lines.append(f"Phase: {phase} ({phase_name})")
        lines.append(f"  Output: {phase_dir}")
        lines.append(f"  Expected count: {len(expected)}")
        lines.append(f"  Generated count: {len(generated)}")
        lines.append(f"  Status: {'OK' if ok else 'MISSING'}")
        lines.append("")

        lines.append("  Selected Forms:")
        if selected:
            for fid in expected:
                mark = "  ○" if fid in generated else "  ×"
                lines.append(f"{mark} {fid}")
        else:
            lines.append("  (no selected forms)")

        if missing:
            lines.append("")
            lines.append("  Missing:")
            for fid in missing:
                lines.append(f"    - {fid}")

        if unexpected:
            lines.append("")
            lines.append("  Extra:")
            for fid in unexpected:
                lines.append(f"    - {fid}")

        checklist_path = _load_checklist(phase_dir)
        done, todo, total = _completion_status(checklist_path)
        if total is not None:
            if todo == 0:
                lines.append("")
                lines.append(f"  Checklist: {done}/{total} complete ✓")
            else:
                lines.append("")
                lines.append(f"  Checklist: {done}/{total} complete, pending {todo}")
        lines.append("")

    lines.append("Summary:")
    lines.append(f"  All phases complete: {'Yes' if all_ok else 'No'}")

    report = "\n".join(lines) + "\n"
    print(report)

    return 0


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yml"
    output_root = sys.argv[2] if len(sys.argv) > 2 else "output"
    raise SystemExit(main(config_path, output_root))
