# 한국투자증권 OpenAPI 설정

KIS OpenAPI는 국내·미국 주식 시세와 주문을 모두 지원하며, **모의투자(paper)** 와 **실전(live)** 두 환경을 별도 키로 운영한다.

## 절차

1. **계좌 개설**
   - 한국투자증권 비대면 계좌 개설 (실전용)
   - https://securities.koreainvestment.com 에서 모의투자 계좌 별도 신청

2. **OpenAPI 신청**
   - https://apiportal.koreainvestment.com → 로그인 → "Open API 신청"
   - **APP_KEY**, **APP_SECRET** 발급 (모의·실전 각각 별도)

3. **`.env` 작성**
   ```
   KIS_PAPER_APP_KEY=...
   KIS_PAPER_APP_SECRET=...
   KIS_PAPER_ACCOUNT_NO=50123456-01
   KIS_LIVE_APP_KEY=...
   KIS_LIVE_APP_SECRET=...
   KIS_LIVE_ACCOUNT_NO=12345678-01
   KIS_ENV=paper                        # 처음엔 반드시 paper
   ```

4. **권장 라이브러리** (이미 `[broker]` extra에 미포함, 선택 설치)
   - [`mojito`](https://github.com/sharebook-kr/mojito) — 가장 가벼움
   - [`pykis`](https://github.com/Soju06/python-kis) — 비동기 지원

5. **모의투자 검증 체크리스트**
   - [ ] 시세 조회 성공 (`get_quote`)
   - [ ] 매수 주문 → 체결 확인
   - [ ] 매도 주문 → 체결 확인
   - [ ] 잔고 조회 정확성
   - [ ] 미국주식 매수/매도 (별도 환전 필요)

## 주의

- 실전 키는 절대 git에 커밋 금지. `.gitignore`로 `.env` 보호 확인.
- 미국 주식은 환전 단계가 추가됨. KIS_BROKER 어댑터에서 처리 또는 사전 환전.
- 모의서버는 실전과 일부 응답 스키마/제한이 다름 → 통합 테스트 시 둘 다 검증.
