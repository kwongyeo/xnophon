"""주탐주예 랭킹을 텔레그램으로 발송.

⚠️ 연구·교육용. 투자자문/수익보장 아님.

준비물(사용자가 직접 발급, .env 에 저장):
  TELEGRAM_BOT_TOKEN   — @BotFather 에서 /newbot 으로 봇 생성 시 받는 토큰
  TELEGRAM_CHAT_ID     — 본인 chat id. 봇에게 아무 말이나 보낸 뒤
                         https://api.telegram.org/bot<토큰>/getUpdates 의 chat.id 확인

사용:
  sp-notify              # 기본 3개월(60거래일) 랭킹 발송(토큰 있으면 발송, 없으면 dry-run)
  sp-notify 20           # 1개월 랭킹
  sp-notify 60 --dry-run # 발송하지 않고 메시지만 출력(검증용)

cron(매월 1일 09:05 발송):
  5 9 1 * * cd /path/to/stock-prediction && PYTHONPATH=src python -m stock_prediction.notify_telegram 60 >> paper_trades/notify.log 2>&1
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv():
    """.env 가 있으면 환경변수로 로드(간단 파서)."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def build_message(horizon: int) -> str:
    from .picks import rank_asof
    months = round(horizon / 21)
    picks = rank_asof(horizon=horizon)
    if picks.empty:
        return "주탐주예: 추천 산출 실패(데이터 부족)."
    lines = [f"📈 <b>주탐주예 {months}개월(≈{horizon}거래일) 랭킹</b>",
             "<i>연구·교육용 · 투자자문/수익보장 아님</i>", ""]
    for mk, label, flag in (("KR", "한국", "🇰🇷"), ("US", "미국", "🇺🇸")):
        sub = picks[picks["market"] == mk].sort_values("pred", ascending=False)
        if sub.empty:
            continue
        asof = sub["entry_date"].iloc[0]
        lines.append(f"{flag} <b>{label}</b> (기준 {asof})")
        for i, (_, r) in enumerate(sub.iterrows(), 1):
            lines.append(f"  {i}. {r['ticker']} {r['name']}")
        lines.append("")
    lines.append("순위는 모델 상대선호도(예측 % 비신뢰). 분산·리스크관리 필수.")
    return "\n".join(lines)


def send(text: str, token: str, chat_id: str) -> bool:
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text,
                                    "parse_mode": "HTML",
                                    "disable_web_page_preview": True}, timeout=30)
    ok = resp.status_code == 200 and resp.json().get("ok", False)
    if not ok:
        print(f"발송 실패 {resp.status_code}: {resp.text[:200]}")
    return ok


def main() -> None:
    _load_dotenv()
    args = sys.argv[1:]
    horizon = next((int(a) for a in args if a.isdigit()), 60)
    dry = "--dry-run" in args
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    text = build_message(horizon)
    if dry or not (token and chat_id):
        if not (token and chat_id) and not dry:
            print("⚠️ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 미설정 → dry-run으로 출력만 합니다.")
            print("   .env 에 두 값을 넣으면 실제 발송됩니다(방법: 이 파일 상단 주석 참조).\n")
        print(text.replace("<b>", "").replace("</b>", "")
                  .replace("<i>", "").replace("</i>", ""))
        return
    if send(text, token, chat_id):
        print(f"텔레그램 발송 완료 (chat_id={chat_id[:4]}…, {horizon}거래일).")


if __name__ == "__main__":
    main()
