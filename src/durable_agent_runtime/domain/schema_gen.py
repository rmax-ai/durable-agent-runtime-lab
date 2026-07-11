"""JSON Schema generation from Pydantic domain models.

Generates JSON Schema files from the canonical Pydantic models (Section 9 requirement).
Schema files are written to the schemas/ directory.
"""

import json
from pathlib import Path

from durable_agent_runtime.domain import (
    ActionProposal,
    Checkpoint,
    Event,
    ExecutionResult,
    GoalSpecification,
    Plan,
    Task,
    VerificationResult,
)

SCHEMA_DIR = Path(__file__).parent.parent.parent.parent / "schemas"

MODEL_SCHEMA_MAP = {
    "goal": GoalSpecification,
    "plan": Plan,
    "task": Task,
    "action-proposal": ActionProposal,
    "execution-result": ExecutionResult,
    "verification-result": VerificationResult,
    "event": Event,
    "checkpoint": Checkpoint,
}


def generate_schema(model_class: type) -> dict:
    """Generate JSON Schema for a Pydantic model."""
    return model_class.model_json_schema()


def generate_all_schemas(output_dir: Path | None = None) -> dict[str, Path]:
    """Generate all JSON Schema files and write them to disk.

    Returns a mapping of schema_name -> output_path.
    """
    target = output_dir or SCHEMA_DIR
    target.mkdir(parents=True, exist_ok=True)

    results: dict[str, Path] = {}
    for name, model in MODEL_SCHEMA_MAP.items():
        schema = generate_schema(model)
        output_path = target / f"{name}.schema.json"
        output_path.write_text(json.dumps(schema, indent=2) + "\n")
        results[name] = output_path

    return results


def validate_against_schema(schema_name: str, instance: dict) -> bool:
    """Validate a dict against a generated schema.

    Basic structural validation only — full JSON Schema validation requires jsonschema.
    """
    model_class = MODEL_SCHEMA_MAP.get(schema_name)
    if model_class is None:
        raise ValueError(f"Unknown schema: {schema_name}")

    try:
        model_class.model_validate(instance)
        return True
    except Exception:
        return False
