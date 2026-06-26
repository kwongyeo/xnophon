"""data/raw/fundamentals_old/ (FY2020-2022)를 data/raw/fundamentals/ 연간 파일에 병합.

회계연도(fiscal_year) 기준 중복 제거하고 연도순 정렬. shares_outstanding 등 메타는
기존(main) 파일 값을 유지. 멱등(idempotent) — 여러 번 실행해도 안전.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "data" / "raw" / "fundamentals"
OLD = ROOT / "data" / "raw" / "fundamentals_old"


def main() -> None:
    if not OLD.exists():
        print("fundamentals_old 없음 — 병합할 것 없음")
        return
    merged = 0
    for f in sorted(OLD.glob("*.json")):
        code = f.stem
        main_f = MAIN / f"{code}.json"
        old = json.loads(f.read_text(encoding="utf-8"))
        if not main_f.exists():
            main_f.write_text(json.dumps(old, ensure_ascii=False))
            merged += 1
            continue
        m = json.loads(main_f.read_text(encoding="utf-8"))
        by_year = {r["fiscal_year"]: r for r in m.get("reports", [])}
        for r in old.get("reports", []):
            by_year.setdefault(r["fiscal_year"], r)  # 기존 우선, 없는 연도만 추가
        m["reports"] = [by_year[y] for y in sorted(by_year)]
        main_f.write_text(json.dumps(m, ensure_ascii=False))
        merged += 1
    print(f"병합 완료: {merged}개 종목")


if __name__ == "__main__":
    main()
