"""워크포워드(rolling) 시간분할.

무작위 K-fold 금지 — 시계열 누수. train 다음에 embargo(공백)를 두고 test 를 배치해
타깃 horizon 중첩으로 인한 누수를 차단한다.

  |---- train_window ----|-- embargo --|-- test_window --|
                                       ^ 여기부터 예측 평가
  다음 폴드는 step 만큼 앞으로 이동(rolling).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Fold:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def walk_forward_splits(dates, train_window: int, test_window: int,
                        step: int, embargo: int = 0) -> list[Fold]:
    """정렬된 고유 거래일을 받아 (train/test 경계) 폴드 목록을 만든다.

    단위는 '거래일 수'. embargo 거래일만큼 train 종료와 test 시작 사이를 비운다.
    """
    uniq = pd.DatetimeIndex(
        pd.Series(pd.to_datetime(dates)).drop_duplicates().sort_values()
    )
    folds: list[Fold] = []
    n = len(uniq)
    start = 0
    while True:
        tr_end = start + train_window
        te_start = tr_end + embargo
        te_end = te_start + test_window
        if te_end > n:
            break
        folds.append(Fold(
            train_start=uniq[start], train_end=uniq[tr_end - 1],
            test_start=uniq[te_start], test_end=uniq[te_end - 1],
        ))
        start += step
    return folds


def assign_fold_masks(df: pd.DataFrame, fold: Fold, date_col: str = "date"):
    """프레임에서 (train_mask, test_mask)를 날짜 경계로 만든다."""
    d = pd.to_datetime(df[date_col])
    train = (d >= fold.train_start) & (d <= fold.train_end)
    test = (d >= fold.test_start) & (d <= fold.test_end)
    return train.to_numpy(), test.to_numpy()
