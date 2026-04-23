#!/usr/bin/env python3
"""Main orchestrator: load config → select forms → generate all → update checklist."""
import os
import sys
import importlib

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.docx_utils import apply_institution_text_replacements, load_config
from scripts.form_selector import select_forms, get_generator
from scripts.institution_profiles import (
    get_harness_phases,
    get_institution_profile,
    get_phase_name,
    should_isolate_phase_outputs,
)
from scripts.checklist import generate_checklist
from scripts.workflow_hooks import run_hooks


def _run_single_phase(config, phase, output_dir, institution_profile, generated_totals, config_path):
    """Run one phase and return (generated, errors, missing, checklist_path)."""
    config = dict(config)
    config["phase"] = phase

    phase_zh = get_phase_name(phase, institution_profile)
    irb_no = config["study"]["irb_no"]

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  IRB-in-Hurry Form Generator                ║")
    print(f"╠══════════════════════════════════════════════╣")
    print(f"║  IRB No:  {irb_no:<34}║")
    print(f"║  Phase:   {phase_zh:<34}║")
    print(f"╚══════════════════════════════════════════════╝")
    print()

    os.makedirs(output_dir, exist_ok=True)
    run_hooks(
        config,
        "before_generate",
        config_path=config_path,
        output_dir=output_dir,
        phase=phase,
        harness_sequence=">".join(generated_totals.get("harness", [])),
    )

    # Select required forms
    forms = select_forms(config, institution=institution_profile["id"])
    print(f"Selected {len(forms)} forms for {phase_zh}:")
    for fid, name_zh in forms:
        print(f"  → {fid} {name_zh}")
    print()

    results = []
    for fid, name_zh in forms:
        gen_info = get_generator(fid)
        if gen_info is None:
            print(f"  ⚠ {fid} {name_zh} — no generator registered")
            results.append((fid, name_zh, None, "missing"))
            continue

        mod_path, func_name = gen_info
        try:
            run_hooks(
                config,
                "before_form_generate",
                config_path=config_path,
                output_dir=output_dir,
                phase=phase,
                form_id=fid,
                form_name_zh=name_zh,
            )
            mod = importlib.import_module(f"scripts.{mod_path}")
            gen_func = getattr(mod, func_name)
            path = gen_func(config, output_dir)
            apply_institution_text_replacements(path, institution_profile)
            print(f"  ■ {fid} {name_zh} → {os.path.basename(path)}")
            results.append((fid, name_zh, path, "generated"))
            run_hooks(
                config,
                "after_form_generate",
                config_path=config_path,
                output_dir=output_dir,
                phase=phase,
                form_id=fid,
                form_name_zh=name_zh,
                output_path=path,
            )
        except Exception as e:
            print(f"  ✗ {fid} {name_zh} — ERROR: {e}")
            results.append((fid, name_zh, None, "error"))

    checklist_path = generate_checklist(
        config,
        results,
        phase_zh,
        output_path=os.path.join(output_dir, "checklist.md"),
    )
    print(f"\n■ Checklist written to {checklist_path}")

    generated = sum(1 for _, _, _, s in results if s == "generated")
    errors = sum(1 for _, _, _, s in results if s == "error")
    missing = sum(1 for _, _, _, s in results if s == "missing")
    run_hooks(
        config,
        "after_generate",
        config_path=config_path,
        output_dir=output_dir,
        phase=phase,
        harness_sequence=">".join(generated_totals.get("harness", [])),
        checklist_path=checklist_path,
        generated=generated,
        errors=errors,
        missing=missing,
    )
    print(f"\n{'═' * 46}")
    print(f"  Generated: {generated}  Errors: {errors}  Missing: {missing}")
    print(f"  Output:    {os.path.abspath(output_dir)}/")
    print(f"{'═' * 46}")

    return generated, errors, missing, checklist_path


def main(config_path="config.yml", output_dir="output"):
    """Generate all required IRB forms based on config."""
    config = load_config(config_path)
    institution_profile = get_institution_profile(config)
    harness_phases = get_harness_phases(config)
    isolate_outputs = should_isolate_phase_outputs(config)

    if len(harness_phases) > 1:
        print(f"Running {len(harness_phases)}-phase harness: {' -> '.join(harness_phases)}")
        print()

    run_meta = {"harness": harness_phases}
    total_generated = total_errors = total_missing = 0
    for phase in harness_phases:
        current_output_dir = output_dir
        if isolate_outputs:
            current_output_dir = os.path.join(output_dir, phase)

        generated, errors, missing, _ = _run_single_phase(
            config,
            phase,
            current_output_dir,
            institution_profile,
            generated_totals=run_meta,
            config_path=config_path,
        )
        total_generated += generated
        total_errors += errors
        total_missing += missing
        if errors > 0:
            print(f"⚠ Phase '{phase}' had {errors} error(s). See generated output above.")

    print(f"\n{'═' * 52}")
    print(f"  Harness Phases: {' -> '.join(harness_phases)}")
    print(f"  Total Generated: {total_generated}  Total Errors: {total_errors}  Total Missing: {total_missing}")
    print(f"  Output root: {os.path.abspath(output_dir)}/")
    print(f"{'═' * 52}")

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yml"
    main(config_path)
