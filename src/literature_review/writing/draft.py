"""lr-draft — 인용 풀에서 Claude로 논문 초안을 생성한다.

`lr-export`가 만든 인용 풀(`results/citations.csl.json`)을 입력으로,
Claude(Opus)가 **풀에 있는 문헌만** 근거로 한국어 학술 초안을 작성한다.
환각 인용을 막기 위해 풀 밖 문헌 인용을 금지하고, 인용은 BibTeX 키(`[key]`)로
달도록 강제한다.

    lr-export "large language model education" --per-country 30
    lr-draft --topic "LLM을 활용한 교육"            # ANTHROPIC_API_KEY 필요

API 키가 없으면 풀로부터 결정적(deterministic) **골격 초안**을 생성한다(섹션
틀 + References). 이는 오프라인에서도 동작하며 단위 테스트로 검증된다.

순수 함수(`reference_lines`, `build_messages`, `skeleton_draft`)와 네트워크
호출(`generate_draft`)을 분리해 테스트가 쉽다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from literature_review import config
from literature_review.writing import citations

DEFAULT_MODEL = config.DEFAULT_MODEL

SECTIONS = ["서론", "선행연구(Related Work)", "본론", "결론"]

# 작성 지시는 assets/prompts/draft_ko.md 에서 읽고, 파일이 없으면 아래 기본값을 쓴다.
# (파일로 분리해 코드 수정 없이 문체·구조 규칙을 바꿀 수 있게 한다.)
_DEFAULT_SYSTEM = (
    "너는 학술 논문 초안을 작성하는 연구 보조자다. 다음 규칙을 반드시 지킨다.\n"
    "1) 아래 '인용 풀'에 있는 문헌만 인용한다. 풀에 없는 문헌·저자·DOI를 "
    "절대 새로 지어내지 않는다(인용 위조 금지).\n"
    "2) 모든 인용은 대괄호 BibTeX 키 형식 [key] 로 본문에 단다. 예: [kim2023large].\n"
    "3) 구성: 서론 → 선행연구(Related Work) → 본론 → 결론. 선행연구 절에서는 "
    "한국(KR)과 미국(US) 연구 동향의 차이를 반드시 대비한다.\n"
    "4) 한국어 학술 문체로 쓰고, 마지막에 '## References' 절에 본문에서 실제로 "
    "인용한 키만 [key] 목록으로 정리한다.\n"
    "5) 출력은 Markdown 한 편의 초안이며, 메타 설명 없이 본문만 출력한다."
)


def load_system_prompt() -> str:
    """작성 지시 시스템 프롬프트를 assets/prompts/draft_ko.md 에서 로드(없으면 기본값)."""
    return config.load_prompt("draft_ko.md", _DEFAULT_SYSTEM).strip()


def _ensure_ids(items: list[dict[str, Any]]) -> None:
    """각 CSL 항목에 고유 BibTeX 키(id)를 보장한다(lr-export가 이미 채웠다면 유지)."""
    used: set[str] = set()
    for item in items:
        existing = item.get("id")
        if existing and existing not in used:
            used.add(existing)
        else:
            item["id"] = citations.make_key(item, used)


def _authors_str(item: dict[str, Any]) -> str:
    names = []
    for a in item.get("author", []):
        names.append(a.get("literal") or f"{a.get('given','')} {a.get('family','')}".strip())
    return "; ".join(n for n in names if n) or "Anonymous"


def _year_str(item: dict[str, Any]) -> str:
    parts = (item.get("issued") or {}).get("date-parts") or [[]]
    return str(parts[0][0]) if parts and parts[0] else "n.d."


def reference_lines(items: list[dict[str, Any]]) -> list[str]:
    """풀의 각 문헌을 ``[key] 저자(연도). 제목. 학술지. [국가]`` 한 줄로 포맷."""
    lines = []
    for item in items:
        country = (item.get("custom") or {}).get("country", "")
        tag = f" [{country}]" if country else ""
        doi = item.get("DOI")
        doi_str = f" doi:{doi}" if doi else ""
        lines.append(
            f"[{item.get('id','?')}] {_authors_str(item)} ({_year_str(item)}). "
            f"{item.get('title','')}. {item.get('container-title','') or 'n/a'}.{tag}{doi_str}"
        )
    return lines


def build_messages(topic: str, items: list[dict[str, Any]]) -> tuple[str, str]:
    """(system, user) 프롬프트를 구성한다. 인용 위조 금지 제약을 명시."""
    refs = "\n".join(reference_lines(items))
    system = load_system_prompt()
    user = (
        f"# 주제\n{topic}\n\n"
        f"# 인용 풀 (이 목록의 [key]만 사용 가능)\n{refs}\n\n"
        f"위 인용 풀을 근거로 '{topic}'에 대한 논문 초안을 작성하라."
    )
    return system, user


def skeleton_draft(topic: str, items: list[dict[str, Any]]) -> str:
    """API 키 없이도 동작하는 결정적 골격 초안(섹션 틀 + References)."""
    refs = reference_lines(items)
    keys = " ".join(f"[{it.get('id','?')}]" for it in items)
    out = [f"# {topic}", "", "> 자동 생성된 **골격 초안**입니다. `ANTHROPIC_API_KEY`를 설정하면",
           "> `lr-draft`가 Claude로 본문을 채운 완성 초안을 생성합니다.", ""]
    for sec in SECTIONS:
        out.append(f"## {sec}")
        out.append("")
        if sec.startswith("선행연구"):
            out.append("한국(KR)과 미국(US)의 선행연구를 대비해 서술한다. 인용 가능한 문헌: " + keys)
        else:
            out.append("(작성 예정) 관련 인용: " + keys)
        out.append("")
    out.append("## References")
    out.append("")
    out.extend(f"- {line}" for line in refs)
    out.append("")
    return "\n".join(out)


def generate_draft(topic: str, items: list[dict[str, Any]], model: str = DEFAULT_MODEL) -> str:
    """Claude로 완성 초안을 생성한다(ANTHROPIC_API_KEY 필요)."""
    import anthropic

    system, user = build_messages(topic, items)
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def load_pool(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(
            f"{path} 를 찾을 수 없습니다. 먼저 lr-export 로 인용 풀을 생성하세요.\n"
            '  예) lr-export "주제어" --per-country 30'
        )
    return json.loads(path.read_text())


def main():
    import os

    parser = argparse.ArgumentParser(
        description="인용 풀(citations.csl.json)에서 Claude로 논문 초안을 생성한다."
    )
    parser.add_argument("--topic", help="논문 주제(미지정 시 인용 풀 파일명/경로 기반).")
    parser.add_argument(
        "--from-pool",
        default="results/citations.csl.json",
        help="입력 CSL-JSON 인용 풀 경로(기본 results/citations.csl.json).",
    )
    parser.add_argument("--out", default="results/draft.md", help="출력 초안 경로.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--skeleton",
        action="store_true",
        help="API 키가 있어도 골격 초안만 생성(LLM 호출 생략).",
    )
    args = parser.parse_args()

    items = load_pool(Path(args.from_pool))
    _ensure_ids(items)
    topic = args.topic or "(주제 미지정)"

    if args.skeleton or not os.environ.get("ANTHROPIC_API_KEY"):
        if not args.skeleton:
            print("ANTHROPIC_API_KEY 미설정 — 골격 초안을 생성합니다.")
        draft = skeleton_draft(topic, items)
    else:
        print(f"Claude({args.model})로 초안 생성 중… (인용 {len(items)}편)")
        draft = generate_draft(topic, items, model=args.model)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(draft)
    print(f"완료: {out_path}")


if __name__ == "__main__":
    main()
