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
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text,
                                        "parse_mode": "HTML",
                                        "disable_web_page_preview": True}, timeout=30)
    except requests.exceptions.RequestException as e:
        msg = str(e)
        if "403" in msg or "proxy" in msg.lower():
            print("발송 실패: 이 환경은 api.telegram.org 접속이 차단됨(클라우드 네트워크 정책).")
            print("  → 로컬 PC에서 실행하면 발송됩니다.")
        else:
            print(f"발송 실패(네트워크): {msg[:160]}")
        return False
    ok = resp.status_code == 200 and resp.json().get("ok", False)
    if not ok:
        print(f"발송 실패 {resp.status_code}: {resp.text[:200]} "
              "(토큰/chat_id 확인 — 404=토큰오타, 400=chat_id, 401=bot접두사)")
    return ok


def _creds():
    return os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


def _plain(text: str) -> str:
    for tag in ("<b>", "</b>", "<i>", "</i>"):
        text = text.replace(tag, "")
    return text


def cmd_status() -> None:
    token, chat_id = _creds()
    configured = bool(token and chat_id)
    print(f'{{ "telegram_configured": {str(configured).lower()} }}')
    if not configured:
        miss = [n for n, v in (("TELEGRAM_BOT_TOKEN", token),
                               ("TELEGRAM_CHAT_ID", chat_id)) if not v]
        print(f"  미설정: {', '.join(miss)} → .env 에 추가(발급법: .env.example).")
    else:
        print(f"  token={token[:6]}…  chat_id={chat_id}")


def cmd_test() -> None:
    token, chat_id = _creds()
    if not (token and chat_id):
        print("⚠️ 미설정 — sp-notify status 참고. 발송 불가."); return
    if send("주탐주예 notify test ✓", token, chat_id):
        print("🎯 텔레그램 발송 성공 — 앱에서 'notify test' 메시지 확인.")


def main() -> None:
    _load_dotenv()
    args = sys.argv[1:]
    sub = args[0] if args else ""

    if sub == "status":
        cmd_status(); return
    if sub == "test":
        cmd_test(); return
    if sub == "send":                       # sp-notify send --subject .. --body ..
        token, chat_id = _creds()
        def opt(name):
            return args[args.index(name) + 1] if name in args else ""
        subj, body = opt("--subject"), opt("--body")
        text = (f"<b>{subj}</b>\n{body}" if subj else body) or "(빈 메시지)"
        if token and chat_id and "--dry-run" not in args:
            if send(text, token, chat_id):
                print("발송 완료.")
        else:
            print(_plain(text))
        return

    # 기본: 랭킹 발송
    horizon = next((int(a) for a in args if a.isdigit()), 60)
    dry = "--dry-run" in args
    token, chat_id = _creds()
    text = build_message(horizon)
    if dry or not (token and chat_id):
        if not (token and chat_id) and not dry:
            print("⚠️ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 미설정 → dry-run 출력만.")
            print("   stock-lab에서 쓰던 동일 값을 .env 에 넣으면 실제 발송됩니다.\n")
        print(_plain(text))
        return
    if send(text, token, chat_id):
        print(f"텔레그램 발송 완료 (chat_id={chat_id[:4]}…, {horizon}거래일).")


if __name__ == "__main__":
    main()
