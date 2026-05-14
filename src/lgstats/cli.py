"""lgstats 통합 CLI.

Examples
--------
  lgstats industry-promotion --raw-dir data/raw/lofin --out data/processed/industry_promotion.xlsx
  lgstats industry-promotion --template-only --out data/processed/industry_promotion_template.xlsx
  lgstats kosis-population --out data/processed/kosis_population.xlsx
  lgstats kosis-discover --keyword "주민등록인구"
  lgstats kosis-export-config --out configs/sources/kosis_vars.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lgstats.pipelines import industry_promotion, kosis_population
from lgstats.sources.kosis.catalog import DEFAULT_VARS


def _cmd_industry(a: argparse.Namespace) -> None:
    industry_promotion.run(
        raw_dir=None if a.template_only else a.raw_dir,
        out=a.out,
    )


def _cmd_kosis_pop(a: argparse.Namespace) -> None:
    kosis_population.run(config=a.config, out=a.out)


def _cmd_kosis_discover(a: argparse.Namespace) -> None:
    from lgstats.sources.kosis.client import discover
    df = discover(a.keyword, start=a.start, limit=a.limit)
    if df is None or df.empty:
        print("검색 결과 없음.")
        return
    print(df.to_string(index=False, max_rows=a.limit))


def _cmd_kosis_export(a: argparse.Namespace) -> None:
    text = json.dumps([v.to_dict() for v in DEFAULT_VARS], ensure_ascii=False, indent=2)
    if a.out.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml
            text = yaml.safe_dump(
                [v.to_dict() for v in DEFAULT_VARS],
                allow_unicode=True, sort_keys=False,
            )
        except ImportError:
            print("PyYAML 미설치 — JSON 으로 저장합니다.")
            a.out = a.out.with_suffix(".json")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8")
    print(f"기본 변수 정의 저장: {a.out}")


def main() -> None:
    p = argparse.ArgumentParser(prog="lgstats", description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    ip = sub.add_parser("industry-promotion", help="산업진흥비 패널 (lofin)")
    ip.add_argument("--raw-dir", type=Path, default=None)
    ip.add_argument("--template-only", action="store_true")
    ip.add_argument("--out", type=Path, required=True)
    ip.set_defaults(func=_cmd_industry)

    kp = sub.add_parser("kosis-population", help="KOSIS 인구·복지 패널")
    kp.add_argument("--config", type=Path, default=None)
    kp.add_argument("--out", type=Path, required=True)
    kp.set_defaults(func=_cmd_kosis_pop)

    kd = sub.add_parser("kosis-discover", help="KOSIS 통계표 키워드 검색")
    kd.add_argument("--keyword", required=True)
    kd.add_argument("--start", type=int, default=1)
    kd.add_argument("--limit", type=int, default=20)
    kd.set_defaults(func=_cmd_kosis_discover)

    ke = sub.add_parser("kosis-export-config", help="기본 KOSIS 변수 정의 저장 (YAML/JSON)")
    ke.add_argument("--out", type=Path, default=Path("configs/sources/kosis_vars.yaml"))
    ke.set_defaults(func=_cmd_kosis_export)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
