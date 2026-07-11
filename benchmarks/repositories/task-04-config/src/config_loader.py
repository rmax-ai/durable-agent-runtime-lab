"""Configuration loader for the application."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml


def load_config(config_dir: str = "config") -> dict[str, Any]:
    """Load all YAML config files from the config directory.

    Args:
        config_dir: Path to the directory containing YAML config files.

    Returns:
        A merged dictionary of all configuration sections.

    Raises:
        FileNotFoundError: If the config directory does not exist.
    """
    config_path = Path(config_dir)
    if not config_path.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    config: dict[str, Any] = {}
    for yaml_file in sorted(config_path.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
            if data:
                config.update(data)

    return config


def setup_logging(config: dict[str, Any]) -> None:
    """Configure logging from the logging config section.

    Reads the 'logging' section of the config dict and configures
    Python's logging module accordingly.

    Args:
        config: The full application configuration dictionary.
    """
    log_config = config.get("logging", {})

    log_format = log_config.get("formatters", {}).get("standard", {}).get(
        "format", "%(levelname)s %(message)s"
    )
    log_level = getattr(logging, log_config.get("handlers", {}).get("console", {}).get("level", "INFO"))

    logging.basicConfig(
        level=log_level,
        format=log_format,
    )

    # Also set up file handler if configured
    file_handler_config = log_config.get("handlers", {}).get("file", {})
    if file_handler_config.get("filename"):
        file_handler = logging.FileHandler(file_handler_config["filename"])
        file_handler.setLevel(
            getattr(logging, file_handler_config.get("level", "DEBUG"))
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
