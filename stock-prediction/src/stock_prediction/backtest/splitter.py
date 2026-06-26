"""워크포워드(rolling/expanding) 시간분할.

무작위 K-fold 금지 — 시계열 누수. train/test 사이 embargo(=horizon) 공백을 둬
타깃 중첩으로 인한 누수를 차단한다.
"""
from __future__ import annotations


def walk_forward_splits(dates, train_window, test_window, step, embargo):
    """(train_idx, test_idx) 쌍을 시간순으로 생성."""
    raise NotImplementedError
