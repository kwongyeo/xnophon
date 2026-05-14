"""한국·미국 선행연구 챗봇.

사용법:
    python chatbot.py

ANTHROPIC_API_KEY 환경변수가 있으면 Claude Opus 4.7이 자연어로 대화하며
OpenAlex 도구를 호출해 한국(KR)·미국(US) 논문을 검색·비교·요약한다.
없으면 간단한 명령 기반 REPL로 동작한다.

명령(LLM 모드 없을 때):
    <검색어>            주제 검색 (KR/US 동시)
    /year <연도>        발행 연도 하한 설정
    /count <N>          국가별 결과 수 설정
    /save <이름>        직전 검색 결과를 results/<이름>.md 로 저장
    /help               도움말
    /quit               종료
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from xnophon.sources import openalex

DEFAULT_FROM_YEAR = 2020
DEFAULT_PER_COUNTRY = 15
RESULTS_DIR = Path("results")


def search_openalex(query: str, country_code: str, from_year: int, per_page: int) -> list[dict]:
    return openalex.search(query, country_code, from_year, per_page)


def format_table(rows: list[dict], header: str) -> str:
    if not rows:
        return f"### {header}\n\n(결과 없음)\n"
    lines = [f"### {header} ({len(rows)}편)", ""]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i}. **{r['title']}** — {r['authors']} ({r['year']}) — "
            f"{r['venue']} — 인용 {r['cited_by']} — <{r['url']}>"
        )
    return "\n".join(lines) + "\n"


def save_markdown(name: str, query: str, kr: list[dict], us: list[dict]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{name}.md"
    body = (
        f"# 선행연구: {query}\n\n"
        + format_table(kr, "한국 (KR)")
        + "\n"
        + format_table(us, "미국 (US)")
    )
    path.write_text(body)
    return path


# --- 모드 1: LLM 챗봇 (ANTHROPIC_API_KEY 있을 때) ---

def run_llm_chatbot():
    import anthropic
    from anthropic import beta_tool

    @beta_tool
    def search_papers(query: str, country: str, from_year: int = 2020, count: int = 15) -> str:
        """OpenAlex에서 특정 국가의 논문을 검색한다.

        Args:
            query: 검색어 (영문 권장).
            country: ISO 국가 코드. 'KR'(한국) 또는 'US'(미국).
            from_year: 발행 연도 하한.
            count: 반환할 최대 논문 수 (1-30).
        """
        rows = search_openalex(query, country, from_year, min(max(count, 1), 30))
        return json.dumps(rows, ensure_ascii=False)

    client = anthropic.Anthropic()
    system = (
        "너는 한국과 미국의 학술 논문을 비교·요약하는 선행연구(문헌검토) 보조 챗봇이다. "
        "사용자가 주제를 제시하면 search_papers 도구로 KR과 US 양국 논문을 각각 검색해 "
        "인용수·연구 동향·방법론 차이를 한국어로 비교 요약한다. "
        "각 논문은 [저자(연도)] 형식으로 인용하고, 마지막에 OpenAlex 링크 목록을 제공한다. "
        "검색 결과가 비면 검색어를 영문으로 재시도하거나 사용자에게 재질의한다."
    )
    history: list[dict] = []
    print("=" * 60)
    print("한·미 선행연구 챗봇 (Claude Opus 4.7 + OpenAlex)")
    print("자연어로 주제를 입력하세요. /quit 으로 종료.")
    print("=" * 60)

    while True:
        try:
            user = input("\n나 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break

        turn_messages = history + [{"role": "user", "content": user}]
        runner = client.beta.messages.tool_runner(
            model="claude-opus-4-7",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=[search_papers],
            messages=turn_messages,
        )
        final_text_parts = []
        for message in runner:
            for block in message.content:
                if block.type == "text":
                    final_text_parts.append(block.text)
                elif block.type == "tool_use":
                    print(f"  [도구 호출: {block.name}({json.dumps(block.input, ensure_ascii=False)})]")
        final_text = "\n".join(final_text_parts).strip() or "(응답 없음)"
        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": final_text})
        print("\n챗봇 >", final_text)


# --- 모드 2: 명령 기반 REPL (API 키 없을 때) ---

def run_simple_repl():
    state = {
        "from_year": DEFAULT_FROM_YEAR,
        "per_country": DEFAULT_PER_COUNTRY,
        "last_query": None,
        "last_kr": [],
        "last_us": [],
    }
    print("=" * 60)
    print("한·미 선행연구 챗봇 (간이 모드, OpenAlex 직접 검색)")
    print("ANTHROPIC_API_KEY 를 설정하면 LLM 대화 모드로 자동 전환됩니다.")
    print(f"기본값: from_year={state['from_year']}, per_country={state['per_country']}")
    print("/help 도움말, /quit 종료")
    print("=" * 60)

    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if line == "/help":
            print(__doc__)
            continue
        if line.startswith("/year "):
            try:
                state["from_year"] = int(line.split()[1])
                print(f"from_year = {state['from_year']}")
            except (ValueError, IndexError):
                print("사용법: /year 2022")
            continue
        if line.startswith("/count "):
            try:
                state["per_country"] = max(1, min(50, int(line.split()[1])))
                print(f"per_country = {state['per_country']}")
            except (ValueError, IndexError):
                print("사용법: /count 20")
            continue
        if line.startswith("/save "):
            name = line.split(maxsplit=1)[1].strip().replace("/", "_")
            if not state["last_query"]:
                print("저장할 검색 결과가 없습니다.")
                continue
            path = save_markdown(name, state["last_query"], state["last_kr"], state["last_us"])
            print(f"저장: {path}")
            continue

        query = line
        print(f"\n검색 중: '{query}' (from {state['from_year']}, {state['per_country']}편/국가)")
        try:
            kr = search_openalex(query, "KR", state["from_year"], state["per_country"])
            us = search_openalex(query, "US", state["from_year"], state["per_country"])
        except Exception as e:
            print(f"오류: {e}")
            continue
        state["last_query"], state["last_kr"], state["last_us"] = query, kr, us
        print()
        print(format_table(kr, "한국 (KR)"))
        print(format_table(us, "미국 (US)"))
        print(f"(저장하려면 /save <이름>)")


def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        run_llm_chatbot()
    else:
        run_simple_repl()


if __name__ == "__main__":
    main()
