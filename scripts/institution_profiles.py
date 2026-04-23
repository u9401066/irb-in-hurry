"""Institution-specific settings for IRB forms.

This module stores all institution-dependent strings and default harness flow settings.
"""

from copy import deepcopy


DEFAULT_INSTITUTION_ID = "kmuh"


def _mk_profile(
    id_,
    name,
    committee_name,
    irb_no_label,
    submission_email,
    decision_note,
    dashboard_title,
):
    """Build a normalized institution profile."""
    return {
        "id": id_,
        "name": name,
        "committee_name": committee_name,
        "irb_no_label": irb_no_label,
        "submission_email": submission_email,
        "decision_note": decision_note,
        "dashboard_title": dashboard_title,
        "phase_names": {
            "new": "新案審查",
            "amendment": "修正案審查",
            "re_review": "複審案審查",
            "continuing": "期中審查",
            "closure": "結案審查",
            "sae": "嚴重不良反應事件審查",
            "ib_update": "主持人手冊更新",
            "import": "專案進口審查",
            "suspension": "計畫暫停/提前終止",
            "appeal": "申覆案審查",
        },
        "text_replacements": {
            "和信治癌中心醫院 人體試驗委員會": committee_name,
            "KFSYSCC-IRB編號": irb_no_label,
            "irb@kfsyscc.org": submission_email,
        },
        "default_harness_phases": [
            "new",
            "amendment",
            "continuing",
            "closure",
            "re_review",
            "sae",
            "ib_update",
            "import",
            "suspension",
            "appeal",
        ],
    }


INSTITUTION_PROFILES = {
    "kfsyscc": _mk_profile(
        id_="kfsyscc",
        name="KFSYSCC",
        committee_name="和信治癌中心醫院 人體試驗委員會",
        irb_no_label="KFSYSCC-IRB編號",
        submission_email="irb@kfsyscc.org",
        decision_note="正式審查結果以和信治癌中心醫院人體試驗委員會之決議為準。",
        dashboard_title="KFSYSCC IRB Submission Dashboard",
    ),
    "kmuh": _mk_profile(
        id_="kmuh",
        name="KMUH",
        committee_name="高雄醫學大學附設中和紀念醫院 人體試驗委員會",
        irb_no_label="KMUH-IRB編號",
        submission_email="irb@kmuh.org.tw",
        decision_note="正式審查結果以高雄醫學大學附設中和紀念醫院人體試驗委員會之決議為準。",
        dashboard_title="KMUH 人體試驗委員會 IRB Submission Dashboard",
    ),
}


def normalize_institution_id(institution):
    """Normalize institution config value into a known institution id."""
    if isinstance(institution, str):
        normalized = institution.strip().lower()
        return normalized if normalized in INSTITUTION_PROFILES else DEFAULT_INSTITUTION_ID
    if isinstance(institution, dict):
        return normalize_institution_id(institution.get("id") or institution.get("name"))
    return DEFAULT_INSTITUTION_ID


def get_institution_profile(config=None):
    """Return immutable institution profile for config."""
    if config is None:
        return deepcopy(INSTITUTION_PROFILES[DEFAULT_INSTITUTION_ID])
    institution = config.get("institution", DEFAULT_INSTITUTION_ID) if isinstance(config, dict) else DEFAULT_INSTITUTION_ID
    institution_id = normalize_institution_id(institution)
    return deepcopy(INSTITUTION_PROFILES[institution_id])


def get_harness_phases(config):
    """Resolve phases for harness mode from config."""
    harness = config.get("harness", {}) if isinstance(config, dict) else {}
    profile = get_institution_profile(config)
    default_phases = profile["default_harness_phases"]

    explicit = harness.get("phases") if isinstance(harness, dict) else None
    if explicit is None:
        return [config.get("phase", "new")] if isinstance(config, dict) and config.get("phase") else ["new"]

    # Preserve order, remove duplicates, ignore empty values
    phases = []
    for p in explicit:
        if not p:
            continue
        p = str(p)
        if p not in phases:
            phases.append(p)
    return phases or default_phases


def should_isolate_phase_outputs(config):
    """Whether multiple phase outputs should be written into per-phase subfolders."""
    harness = config.get("harness", {}) if isinstance(config, dict) else {}
    phases = get_harness_phases(config) if isinstance(config, dict) else ["new"]
    explicit = harness.get("group_by_phase") if isinstance(harness, dict) else None
    if explicit is not None:
        return bool(explicit)
    return len(phases) > 1


def get_phase_name(phase, config_or_profile=None):
    """Get display name for a phase."""
    if isinstance(config_or_profile, dict) and config_or_profile.get("phase_names"):
        profile = config_or_profile
    else:
        profile = get_institution_profile({"institution": config_or_profile}) if config_or_profile else get_institution_profile()
    return profile.get("phase_names", {}).get(phase, phase)
