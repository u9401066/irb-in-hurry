"""Optional workflow hooks and conversion helpers."""
import os
import shlex
import subprocess

DEFAULT_ERROR_MESSAGE = "unknown error"


def _automation(config):
    return config.get("automation", {}) if config else {}


def hook_commands(config, hook_name):
    """Return configured commands for a hook name."""
    hooks = _automation(config).get("hooks", {})
    commands = hooks.get(hook_name, [])
    if isinstance(commands, str):
        return [commands]
    return list(commands)


def hook_context(config, **context):
    """Build shared runtime context for hooks and converters."""
    data = {
        "phase": config.get("phase", "") if config else "",
        "irb_no": config.get("study", {}).get("irb_no", "") if config else "",
        "title_zh": config.get("study", {}).get("title_zh", "") if config else "",
    }
    for key, value in context.items():
        data[key] = "" if value is None else str(value)
    return data


def run_command(command, context, timeout=120):
    """Run a formatted command without invoking a shell."""
    if isinstance(command, str):
        args = shlex.split(command, posix=os.name != "nt")
    else:
        args = [str(part) for part in command]

    env = os.environ.copy()
    for key, value in context.items():
        env[f"IRB_HOOK_{key.upper()}"] = value

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or DEFAULT_ERROR_MESSAGE
        raise RuntimeError(f"{args[0]} failed: {stderr}")
    return result


def run_hooks(config, hook_name, **context):
    """Run all configured commands for a hook."""
    commands = hook_commands(config, hook_name)
    if not commands:
        return

    timeout = _automation(config).get("hook_timeout", 120)
    values = hook_context(config, **context)
    for command in commands:
        run_command(command, values, timeout=timeout)


def conversion_backend(config):
    """Return the configured conversion backend."""
    conversion = _automation(config).get("conversion", {})
    return conversion.get("backend", "libreoffice")


def asset_aware_command(config):
    """Return the configured Asset Aware MCP command template."""
    conversion = _automation(config).get("conversion", {})
    return conversion.get("command", "")


def asset_aware_timeout(config):
    """Return timeout for Asset Aware MCP conversion."""
    conversion = _automation(config).get("conversion", {})
    return conversion.get("timeout", 120)


def expected_pdf_path(docx_path, output_dir):
    """Return the PDF path that should be produced for a DOCX file."""
    basename = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
    return os.path.join(output_dir, basename)
