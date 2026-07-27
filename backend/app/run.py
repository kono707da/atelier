from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app_factory import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Atelier application server.")
    parser.add_argument("--atelier-server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--project-root", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8110)
    parser.add_argument(
        "--environment",
        choices=("production", "test"),
        default="production",
    )
    parser.add_argument(
        "--lock-database",
        action="store_true",
        help="Prevent runtime switching away from the selected database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    locked_environment = args.environment if args.lock_database else None
    application = create_app(
        environment=args.environment,
        locked_environment=locked_environment,
    )
    uvicorn.run(
        application,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

