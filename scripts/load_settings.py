"""
Load environment variables for standalone Python scripts. File values
deliberately take precedence over values inherited from the shell.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ENVIRONMENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_settings(environment_name: str | None = None) -> None:
    if environment_name is not None and not ENVIRONMENT_NAME_PATTERN.match(
        environment_name
    ):
        raise ValueError(
            f'Invalid environment name "{environment_name}". '
            "Use only letters, numbers, hyphens and underscores."
        )

    if environment_name == "shell":
        _warn("Shell-only settings mode selected; no settings file was loaded.")
        return

    settings_file = (
        f"{environment_name}.settings.json"
        if environment_name
        else "local.settings.json"
    )
    settings_path = Path.cwd() / settings_file
    source = _read_settings_file(
        settings_path, settings_file, required=environment_name is not None
    )

    if source is not None:
        _apply_settings(source, settings_file)

        if environment_name is not None:
            _warn(
                f"Loaded {settings_file}; variables not listed in Values "
                "remain inherited from the shell."
            )


def _read_settings_file(
    settings_path: Path, settings_file: str, *, required: bool
) -> str | None:
    try:
        return settings_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if required:
            raise FileNotFoundError(
                f"Selected settings file {settings_file} was not found."
            ) from None

        _warn(
            f"Settings file {settings_file} was not found; "
            "using existing environment variables."
        )
        return None
    except OSError as error:
        raise OSError(f"Unable to read {settings_file}.") from error


def _apply_settings(source: str, settings_file: str) -> None:
    try:
        settings: Any = json.loads(source)
    except json.JSONDecodeError:
        # JSON parser details can include fragments of a secret value.
        raise ValueError(f"Unable to parse {settings_file} as JSON.") from None

    if not isinstance(settings, dict) or not isinstance(settings.get("Values"), dict):
        raise ValueError(f"{settings_file} must contain a Values object.")

    for name, value in settings["Values"].items():
        if not VARIABLE_NAME_PATTERN.match(name):
            raise ValueError(
                f"{settings_file} contains an invalid environment variable name: {name}"
            )

        if not isinstance(value, str | int | float | bool):
            raise ValueError(
                f"{settings_file} contains a non-scalar value for "
                f"environment variable {name}."
            )

        if name in os.environ:
            # Report only the variable name so diagnostics never disclose either value.
            _warn(
                f"Settings file {settings_file} overrides environment variable {name}."
            )

        os.environ[name] = _to_environment_value(value)


def _to_environment_value(value: str | int | float | bool) -> str:
    # Match the JSON spelling of booleans rather than Python's True/False.
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _warn(message: str) -> None:
    print(message, file=sys.stderr)
