#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주탐주예(JuTamJuYe) — 주식 탐색·주식 예측 멀티팩터 모델
향후 ~60거래일(3개월) 기대수익 상위 종목 랭킹.

설계 개요
  '주탐(株探)' : 후보 종목군을 탐색해 횡단면 데이터를 모은다.
  '주예(株豫)' : 5개 팩터를 시장내 z-score로 표준화 후 가중합해 기대수익을 점수화한다.

5팩터 (괄호=종합점수 가중치)
  CONS 컨센서스(예측) : 애널 목표가 상승여력 + 투자의견    (0.30)
  MOM  모멘텀         : 200일선/50일선 대비 위치(중기추세)  (0.25)
  QUAL 퀄리티         : ROE + 순이익률 + (-부채비율)        (0.20)
  VAL  밸류           : 선행이익수익률 + (-PEG) + (-PBR)    (0.15)
  GROW 성장          : 이익성장 + 매출성장                 (0.10)

데이터 출처: yfinance 스냅샷(2026-06-26, PlayMCP UsStockInfo.get_stock_info).
주의: 연구·교육용 팩터 데모이며 투자권유가 아니다. 극단치는 winsorize로 완화한다.
"""
import numpy as np

# ---- 데이터 스냅샷 (2026-06-26) -------------------------------------------------
# 필드: t200=현재가/200일선-1, t50=현재가/50일선-1, fpe=forwardPE, pb=priceToBook,
#       peg=trailingPegRatio, roe, marg=profitMargins, de=debtToEquity,
#       eg=earningsGrowth, rg=revenueGrowth, up=목표가상승여력, rec=recommendationMean, na=애널수
US = {
 #ticker  name          t200     t50     fpe    pb     peg    roe     marg   de     eg     rg     up      rec   na
 "NVDA": ("엔비디아",     0.0196, -0.0759,15.26, 24.07, 0.60, 1.143, 0.630, 6.56, 2.145, 0.852, 0.539, 1.29, 59),
 "MSFT": ("마이크로소프트",-0.1761,-0.1023,19.08, 6.63, 1.09, 0.340, 0.393,30.27, 0.234, 0.183, 0.518, 1.34, 55),
 "GOOGL":("알파벳",       0.0989,-0.0675,23.66, 8.71, 1.35, 0.389, 0.379,20.03, 0.820, 0.218, 0.257, 1.44, 53),
 "META": ("메타",        -0.1473,-0.0977,15.32, 5.78, 0.78, 0.329, 0.328,35.61, 0.624, 0.331, 0.490, 1.31, 59),
 "AMZN": ("아마존",      -0.0028,-0.0947,23.50, 5.65, 1.83, 0.243, 0.122,53.30, 0.748, 0.166, 0.348, 1.34, 63),
 "AVGO": ("브로드컴",     0.0256,-0.1022,19.10, 20.10,0.69, 0.373, 0.388,74.02, 0.854, 0.479, 0.414, 1.33, 45),
 "AMD":  ("AMD",         0.9154, 0.1860,39.08, 13.01,1.28, 0.0806,0.134, 6.01, 0.912, 0.378,-0.028, 1.45, 48),
 "PLTR": ("팰런티어",    -0.2886,-0.1741,54.36, 32.11,1.54, 0.326, 0.437, 2.48, 3.250, 0.847, 0.615, 1.91, 27),
 "NFLX": ("넷플릭스",    -0.2298,-0.1357,19.51, 10.14,1.39, 0.485, 0.285,53.79, 0.864, 0.162, 0.523, 1.68, 44),
 "LLY":  ("일라이릴리",   0.2376, 0.1753,27.09, 34.51,1.46, 1.075, 0.350,139.0, 1.699, 0.555, 0.015, 1.74, 29),
 "JPM":  ("JP모건",      0.0788, 0.0690,14.09, 2.59, 1.78, 0.165, 0.339, np.nan,0.172, 0.127, 0.033, 2.17, 21),
 "COST": ("코스트코",     0.0012,-0.0387,42.38, 25.72,4.60, 0.292, 0.030,60.26, 0.455, 0.215, 0.129, 1.97, 33),
 "TSLA": ("테슬라",      -0.0790,-0.0499,153.8, 17.57,5.36, 0.049, 0.039,18.74, 0.083, 0.158, 0.095, 2.34, 41),
}

KR = {
 "005930":("삼성전자",       0.9842, 0.1973, 5.50, np.nan,0.42, 0.189, 0.215, 5.78, 4.921, 0.692, 0.338, 1.38, 36),
 "000660":("SK하이닉스",     1.7364, 0.4225, 6.16, np.nan,3.99, 0.612, 0.569,13.28, 3.966, 1.981, 0.140, 1.43, 37),
 "005380":("현대차",        0.1347,-0.2044, 9.74, np.nan,4.13, 0.0754,0.046,139.5,-0.431, 0.034, 0.558, 1.65, 31),
 "005490":("POSCO홀딩스",  -0.1217,-0.2657,10.09, np.nan,0.90, 0.0113,0.012,49.97, 0.545, 0.025, 0.711, 1.55, 20),
 "035420":("NAVER",       -0.1769,-0.1088,13.25, np.nan,24.2, 0.0572,0.145,17.17,-0.322, 0.163, 0.557, 1.67, 27),
 "000270":("기아",         -0.0348,-0.1525, 5.73, np.nan,0.42, 0.119, 0.061, 4.32,-0.225, 0.053, 0.700, 1.37, 30),
 "012450":("한화에어로스페이스",-0.1221,-0.1943,17.80,np.nan,np.nan,0.185,0.060,91.24,2.849,0.049,0.716, 1.39, 23),
 "042700":("한미반도체",     0.2218,-0.1955,46.94, np.nan,1.42, 0.308, 0.371, 0.35,-0.652,-0.655, 0.022, 3.13,  8),
 "207940":("삼성바이오로직스",-0.1776,-0.0568,27.86,np.nan,2.07, 0.1825,0.390,15.08, 0.251, 0.258, 0.561, 1.43, 23),
 "105560":("KB금융",        0.0731,-0.0534, 7.89, np.nan,0.74, 0.0999,0.366, np.nan,0.168,0.152, 0.312, 1.40, 20),
 "068270":("셀트리온",     -0.1076,-0.0887,22.97, np.nan,0.85, 0.0726,0.284,21.70, 2.243, 0.360, 0.531, 1.54, 24),
 "028260":("삼성물산",      0.7053, 0.2336,27.20, np.nan,0.0,  0.0748,0.062, 6.94, 0.142, 0.075, 0.080, 1.39, 18),
}
# 028260 peg는 결측 → 0.0 placeholder, 아래에서 NaN 처리
KR["028260"] = KR["028260"][:5] + (np.nan,) + KR["028260"][6:]

IDX = dict(t200=0+2, t50=1+2, fpe=2+2, pb=3+2, peg=4+2, roe=5+2, marg=6+2,
           de=7+2, eg=8+2, rg=9+2, up=10+2, rec=11+2, na=12+2)
# row layout: (name, t200, t50, fpe, pb, peg, roe, marg, de, eg, rg, up, rec, na)
COL = {k:i for i,k in enumerate(
    ["name","t200","t50","fpe","pb","peg","roe","marg","de","eg","rg","up","rec","na"])}

def col(data, key):
    return np.array([row[COL[key]] for row in data.values()], dtype=float)

def winsor(x, lo=-2.5, hi=2.5):
    return np.clip(x, lo, hi)

def zscore(x, invert=False, wlo=None, whi=None):
    """결측은 시장 중앙값으로 대체 후 z-score. winsor on raw percentile-ish via clip."""
    x = np.array(x, dtype=float)
    if np.all(np.isnan(x)):           # 전부 결측 컬럼 → 중립(0)
        return np.zeros_like(x)
    if wlo is not None or whi is not None:
        x = np.clip(x, wlo if wlo is not None else np.nanmin(x),
                       whi if whi is not None else np.nanmax(x))
    med = np.nanmedian(x)
    x = np.where(np.isnan(x), med, x)
    mu, sd = x.mean(), x.std()
    z = (x - mu) / (sd if sd > 1e-9 else 1.0)
    z = winsor(z)
    return -z if invert else z

def score_market(data):
    t200 = col(data,"t200"); t50 = col(data,"t50")
    fpe  = col(data,"fpe");  pb  = col(data,"pb");  peg = col(data,"peg")
    roe  = col(data,"roe");  marg= col(data,"marg"); de = col(data,"de")
    eg   = col(data,"eg");   rg  = col(data,"rg")
    up   = col(data,"up");   rec = col(data,"rec")

    # ---- 팩터 구성 ----
    # 모멘텀: 중기추세(200일선) 0.6 + 단기추세(50일선) 0.4, 과열 winsor
    MOM = 0.6*zscore(t200, wlo=-0.40, whi=0.60) + 0.4*zscore(t50, wlo=-0.30, whi=0.30)

    # 컨센서스(예측): 애널 목표가 상승여력 0.6 + 투자의견(낮을수록 강함) 0.4
    CONS = 0.6*zscore(up, wlo=-0.20, whi=0.80) + 0.4*zscore(rec, invert=True)

    # 밸류: 선행이익수익률(1/fpe) 0.5 + PEG(낮을수록↑) 0.3 + PBR(낮을수록↑) 0.2
    ey = 1.0/np.where(fpe>0, fpe, np.nan)
    VAL = 0.5*zscore(ey) + 0.3*zscore(peg, invert=True, wlo=0.0, whi=5.0) + 0.2*zscore(pb, invert=True, wlo=0.0, whi=35.0)

    # 퀄리티: ROE 0.4 + 순이익률 0.3 + 부채비율(낮을수록↑) 0.3
    QUAL = 0.4*zscore(roe, wlo=-0.2, whi=1.2) + 0.3*zscore(marg) + 0.3*zscore(de, invert=True, wlo=0.0, whi=150.0)

    # 성장: 이익성장 0.5 + 매출성장 0.5, 극단 winsor
    GROW = 0.5*zscore(eg, wlo=-1.0, whi=3.0) + 0.5*zscore(rg, wlo=-0.7, whi=2.0)

    # ---- 종합 기대수익 점수 (3개월 horizon 가중) ----
    W = dict(CONS=0.30, MOM=0.25, QUAL=0.20, VAL=0.15, GROW=0.10)
    TOTAL = (W["CONS"]*CONS + W["MOM"]*MOM + W["QUAL"]*QUAL +
             W["VAL"]*VAL + W["GROW"]*GROW)

    names = [row[0] for row in data.values()]
    tickers = list(data.keys())
    out = []
    for i,(tk,nm) in enumerate(zip(tickers,names)):
        out.append(dict(ticker=tk, name=nm, TOTAL=TOTAL[i],
                        CONS=CONS[i], MOM=MOM[i], QUAL=QUAL[i], VAL=VAL[i], GROW=GROW[i],
                        up=up[i], rec=rec[i], fpe=fpe[i], roe=roe[i], t200=t200[i]))
    out.sort(key=lambda d: d["TOTAL"], reverse=True)
    return out

def show(title, ranked):
    print("="*96)
    print(title)
    print("="*96)
    print(f"{'순위':<4}{'종목':<14}{'종합':>7}{'컨센':>7}{'모멘':>7}{'퀄리티':>8}{'밸류':>7}{'성장':>7}{'상승여력':>9}{'의견':>6}")
    for i,d in enumerate(ranked,1):
        print(f"{i:<5}{d['name']:<13}{d['TOTAL']:>7.2f}{d['CONS']:>7.2f}{d['MOM']:>7.2f}"
              f"{d['QUAL']:>8.2f}{d['VAL']:>7.2f}{d['GROW']:>7.2f}{d['up']*100:>8.1f}%{d['rec']:>6.2f}")

us = score_market(US)
kr = score_market(KR)
show("미국시장 — 주탐주예 3개월 기대수익 랭킹", us)
print()
show("한국시장 — 주탐주예 3개월 기대수익 랭킹", kr)

# top-factor 설명용
def top_factors(d):
    fs = {"컨센서스":d["CONS"],"모멘텀":d["MOM"],"퀄리티":d["QUAL"],"밸류":d["VAL"],"성장":d["GROW"]}
    return sorted(fs.items(), key=lambda x:x[1], reverse=True)

print("\n\n[상위 5 — 강한 팩터 요약]")
for mkt,rk in [("US",us),("KR",kr)]:
    print(f"\n# {mkt}")
    for d in rk[:5]:
        tf = top_factors(d)
        print(f"  {d['name']:<12} 강점={tf[0][0]}({tf[0][1]:+.2f}), {tf[1][0]}({tf[1][1]:+.2f}) | 약점={tf[-1][0]}({tf[-1][1]:+.2f})")
