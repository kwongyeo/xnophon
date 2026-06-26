"""End-to-end 파이프라인: 수집 → 피처 → 학습 → 백테스트 → 평가.

진입점: `sp-pipeline` (pyproject.toml [project.scripts]).
각 단계는 config.yaml 설정에 따라 동작한다.
"""
from __future__ import annotations

from .config import load_config


def main() -> None:
    cfg = load_config()
    print("[stock-prediction] 설정 로드 완료")
    print(f"  유니버스: {cfg['universe']['market']} / {cfg['universe']['index']}")
    print(f"  기간: {cfg['period']['start']} ~ {cfg['period']['end']}")
    print(f"  타깃: {cfg['target']['type']} (horizon={cfg['target']['horizon']}일)")
    print(f"  모델: {cfg['model']['type']}")
    print()
    print("다음 단계 구현 순서 (docs/data-sources.md 로드맵 참조):")
    print("  1) data.collectors.* — 가격 수집 → data/raw")
    print("  2) data.loaders.build_features_matrix — 피처 매트릭스")
    print("  3) backtest.splitter.walk_forward_splits — 시간분할")
    print("  4) models.* 학습 → backtest.engine.run_backtest")
    print("  5) evaluation.metrics — 성과 평가")


if __name__ == "__main__":
    main()
