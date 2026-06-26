"""시퀀스 모델 (LSTM/GRU/Transformer). 선택사항 — pip install .[deep] 필요.
시계열 윈도를 입력으로 받는다. 데이터/연산 비용 높으므로 베이스라인 이후 도입.
"""
from __future__ import annotations


class SequenceModel:
    def fit(self, X, y): raise NotImplementedError
    def predict(self, X): raise NotImplementedError
