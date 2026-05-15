"""ai_trader CLI 진입점. `trader backtest|paper|live --config <path>`."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trader")
    parser.add_argument("mode", choices=["backtest", "paper", "live"])
    parser.add_argument(
        "--config",
        default="src/ai_trader/configs/base.yaml",
        help="base.yaml 경로",
    )
    args = parser.parse_args(argv)

    from ai_trader.orchestrator.runner import run

    return run(mode=args.mode, config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
