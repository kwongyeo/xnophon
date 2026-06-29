# 주탐주예 (主探主豫) — 주식탐색과 주가예측

이 디렉터리(`stock-prediction/`)는 **주탐주예** 알고리즘이다. 한국(KRX)·미국 주식을
가격·재무·거시·심리 데이터로 탐색하고 단기~중기 수익률을 예측하는 연구 파이프라인.

> ⚠️ 연구·교육용. 투자자문/수익보장 아님. 모델 스킬은 약하다(검증 결과 아래).

## 빠른 재개 (다음 세션에서)
1. 이 파일과 `README.md`를 읽는다.
2. 환경 준비: `cd stock-prediction && pip install -e .` (또는 `PYTHONPATH=src python -m ...`)
3. 데이터는 `data/raw/*`(gitignore)라 **새 환경엔 없을 수 있음** → 필요 시 MCP로 재수집
   (UsStockInfo=시세/US재무, opendart=KR재무, NaverSearch=검색트렌드). 수집 방식은
   기존 커밋 히스토리/`docs/` 참고. 코드는 `data/raw/{universe,fundamentals,fundamentals_q,macro,meta,sentiment_kr}/`를 읽음.
4. 핵심 산출물 재현: `sp-final`(사다리), `sp-picks 60`(랭킹), `sp-paper report`(모의투자).

## 주요 명령 (pyproject [project.scripts])
- `sp-poc` 0단계 데이터 검증 · `sp-baseline` 1단계 가격 베이스라인
- `sp-horizon` 타깃기간 스윕 · `sp-longshort` 롱숏 · `sp-stage2` 펀더멘털
- `sp-stage3` 분기펀더+거시 · `sp-regime` 레짐필터 · `sp-neutral` 시장중립
- `sp-sector` 섹터중립 · `sp-stage4` 검색관심도 · `sp-final` 최종 ablation
- `sp-picks [h]` 현재 랭킹(기본40, 예 `sp-picks 60`) · `sp-paper {record|report [stop%]}` 모의투자

## 구조
- `src/stock_prediction/`: data/collectors, features(technical·fundamental·macro·sentiment·sector),
  models(baseline·tree), backtest(splitter·engine), evaluation, 각 단계 러너, picks/paper_trade.
- `docs/`: 단계별 결과·정직한 한계 문서(여기에 모든 실험 결론이 있음).
- `paper_trades/`: 모의투자 장부·산출물(gitignore).

## 검증된 결론 (정직)
- 가격 피처만으로는 신호 없음(IC≈0). **펀더멘털은 중장기(20·60일)에 유효**(RankIC↑).
- **시장중립 롱숏**이 신호를 살리고 드로다운을 줄임. **분기 펀더멘털**이 추가 개선.
- **레짐필터·섹터중립·검색관심도는 효과 없음/비결정적**(2년 샘플의 레짐필터 호조는
  5년 검증서 과최적화로 판명). 최종 시장중립 롱숏도 위험조정 성과는 벤치마크와 비슷.
- 자세한 수치·한계는 `docs/*-results.md` 와 `docs/longer-history-validation.md`.

## 작업 규칙
- 데이터 누수 금지: 피처는 시점 t 이전만, 재무는 disclosed_at PIT, 워크포워드+embargo.
- 변경 시 `PYTHONPATH=src python -m pytest tests/ -q` 통과 확인.
- 결과는 항상 정직한 한계와 함께 보고(과최적화·소표본 경계).
- 개발 브랜치: `claude/stock-prediction-algorithm-0qw2rd`.
