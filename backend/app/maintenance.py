from __future__ import annotations

import argparse
import json

from .app_factory import DEFAULT_DATA_ROOT
from .database import DatabaseManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Atelier database maintenance.")
    parser.add_argument("command", choices=("inspect", "clear"))
    parser.add_argument("environment", choices=("production", "test"))
    parser.add_argument(
        "--confirm",
        default="",
        help="Required confirmation for destructive clear operations.",
    )
    args = parser.parse_args()

    manager = DatabaseManager(DEFAULT_DATA_ROOT)
    if args.command == "inspect":
        print(json.dumps(manager.database_info(args.environment), indent=2))
        return

    expected = f"CLEAR {args.environment.upper()}"
    if args.confirm != expected:
        raise SystemExit(f"Refusing to clear. Pass --confirm \"{expected}\".")
    result = manager.clear_environment_data(args.environment)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

