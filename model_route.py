import argparse
import ast
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from typesafe_sdk import Choice, TypeSafeClient

load_dotenv()


def _parse_scalar(value: str) -> object:
    # Parse quoted strings, numbers, and booleans without requiring a YAML package.
    value = value.strip()
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.lower() in {"null", "~"}:
            return None
        return value

# This function will load model configurations from a YAML file and return them as a list of dictionaries. 
# Each dictionary represents a model with its metadata, such as name, id, description, and rank. 
# The function also performs validation to ensure that each model entry is complete and unique.

def load_models(path: Path | None = None) -> list[dict[str, object]]:
    """Load model entries from the project's simple models.yaml list."""
    if path is None:
        # Support both a config next to this script and the current virtualenv layout.
        path = Path(__file__).with_name("models.yaml")
        
    if not path.is_file():
        raise FileNotFoundError(f"Model configuration not found: {path}")

    models: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_models = False
    field_pattern = re.compile(r"^\s*([A-Za-z_]\w*):\s*(.*?)\s*$")

    # Read the flat `models:` list format used by the project's configuration.
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "models:":
            in_models = True
            continue
        if not in_models:
            continue

        if stripped.startswith("- "):
            if current is not None:
                models.append(current)
            current = {}
            line = re.sub(r"^\s*-\s*", "", line, count=1)

        match = field_pattern.match(line)
        if match is None or current is None:
            raise ValueError(f"Unsupported models.yaml syntax at {path}:{line_number}")
        key, value = match.groups()
        current[key] = _parse_scalar(value)

    if current is not None:
        models.append(current)
    if not models:
        raise ValueError(f"No models were defined in {path}")

    names: set[str] = set()
    for model in models:
        # Fail early on incomplete or ambiguous entries before sending them for routing.
        for required in ("name", "id", "description"):
            if not isinstance(model.get(required), str) or not model[required]:
                raise ValueError(f"Each model in {path} must have a non-empty {required!r}")
        name = model["name"]
        if name in names:
            raise ValueError(f"Duplicate model name {name!r} in {path}")
        names.add(name)

    return models


def select_model(user_request: str, models: list[dict[str, object]]) -> dict[str, object]:
    if not user_request.strip():
        raise ValueError("The user request must not be empty")

    criteria = {
        # Pass each model's metadata to Jev so it can compare capabilities and cost rank.
        str(model["name"]): (
            f"{model['description']} "
            f"(rank: {model.get('rank', 'unspecified')}; lower-ranked models are generally cheaper)"
        )
        for model in models
    }

    #print(criteria)

    with TypeSafeClient(model="jev-latest", api_key=os.getenv("TYPESAFE_API_KEY")) as client:
        response = client.system_one(
            state=user_request,
            questions={
                "model": Choice(
                    instructions=(
                        "Select the least expensive model that can satisfy the user's request. "
                        "Use the model descriptions and ranks; choose a more capable model when "
                        "the request needs difficult reasoning, coding, or analysis."
                    ),
                    criteria=criteria,
                )
            },
        )

    selected_name = response.choices["model"].choice
    #print(response.choices["model"])
    # Return the full config entry, not just the label selected by the classifier.
    return next(model for model in models if model["name"] == selected_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose the best configured model for a request.")
    parser.add_argument("request", nargs="+", help="The user's request to route")
    args = parser.parse_args()

    selected = select_model(" ".join(args.request), load_models())
    print(f"{selected['name']} ({selected['id']})")


if __name__ == "__main__":
    main()
