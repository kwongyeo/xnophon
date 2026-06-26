"""단계1 베이스라인 — 가격/기술적 피처만으로 횡단면 수익률 예측 + 워크포워드 백테스트.

흐름:
  유니버스 시세(data/raw/universe/*.json) 정규화
   → 기술적 피처 + 미래 h일 수익률 타깃
   → 날짜별 횡단면 표준화(zscore)
   → 워크포워드 분할(rolling, embargo)
   → 모델별 OOS 예측(Momentum / Ridge / LightGBM)
   → 상위 K종목 롱 백테스트 vs 동일가중 벤치마크

목적: '가격 정보만으로' 달성 가능한 기준선 성능을 측정한다.
이후 단계(펀더멘털/거시/심리)는 이 기준선을 이겨야 의미가 있다.

실행: sp-baseline   (또는  python -m stock_prediction.baseline)
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# LightGBM/sklearn 의 "feature names" UserWarning 은 numpy 입력 시 무해 — 리포트 가독성 위해 억제
warnings.filterwarnings("ignore", category=UserWarning)

from .backtest import engine
from .backtest.splitter import assign_fold_masks, walk_forward_splits
from .config import load_config
from .data.collectors import yfinance_us
from .features.technical import FEATURE_COLUMNS, add_technical_features
from .poc import build_target

UNIVERSE = Path(__file__).resolve().parents[2] / "data" / "raw" / "universe"
PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


def load_universe_panel(horizon: int) -> pd.DataFrame:
    """유니버스 원본 시세 → 피처 + 타깃 패널(long)."""
    files = sorted(UNIVERSE.glob("*.json"))
    if not files:
        raise FileNotFoundError(
            f"유니버스 데이터 없음: {UNIVERSE} — 먼저 시세를 수집하세요(README 단계1)."
        )
    frames = []
    for f in files:
        ticker = f.stem
        try:
            px = yfinance_us.normalize_price(yfinance_us.load_raw(f), ticker)
        except Exception:
            continue
        if len(px) < 60:
            continue
        px = add_technical_features(px)
        px = build_target(px, horizon)
        frames.append(px)
    if not frames:
        raise RuntimeError("정규화 가능한 종목이 없습니다.")
    return pd.concat(frames, ignore_index=True)


def cross_sectional_zscore(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """날짜별 횡단면 표준화. 그 날의 단면만 사용 → 누수 없음."""
    df = df.copy()
    g = df.groupby("date")
    for c in cols:
        mean = g[c].transform("mean")
        std = g[c].transform("std")
        df[c] = (df[c] - mean) / std.replace(0, np.nan)
    return df


def _fit_windows(cfg: dict, n_dates: int, horizon: int):
    """config 윈도가 데이터보다 크면 PoC 규모로 자동 축소."""
    s = cfg["split"]
    tr, te, st = s["train_window"], s["test_window"], s["step"]
    emb = max(s.get("embargo", horizon), horizon)
    if tr + emb + te > n_dates:
        tr, te, st = 126, 21, 21  # 6개월 학습 / 1개월 검증 (롤링)
    return tr, te, st, emb


def run_models(panel: pd.DataFrame, cfg: dict, horizon: int,
               feature_cols: list[str] | None = None,
               prefiltered: bool = False) -> dict:
    """워크포워드 OOS 예측 + 백테스트.

    feature_cols: 사용할 피처 목록(기본 가격/기술적). mom_20 은 Momentum 기준선에 필요.
    prefiltered: True면 panel이 이미 결측 제거된 공통 샘플(단계 간 공정 비교용).
    """
    target = f"target_ret_{horizon}d"
    feat = list(feature_cols or FEATURE_COLUMNS)
    data = panel.copy() if prefiltered else panel.dropna(subset=feat + [target]).copy()
    data = cross_sectional_zscore(data, feat).dropna(subset=feat)

    dates = np.sort(data["date"].unique())
    tr, te, st, emb = _fit_windows(cfg, len(dates), horizon)
    folds = walk_forward_splits(dates, tr, te, st, emb)
    if not folds:
        raise RuntimeError(f"폴드 생성 실패: 거래일 {len(dates)}개로 부족.")

    from .models.baseline import MomentumBaseline, RidgeModel
    from .models.tree import TreeModel

    mom_idx = feat.index("mom_20") if "mom_20" in feat else 0
    builders = {
        "Momentum": lambda: MomentumBaseline(mom_index=mom_idx),
        "Ridge": lambda: RidgeModel(alpha=1.0),
        "LightGBM": lambda: TreeModel(cfg["model"]["params"], seed=cfg["model"]["seed"]),
    }
    preds = {name: [] for name in builders}

    for fold in folds:
        tr_mask, te_mask = assign_fold_masks(data, fold)
        Xtr, ytr = data.loc[tr_mask, feat].to_numpy(), data.loc[tr_mask, target].to_numpy()
        test = data.loc[te_mask, ["date", "ticker", target]].copy()
        Xte = data.loc[te_mask, feat].to_numpy()
        if len(Xtr) < 30 or len(Xte) == 0:
            continue
        for name, build in builders.items():
            model = build().fit(Xtr, ytr)
            out = test.rename(columns={target: "fwd_ret"}).copy()
            out["pred"] = model.predict(Xte)
            preds[name].append(out)

    results = {}
    for name, parts in preds.items():
        if not parts:
            continue
        pred_df = pd.concat(parts, ignore_index=True)
        results[name] = engine.run_backtest(
            pred_df, horizon=horizon,
            top_k=cfg["backtest"]["top_k"], cost_bps=cfg["backtest"]["cost_bps"],
        )
    return {"results": results, "n_dates": len(dates), "n_folds": len(folds),
            "windows": (tr, te, st, emb), "n_tickers": data["ticker"].nunique()}


def main() -> None:
    cfg = load_config()
    h = cfg["target"]["horizon"]
    k = cfg["backtest"]["top_k"]
    PROCESSED.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("단계1 베이스라인 — 가격/기술적 피처 → 횡단면 예측 + 워크포워드 백테스트")
    print("=" * 70)

    panel = load_universe_panel(h)
    out = run_models(panel, cfg, h)
    tr, te, st, emb = out["windows"]
    print(f"\n유니버스: {out['n_tickers']}종목 · 거래일 {out['n_dates']}일 · "
          f"폴드 {out['n_folds']}개")
    print(f"워크포워드: train={tr} / embargo={emb} / test={te} / step={st} (거래일)")
    print(f"타깃: 미래 {h}일 수익률 · 백테스트: 상위 {k}종목 동일가중 롱, "
          f"비용 {cfg['backtest']['cost_bps']}bp\n")

    # 벤치마크는 모델 무관 동일 — 첫 결과에서 한 번만 출력
    bench = None
    print(f"{'모델':<10} {'IC':>7} {'RankIC':>8} {'방향적중':>8} "
          f"{'전략수익':>9} {'샤프':>7} {'MDD':>8}")
    print("-" * 66)
    for name, r in out["results"].items():
        if "error" in r:
            print(f"{name:<10} {r['error']}")
            continue
        s = r["strategy"]
        bench = r["benchmark"]
        print(f"{name:<10} {r['ic']:>7.3f} {r['rank_ic']:>8.3f} "
              f"{r['dir_acc']:>7.1%} {s['total_return']:>8.1%} "
              f"{s['sharpe']:>7.2f} {s['mdd']:>7.1%}")
    if bench:
        print("-" * 66)
        print(f"{'벤치마크':<10} {'':>7} {'':>8} {'':>8} "
              f"{bench['total_return']:>8.1%} {bench['sharpe']:>7.2f} {bench['mdd']:>7.1%}")

    # 곡선 저장(LightGBM 우선, 없으면 첫 모델)
    pick = out["results"].get("LightGBM") or next(iter(out["results"].values()), None)
    if pick and "curve" in pick:
        pick["curve"].to_parquet(PROCESSED / "baseline_equity_curve.parquet", index=False)
        print(f"\n저장 → {PROCESSED}/baseline_equity_curve.parquet")

    print("\n해석: IC>0·RankIC>0 이면 예측에 신호가 있다는 뜻. 전략수익이 벤치마크보다 "
          "높고 샤프가 양호하면 단계1 기준선 통과.")
    print("다음 단계: 펀더멘털(단계2) 피처를 추가해 이 기준선 대비 개선 여부를 검증.")


if __name__ == "__main__":
    main()
