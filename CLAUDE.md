# 저장소 안내 (xnophon)

이 저장소에는 두 프로젝트가 있다:

- **`stock-prediction/` — 주탐주예 (主探主豫, 주식탐색과 주가예측)** ★
  한국·미국 주식 수익률 예측 연구 파이프라인. 상세 맥락·명령·결론은
  **[`stock-prediction/CLAUDE.md`](stock-prediction/CLAUDE.md)** 에 있다. "주탐주예"
  작업 요청 시 그 파일을 먼저 읽고 `stock-prediction/`에서 작업한다.
  빠른 예: `cd stock-prediction && pip install -e .` 후 `PYTHONPATH=src python -m stock_prediction.picks 60`.

- 루트(`src/`, `web/`) — literature-review(문헌검토) 도구(별개 프로젝트).

> 데이터(`stock-prediction/data/raw/`)는 gitignore라 새 클론엔 없을 수 있음 → 필요 시
> MCP(UsStockInfo·opendart·NaverSearch)로 재수집 후 분석.
