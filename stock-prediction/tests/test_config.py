"""설정 로딩 스모크 테스트."""
from stock_prediction.config import load_config


def test_load_config_has_required_sections():
    cfg = load_config()
    for key in ("universe", "period", "target", "split", "features", "model", "backtest"):
        assert key in cfg, f"config.yaml에 '{key}' 섹션이 없습니다"


def test_target_horizon_matches_embargo():
    # 누수 방지: embargo는 타깃 horizon 이상이어야 한다.
    cfg = load_config()
    assert cfg["split"]["embargo"] >= cfg["target"]["horizon"]
