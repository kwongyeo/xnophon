"""lr-outline — 주제 + 인용 풀에서 주제 맞춤 목차(개요)를 생성한다.

고정된 4섹션 템플릿 대신, Claude가 연구주제와 인용 풀의 흐름에 맞춰
절·소절 목차를 설계한다. 결과는 사람이 먼저 검토·수정할 수 있도록
``outline.md``(가독용) + ``outline.json``(기계용)으로 저장하고, 이후
``lr-draft``가 이 목차를 그대로 따라 본문을 작성한다.

    lr-export "주제어"            # 인용 풀 생성
    lr-outline --topic "주제어"   # outline.md / outline.json 생성 (ANTHROPIC_API_KEY 필요)

목차 자료구조(canonical):

    {"title": "<제목>",
     "sections": [{"heading": "서론", "subsections": ["...", ...]}, ...]}

프롬프트 구성·파싱·렌더링(순수 함수)과 네트워크 호출(generate_outline)을
분리해 오프라인 단위 테스트가 가능하다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from literature_review import config
from literature_review.writing import citations, draft

DEFAULT_MODEL = config.DEFAULT_MODEL

# 고정 기본 목차 — API 키가 없을 때의 결정적 폴백.
DEFAULT_SECTIONS: list[dict[str, Any]] = [
    {"heading": "서론", "subsections": []},
    {
        "heading": "선행연구(Related Work)",
        "subsections": ["한국(KR) 연구 동향", "미국(US) 연구 동향", "비교 및 시사점"],
    },
    {"heading": "본론", "subsections": []},
    {"heading": "결론", "subsections": []},
]

_DEFAULT_SYSTEM = (
    "너는 학술 논문의 목차를 설계하는 연구 보조자다. 연구주제와 인용 풀에 맞춰 "
    "한국어 학술 논문 목차를 JSON으로만 출력한다. 최상위 절은 4~6개이며 '서론'으로 "
    "시작해 '결론'으로 끝나고, '선행연구' 절 안에 한국(KR)·미국(US) 동향을 대비하는 "
    "소절을 둔다. 출력은 "
    '{"title": "...", "sections": [{"heading": "...", "subsections": ["..."]}]} '
    "스키마의 JSON 하나뿐이며 설명·코드펜스를 붙이지 않는다."
)


def default_outline(topic: str) -> dict[str, Any]:
    """주제 라벨을 단 기본 목차(깊은 복사)."""
    return {
        "title": topic,
        "sections": [
            {"heading": s["heading"], "subsections": list(s["subsections"])}
            for s in DEFAULT_SECTIONS
        ],
    }


# 골격 폴백은 기본 목차와 동일.
skeleton_outline = default_outline


def section_headings(outline: dict[str, Any]) -> list[str]:
    return [s.get("heading", "") for s in outline.get("sections", []) if s.get("heading")]


def load_system_prompt() -> str:
    return config.load_prompt("outline_ko.md", _DEFAULT_SYSTEM).strip()


def build_messages(topic: str, items: list[dict[str, Any]]) -> tuple[str, str]:
    """(system, user) 프롬프트 구성. user에 주제 + 인용 풀 요약을 담는다."""
    refs = "\n".join(draft.reference_lines(items))
    system = load_system_prompt()
    user = (
        f"# 연구주제\n{topic}\n\n"
        f"# 인용 풀(주제 흐름 참고용)\n{refs}\n\n"
        f"위 주제와 인용 풀에 맞는 논문 목차를 JSON으로 출력하라."
    )
    return system, user


def normalize_outline(data: dict[str, Any], topic: str = "") -> dict[str, Any]:
    """파싱 결과를 canonical 구조로 정규화(누락 필드 보정)."""
    sections = []
    for s in data.get("sections") or []:
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading", "")).strip()
        if not heading:
            continue
        subs = [str(x).strip() for x in (s.get("subsections") or []) if str(x).strip()]
        sections.append({"heading": heading, "subsections": subs})
    if not sections:
        raise ValueError("목차에 유효한 섹션이 없습니다.")
    return {"title": str(data.get("title") or topic).strip() or topic, "sections": sections}


def parse_outline_response(text: str, topic: str = "") -> dict[str, Any]:
    """LLM 응답에서 JSON 목차를 관대하게 추출·정규화한다."""
    if not text:
        raise ValueError("빈 응답")
    # 코드펜스/잡텍스트가 섞여도 첫 '{' ~ 마지막 '}' 구간을 시도.
    candidate = text.strip()
    if not candidate.startswith("{"):
        m = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not m:
            raise ValueError("JSON을 찾을 수 없습니다.")
        candidate = m.group(0)
    data = json.loads(candidate)
    return normalize_outline(data, topic)


def outline_to_markdown(outline: dict[str, Any]) -> str:
    """목차를 사람이 검토하기 좋은 번호 매김 Markdown으로 렌더링."""
    lines = [f"# {outline.get('title', '(제목 없음)')}", "", "## 목차", ""]
    for i, sec in enumerate(outline.get("sections", []), 1):
        lines.append(f"{i}. {sec.get('heading', '')}")
        for j, sub in enumerate(sec.get("subsections", []), 1):
            lines.append(f"   {i}.{j} {sub}")
    lines.append("")
    return "\n".join(lines)


def generate_outline(
    topic: str, items: list[dict[str, Any]], model: str = DEFAULT_MODEL
) -> dict[str, Any]:
    """Claude로 주제 맞춤 목차를 생성한다(ANTHROPIC_API_KEY 필요)."""
    import anthropic

    system, user = build_messages(topic, items)
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return parse_outline_response(text, topic)


def load_outline(path: Path) -> dict[str, Any]:
    return normalize_outline(json.loads(path.read_text()))


def write_outline(outline: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"json": out_dir / "outline.json", "md": out_dir / "outline.md"}
    paths["json"].write_text(json.dumps(outline, ensure_ascii=False, indent=2))
    paths["md"].write_text(outline_to_markdown(outline))
    return paths


def main():
    import os

    parser = argparse.ArgumentParser(
        description="주제 + 인용 풀에서 주제 맞춤 논문 목차를 생성한다."
    )
    parser.add_argument("--topic", help="연구주제(미지정 시 인용 풀 경로 기반).")
    parser.add_argument(
        "--from-pool",
        default="results/citations.csl.json",
        help="입력 CSL-JSON 인용 풀 경로.",
    )
    parser.add_argument("--out-dir", default=None, help="출력 디렉터리(기본 인용 풀과 같은 폴더).")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--skeleton", action="store_true", help="LLM 대신 기본 목차만 생성."
    )
    args = parser.parse_args()

    pool_path = Path(args.from_pool)
    if not pool_path.exists():
        raise SystemExit(
            f"{pool_path} 를 찾을 수 없습니다. 먼저 lr-export 로 인용 풀을 생성하세요."
        )
    items = json.loads(pool_path.read_text())
    topic = args.topic or "(주제 미지정)"
    out_dir = Path(args.out_dir) if args.out_dir else pool_path.parent

    if args.skeleton or not os.environ.get("ANTHROPIC_API_KEY"):
        if not args.skeleton:
            print("ANTHROPIC_API_KEY 미설정 — 기본 목차를 생성합니다.")
        outline = skeleton_outline(topic)
    else:
        print(f"Claude({args.model})로 목차 설계 중…")
        try:
            outline = generate_outline(topic, items, model=args.model)
        except Exception as e:  # noqa: BLE001
            print(f"목차 생성 실패 → 기본 목차로 대체: {e}")
            outline = skeleton_outline(topic)

    paths = write_outline(outline, out_dir)
    print(f"완료: {len(outline['sections'])}개 절")
    for label, path in paths.items():
        print(f"  - {path}")


if __name__ == "__main__":
    main()
