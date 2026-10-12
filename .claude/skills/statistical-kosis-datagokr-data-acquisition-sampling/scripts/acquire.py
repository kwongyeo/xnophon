#!/usr/bin/env python3
"""KOSIS · data.go.kr 통계 데이터 수집 + 표본추출 CLI (표준 라이브러리만 사용).

MCP 서버(korean-stat, data-go-*)를 쓸 수 없을 때의 REST 대체 경로이자,
수집된 모집단 CSV에서 재현 가능한 표본을 뽑고 가중 추정치를 내는 도구다.

하위 명령:
  preflight     키 존재 여부 + 호스트 도달 가능성(egress 정책) 점검
  kosis-search  KOSIS 통합검색으로 통계표(orgId/tblId) 찾기
  kosis-meta    통계표 메타데이터(분류·항목·수록기간 등) 조회
  kosis-data    통계자료 조회 (40,000셀 초과 시 기간 자동 분할)
  datago        data.go.kr 오픈API 페이지네이션 수집 (apis.data.go.kr / odcloud)
  sample        CSV에서 표본추출 (srs / systematic / stratified / cluster) + 설계가중치
  estimate      표본 + 설계 JSON으로 평균·총계 추정치와 표준오차 계산

키는 환경변수 또는 .env(KOSIS_API_KEY, DATA_GO_KR_API_KEY)에서 읽고,
어떤 출력·로그·manifest에도 원문을 남기지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path

KOSIS_BASE = "https://kosis.kr/openapi"
KEY_PARAM_NAMES = ("apiKey", "serviceKey", "ServiceKey")
KOSIS_ERRORS = {
    "10": "인증키 누락",
    "11": "인증키 기간 만료",
    "20": "필수 요청변수 누락",
    "21": "잘못된 요청변수",
    "30": "조회 결과 없음",
    "31": "조회 결과 초과(40,000셀) — 기간/분류를 나눠 요청",
    "40": "호출 가능 건수 제한",
    "41": "호출 가능 ROW 수 제한",
    "50": "서버 오류",
}


# ---------------------------------------------------------------- 공통 유틸

def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_env(env_file: str | None) -> None:
    """.env를 읽어 os.environ에 없는 값만 채운다 (기존 환경변수 우선)."""
    candidates = [Path(env_file)] if env_file else [Path.cwd() / ".env"]
    for p in candidates:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


def require_key(name: str) -> str:
    key = os.environ.get(name, "").strip()
    if not key:
        sys.exit(f"[error] {name}가 비어 있습니다. .env 또는 환경변수에 설정하세요.")
    return key


def mask(text: str) -> str:
    """URL·메시지에서 키 값을 *** 로 가린다."""
    for name in ("KOSIS_API_KEY", "DATA_GO_KR_API_KEY"):
        v = os.environ.get(name)
        if v:
            text = text.replace(v, "***").replace(urllib.parse.quote(v, safe=""), "***")
    return text


def build_url(base: str, params: dict, key_name: str | None = None, key: str | None = None) -> str:
    """쿼리 문자열 생성. data.go.kr 'Encoding 키'(이미 %인코딩됨)는 이중 인코딩하지 않는다."""
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    if key_name and key:
        key_part = f"{key_name}={key}" if "%" in key else urllib.parse.urlencode({key_name: key})
        query = f"{key_part}&{query}" if query else key_part
    return f"{base}?{query}"


def http_get(url: str, *, data: bytes | None = None, headers: dict | None = None,
             retries: int = 4, timeout: int = 60) -> bytes:
    """지수 백오프 재시도. 프록시 403(egress 정책 차단)은 재시도하지 않고 즉시 중단한다."""
    hdrs = {"User-Agent": "kosis-datagokr-acquire/1.0"}
    hdrs.update(headers or {})
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except OSError as e:  # URLError, HTTPError, 터널 실패 모두 OSError 계열
            msg = str(e)
            if "Tunnel connection failed: 403" in msg or "Tunnel connection failed: 407" in msg:
                sys.exit(f"[blocked] egress 정책이 이 호스트를 차단합니다: {mask(url).split('?')[0]}\n"
                         "        우회하지 말고, 접속이 허용된 환경(로컬 PC 등)에서 다시 실행하세요.")
            status = getattr(e, "code", None)
            if status and 400 <= status < 500 and status != 429:
                body = e.read().decode("utf-8", "replace")[:500] if hasattr(e, "read") else ""
                sys.exit(f"[error] HTTP {status}: {mask(body)}")
            if attempt == retries:
                sys.exit(f"[error] 요청 실패({retries + 1}회): {mask(msg)}")
            wait = 2 ** (attempt + 1)
            log(f"[retry] {mask(msg)} → {wait}s 후 재시도")
            time.sleep(wait)
    raise AssertionError("unreachable")


def write_csv(rows: list[dict], path: Path) -> list[str]:
    fields: "OrderedDict[str, None]" = OrderedDict()
    for r in rows:
        for k in r:
            fields.setdefault(k, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # 엑셀 한글 호환
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        w.writerows(rows)
    return list(fields)


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_manifest(out: Path, info: dict, rows: list[dict], fields: list[str]) -> None:
    csv_path = out / "data.csv"
    info.update({
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(rows),
        "columns": fields,
        "data_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    })
    (out / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[ok] {len(rows)}행 → {csv_path}  (manifest.json 포함)")


def parse_kv(pairs: list[str] | None) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            sys.exit(f"[error] --param 형식은 key=value 입니다: {p}")
        k, v = p.split("=", 1)
        out[k] = v
    return out


# ---------------------------------------------------------------- preflight

def cmd_preflight(args) -> None:
    report = {"keys": {}, "hosts": {}}
    for name in ("KOSIS_API_KEY", "DATA_GO_KR_API_KEY"):
        v = os.environ.get(name, "")
        report["keys"][name] = f"set ({len(v)} chars)" if v else "MISSING"
    for host in ("kosis.kr", "apis.data.go.kr", "api.odcloud.kr"):
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://{host}/", method="HEAD"), timeout=15)
            report["hosts"][host] = "reachable"
        except urllib.error.HTTPError as e:  # 서버가 응답했다면 도달 가능
            report["hosts"][host] = f"reachable (HTTP {e.code})"
        except OSError as e:
            m = str(e)
            report["hosts"][host] = ("BLOCKED by egress policy (proxy 403)" if "403" in m or "407" in m
                                     else f"unreachable: {m[:120]}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- KOSIS

def kosis_call(path: str, params: dict) -> object:
    key = require_key("KOSIS_API_KEY")
    params = {**params, "format": "json", "jsonVD": "Y"}
    url = build_url(f"{KOSIS_BASE}/{path}", params, "apiKey", key)
    raw = http_get(url).decode("utf-8", "replace").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"[error] KOSIS 응답이 JSON이 아닙니다: {mask(raw[:300])}")
    if isinstance(data, dict) and "err" in data:
        code = str(data.get("err"))
        raise KosisError(code, f"KOSIS err {code} ({KOSIS_ERRORS.get(code, '알 수 없음')}): {data.get('errMsg', '')}")
    return data


class KosisError(Exception):
    def __init__(self, code: str, msg: str):
        super().__init__(msg)
        self.code = code


def cmd_kosis_search(args) -> None:
    try:
        rows = kosis_call("statisticsSearch.do", {
            "method": "getList", "searchNm": args.query, "orgId": args.org_id,
            "sort": "RANK", "startCount": 1, "resultCount": args.limit,
        })
    except KosisError as e:
        sys.exit(f"[error] {e}")
    for r in rows:
        print(f"{r.get('ORG_ID')}\t{r.get('TBL_ID')}\t{r.get('TBL_NM')}\t"
              f"{r.get('STRT_PRD_DE', '')}~{r.get('END_PRD_DE', '')}\t{r.get('ORG_NM', '')}")


def cmd_kosis_meta(args) -> None:
    try:
        rows = kosis_call("statisticsData.do", {
            "method": "getMeta", "type": args.type, "orgId": args.org_id, "tblId": args.tbl_id,
        })
    except KosisError as e:
        sys.exit(f"[error] {e}")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def enumerate_periods(se: str, start: str, end: str) -> list[str] | None:
    """수록주기별 기간 목록. 지원하지 않는 주기면 None (자동 분할 불가)."""
    per_year = {"Y": None, "H": 2, "Q": 4, "M": 12}
    if se not in per_year:
        return None
    if se == "Y":
        return [str(y) for y in range(int(start[:4]), int(end[:4]) + 1)]
    n = per_year[se]
    out = []
    for y in range(int(start[:4]), int(end[:4]) + 1):
        for i in range(1, n + 1):
            p = f"{y}{i:02d}"
            if start <= p <= end:
                out.append(p)
    return out


def cmd_kosis_data(args) -> None:
    base = {
        "method": "getList", "orgId": args.org_id, "tblId": args.tbl_id,
        "itmId": args.itm_id, "prdSe": args.prd_se,
    }
    for i, obj in enumerate(args.obj or [], start=1):
        base[f"objL{i}"] = obj
    if args.latest:
        base["newEstPrdCnt"] = args.latest
        rows = _kosis_fetch(base, None)
    else:
        periods = enumerate_periods(args.prd_se, args.start, args.end)
        rows = _kosis_fetch(base, periods, args.start, args.end)
    out = Path(args.out)
    fields = write_csv(rows, out / "data.csv")
    params = {k: v for k, v in base.items() if k != "method"}
    write_manifest(out, {
        "source": "KOSIS 국가통계포털 (https://kosis.kr)",
        "endpoint": f"{KOSIS_BASE}/Param/statisticsParameterData.do",
        "params": {**params, "startPrdDe": args.start, "endPrdDe": args.end},
        "citation": f"출처: 통계청 KOSIS, 통계표 {args.tbl_id} (orgId {args.org_id}), "
                    f"{datetime.now():%Y.%m.%d} 수집",
    }, rows, fields)


def _kosis_fetch(base: dict, periods: list[str] | None, start: str | None = None,
                 end: str | None = None) -> list[dict]:
    """40,000셀 초과(err 31)면 기간 목록을 반으로 나눠 재귀 요청한다."""
    params = dict(base)
    if periods is not None:
        params["startPrdDe"], params["endPrdDe"] = periods[0], periods[-1]
    elif start and end:
        params["startPrdDe"], params["endPrdDe"] = start, end
    try:
        data = kosis_call("Param/statisticsParameterData.do", params)
        log(f"[kosis] {params.get('startPrdDe', 'latest')}~{params.get('endPrdDe', '')}: {len(data)}행")
        time.sleep(0.2)
        return list(data)
    except KosisError as e:
        if e.code == "30":
            return []
        if e.code == "31" and periods and len(periods) > 1:
            mid = len(periods) // 2
            log(f"[kosis] 셀 한도 초과 → 기간 분할 ({periods[0]}~{periods[-1]})")
            return _kosis_fetch(base, periods[:mid]) + _kosis_fetch(base, periods[mid:])
        sys.exit(f"[error] {e}")


# ---------------------------------------------------------------- data.go.kr

def _items_and_total(payload: object) -> tuple[list[dict], int | None]:
    """apis.data.go.kr(response.body.items.item) / odcloud(data) 양식을 모두 처리."""
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):  # odcloud
            return payload["data"], payload.get("totalCount") or payload.get("matchCount")
        body = (payload.get("response") or {}).get("body") or payload.get("body") or {}
        header = (payload.get("response") or {}).get("header") or payload.get("header") or {}
        code = str(header.get("resultCode", "00"))
        if code not in ("00", "0", "000", "INFO-000"):
            sys.exit(f"[error] data.go.kr resultCode {code}: {header.get('resultMsg', '')}")
        items = body.get("items")
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]
        total = body.get("totalCount")
        return list(items or []), int(total) if str(total or "").isdigit() else None
    if isinstance(payload, list):
        return payload, None
    return [], None


def _parse_xml(raw: str) -> tuple[list[dict], int | None]:
    root = ET.fromstring(raw)
    auth = root.findtext(".//returnAuthMsg")
    reason = root.findtext(".//returnReasonCode")
    if auth or reason:
        sys.exit(f"[error] data.go.kr 인증/호출 오류 {reason}: {auth} "
                 "(SERVICE_KEY_IS_NOT_REGISTERED면 활용신청 승인 여부 확인 또는 Encoding↔Decoding 키 교체)")
    code = root.findtext(".//resultCode")
    if code and code not in ("00", "0", "000"):
        sys.exit(f"[error] data.go.kr resultCode {code}: {root.findtext('.//resultMsg')}")
    items = [{c.tag: (c.text or "") for c in item} for item in root.iter("item")]
    total = root.findtext(".//totalCount")
    return items, int(total) if total and total.isdigit() else None


def cmd_datago(args) -> None:
    key = require_key("DATA_GO_KR_API_KEY")
    page_param, size_param = ("page", "perPage") if args.style == "odcloud" else ("pageNo", "numOfRows")
    page_param = args.page_param or page_param
    size_param = args.size_param or size_param
    extra = parse_kv(args.param)
    out = Path(args.out)
    rows: list[dict] = []
    total = None
    page = 1
    while page <= args.max_pages:
        params = {**extra, page_param: page, size_param: args.size}
        url = build_url(args.url, params, "serviceKey", key)
        raw = http_get(url).decode("utf-8", "replace").strip()
        (out / "raw").mkdir(parents=True, exist_ok=True)
        (out / "raw" / f"page-{page:04d}.txt").write_text(mask(raw), encoding="utf-8")
        if raw.startswith("<"):
            items, total = _parse_xml(raw)
        else:
            try:
                items, total = _items_and_total(json.loads(raw))
            except json.JSONDecodeError:
                sys.exit(f"[error] 알 수 없는 응답 형식: {mask(raw[:300])}")
        rows.extend(items)
        log(f"[datago] page {page}: {len(items)}행 (누적 {len(rows)}/{total or '?'})")
        if not items or len(items) < args.size or (total is not None and len(rows) >= total):
            break
        page += 1
        time.sleep(args.sleep)
    if page > args.max_pages and total and len(rows) < total:
        log(f"[warn] --max-pages {args.max_pages} 에서 중단: {len(rows)}/{total}행만 수집")
    fields = write_csv(rows, out / "data.csv")
    write_manifest(out, {
        "source": "공공데이터포털 data.go.kr",
        "endpoint": args.url,
        "params": extra,
        "pagination": {page_param: f"1..{page}", size_param: args.size},
        "total_count_reported": total,
        "complete": total is None or len(rows) >= total,
        "citation": f"출처: 공공데이터포털(data.go.kr), {args.url.split('?')[0]}, {datetime.now():%Y.%m.%d} 수집",
    }, rows, fields)


# ---------------------------------------------------------------- 표본추출

def _allocate(n: int, sizes: dict, method: str, sds: dict | None, min_per: int) -> dict:
    """층별 표본 배분 (최대잉여법으로 합계 n 보존, 층 크기 상한 적용)."""
    H = len(sizes)
    if method == "equal":
        weights = {h: 1.0 for h in sizes}
    elif method == "neyman":
        weights = {h: sizes[h] * (sds[h] if sds[h] > 0 else 1e-9) for h in sizes}
    else:
        weights = dict(sizes)
    tot = sum(weights.values())
    raw = {h: n * w / tot for h, w in weights.items()}
    alloc = {h: min(sizes[h], max(min_per, math.floor(raw[h]))) for h in sizes}
    left = n - sum(alloc.values())
    for h in sorted(sizes, key=lambda h: raw[h] - math.floor(raw[h]), reverse=True):
        if left <= 0:
            break
        if alloc[h] < sizes[h]:
            alloc[h] += 1
            left -= 1
    if n < H * min_per:
        log(f"[warn] n={n} < 층 수({H})×최소({min_per}) → 층당 최소 배분으로 n이 늘어남")
    return alloc


def _to_float(v: str) -> float | None:
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _sd(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def cmd_sample(args) -> None:
    rows = read_csv(args.input)
    N = len(rows)
    if N == 0:
        sys.exit("[error] 입력 CSV가 비어 있습니다.")
    if args.id_col:
        # 같은 틀이면 행 순서가 달라도 같은 표본이 나오도록 고유 ID로 정렬한 뒤 추출한다.
        if args.id_col not in rows[0]:
            sys.exit(f"[error] --id-col '{args.id_col}' 컬럼이 없습니다: {list(rows[0])}")
        ids = [r[args.id_col] for r in rows]
        if len(set(ids)) != N:
            sys.exit(f"[error] --id-col '{args.id_col}' 값이 고유하지 않습니다 (중복 {N - len(set(ids))}건).")
        rows.sort(key=lambda r: r[args.id_col])
    else:
        log("[warn] --id-col 미지정: 같은 시드라도 입력 행 순서가 바뀌면 다른 표본이 나옵니다.")
    rng = random.Random(args.seed)
    target = args.n if args.n else max(1, round(N * args.frac))
    design: dict = {"method": args.method, "seed": args.seed, "N": N, "input": args.input,
                    "input_sha256": hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                    "id_col": args.id_col}
    picked: list[dict] = []

    if args.method in ("srs", "systematic"):
        n = min(target, N)
        if args.method == "srs":
            idx = sorted(rng.sample(range(N), n))
        else:
            order = sorted(range(N), key=lambda i: rows[i].get(args.sort_by, "")) if args.sort_by else list(range(N))
            k = N / n
            start = rng.uniform(0, k)
            idx = [order[min(N - 1, math.floor(start + i * k))] for i in range(n)]
            design.update({"interval_k": round(k, 4), "random_start": round(start, 4), "sort_by": args.sort_by})
        for i in idx:
            picked.append({**rows[i], "_stratum": "", "_weight": N / n})
        design["n"] = n

    elif args.method == "stratified":
        if not args.strata:
            sys.exit("[error] stratified는 --strata 컬럼이 필요합니다.")
        groups: dict = defaultdict(list)
        certainty: list[dict] = []
        if args.take_all_above is not None and not args.value:
            sys.exit("[error] --take-all-above는 규모 기준 수치 컬럼 --value가 필요합니다.")
        for r in rows:
            x = _to_float(r.get(args.value, "")) if args.take_all_above is not None else None
            if x is not None and x >= args.take_all_above:
                certainty.append(r)  # 대규모 단위는 전수 포함 (가중치 1, 분산 기여 0)
            else:
                groups[tuple(r.get(c, "") for c in args.strata)].append(r)
        if len(certainty) >= target:
            sys.exit(f"[error] 전수층 {len(certainty)}건이 표본 크기 {target} 이상입니다. 임계값을 올리세요.")
        target -= len(certainty)
        sizes = {h: len(g) for h, g in groups.items()}
        sds = None
        if args.allocation == "neyman":
            if not args.value:
                sys.exit("[error] neyman 배분은 --value(분산 계산용 수치 컬럼)가 필요합니다.")
            sds = {h: _sd([x for x in (_to_float(r.get(args.value, "")) for r in g) if x is not None])
                   for h, g in groups.items()}
        alloc = _allocate(target, sizes, args.allocation, sds, args.min_per_stratum)
        strata_info = {}
        for h, g in groups.items():
            nh = alloc[h]
            label = "|".join(h)
            for r in rng.sample(g, nh):
                picked.append({**r, "_stratum": label, "_weight": sizes[h] / nh if nh else 0})
            strata_info[label] = {"N_h": sizes[h], "n_h": nh}
        if certainty:
            for r in certainty:
                picked.append({**r, "_stratum": "__take_all__", "_weight": 1.0})
            strata_info["__take_all__"] = {"N_h": len(certainty), "n_h": len(certainty),
                                           "rule": f"{args.value} >= {args.take_all_above}"}
        design.update({"strata_columns": args.strata, "allocation": args.allocation,
                       "allocation_variable": args.value if args.allocation == "neyman" else None,
                       "strata": strata_info, "n": sum(v["n_h"] for v in strata_info.values())})

    elif args.method == "cluster":
        if not args.cluster:
            sys.exit("[error] cluster는 --cluster 컬럼이 필요합니다.")
        clusters: dict = defaultdict(list)
        for r in rows:
            clusters[r.get(args.cluster, "")].append(r)
        M = len(clusters)
        m = min(target, M)
        chosen = sorted(rng.sample(sorted(clusters), m))
        for c in chosen:
            for r in clusters[c]:
                picked.append({**r, "_stratum": "", "_cluster": c, "_weight": M / m})
        design.update({"cluster_column": args.cluster, "M": M, "m": m, "clusters": chosen,
                       "n": len(picked)})

    out = Path(args.out)
    write_csv(picked, out)
    design_path = out.with_suffix(".design.json")
    design["output"] = str(out)
    design_path.write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[ok] {args.method} 표본 {len(picked)}행 / 모집단 {N}행 → {out}, 설계: {design_path}")


_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
         2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
         2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def _t975(df: int) -> float:
    if df < 1:
        return float("nan")
    return _T975[df - 1] if df <= 30 else 1.959964 + 2.4 / df  # 30 초과는 근사


def cmd_estimate(args) -> None:
    rows = read_csv(args.sample)
    design = json.loads(Path(args.design).read_text(encoding="utf-8"))
    vals = []
    for r in rows:
        x = _to_float(r.get(args.value, ""))
        if x is not None:
            vals.append((r, x))
    if not vals:
        sys.exit(f"[error] '{args.value}' 컬럼에 수치가 없습니다.")
    method, N = design["method"], design["N"]
    res: dict = {"value": args.value, "method": method, "n_used": len(vals),
                 "n_missing": len(rows) - len(vals)}

    if method in ("srs", "systematic"):
        xs = [x for _, x in vals]
        n = len(xs)
        mean = sum(xs) / n
        var_mean = (1 - n / N) * _sd(xs) ** 2 / n
        res.update({"mean": mean, "se_mean": math.sqrt(var_mean), "total": N * mean,
                    "se_total": N * math.sqrt(var_mean)})
        if method == "systematic":
            res["note"] = "계통추출 분산은 SRS 근사치(주기성 있으면 과소/과대 가능)"
    elif method == "stratified":
        by: dict = defaultdict(list)
        for r, x in vals:
            by[r["_stratum"]].append(x)
        total = var_total = 0.0
        for label, info in design["strata"].items():
            xs = by.get(label, [])
            if not xs:
                continue
            Nh, nh = info["N_h"], len(xs)
            total += Nh * sum(xs) / nh
            var_total += Nh ** 2 * (1 - nh / Nh) * _sd(xs) ** 2 / nh
        res.update({"total": total, "se_total": math.sqrt(var_total),
                    "mean": total / N, "se_mean": math.sqrt(var_total) / N})
    elif method == "cluster":
        M, m = design["M"], design["m"]
        ct: dict = defaultdict(float)
        for r, x in vals:
            ct[r["_cluster"]] += x
        t = [ct.get(c, 0.0) for c in design["clusters"]]
        total = M / m * sum(t)
        var_total = M ** 2 * (1 - m / M) * _sd(t) ** 2 / m
        res.update({"total": total, "se_total": math.sqrt(var_total),
                    "mean_per_unit": total / N, "se_mean_per_unit": math.sqrt(var_total) / N})
    # 군집 수가 적으면 정규근사가 구간을 과소추정하므로 t(m-1) 임계값을 쓴다.
    crit = _t975(design["m"] - 1) if method == "cluster" else 1.959964
    res["ci_critical_value"] = round(crit, 4)
    if "se_total" in res:
        res["ci95_total"] = [res["total"] - crit * res["se_total"], res["total"] + crit * res["se_total"]]
    print(json.dumps(res, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", help=".env 경로 (기본: 현재 디렉터리의 .env)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight", help="키·호스트 도달성 점검").set_defaults(func=cmd_preflight)

    p = sub.add_parser("kosis-search", help="KOSIS 통계표 검색")
    p.add_argument("query")
    p.add_argument("--org-id")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_kosis_search)

    p = sub.add_parser("kosis-meta", help="KOSIS 통계표 메타데이터")
    p.add_argument("--org-id", required=True)
    p.add_argument("--tbl-id", required=True)
    p.add_argument("--type", default="ITM", help="TBL|ORG|PRD|ITM|CMMT|UNIT|SOURCE|WGT|NCD")
    p.set_defaults(func=cmd_kosis_meta)

    p = sub.add_parser("kosis-data", help="KOSIS 통계자료 조회")
    p.add_argument("--org-id", required=True)
    p.add_argument("--tbl-id", required=True)
    p.add_argument("--itm-id", default="ALL")
    p.add_argument("--obj", action="append", help="objL1, objL2 … 순서대로 반복 지정 (예: ALL, 00+11)")
    p.add_argument("--prd-se", default="Y", help="수록주기 Y|H|Q|M|D|IR …")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--latest", type=int, help="최근 N개 시점 (newEstPrdCnt)")
    g.add_argument("--start", help="시작 시점 (예: 2015, 201501)")
    p.add_argument("--end", help="끝 시점")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_kosis_data)

    p = sub.add_parser("datago", help="data.go.kr 오픈API 수집")
    p.add_argument("--url", required=True, help="오퍼레이션 URL (쿼리 제외)")
    p.add_argument("--param", action="append", help="key=value (반복). 예: type=json, _type=json")
    p.add_argument("--style", choices=["apis", "odcloud"], default="apis")
    p.add_argument("--page-param")
    p.add_argument("--size-param")
    p.add_argument("--size", type=int, default=100)
    p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--sleep", type=float, default=0.3)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_datago)

    p = sub.add_parser("sample", help="표본추출 + 설계가중치")
    p.add_argument("--input", required=True)
    p.add_argument("--method", choices=["srs", "systematic", "stratified", "cluster"], required=True)
    s = p.add_mutually_exclusive_group(required=True)
    s.add_argument("--n", type=int, help="표본 크기 (cluster는 뽑을 군집 수)")
    s.add_argument("--frac", type=float, help="추출 비율 (0~1)")
    p.add_argument("--strata", nargs="+", help="층화 컬럼(복수 가능)")
    p.add_argument("--allocation", choices=["proportional", "equal", "neyman"], default="proportional")
    p.add_argument("--value", help="neyman 배분·전수층 기준용 보조 수치 컬럼 (조사 전 알려진 값)")
    p.add_argument("--min-per-stratum", type=int, default=1)
    p.add_argument("--cluster", help="군집 컬럼")
    p.add_argument("--sort-by", help="계통추출 전 정렬 컬럼(암묵적 층화)")
    p.add_argument("--id-col", help="고유 ID 컬럼 — 지정하면 행 순서와 무관하게 재현 (권장)")
    p.add_argument("--take-all-above", type=float,
                   help="stratified: --value가 이 값 이상인 단위는 전수층으로 모두 포함")
    p.add_argument("--seed", type=int, default=20260626)
    p.add_argument("--out", required=True, help="표본 CSV 경로 (설계는 .design.json으로 저장)")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("estimate", help="가중 추정치·표준오차")
    p.add_argument("--sample", required=True)
    p.add_argument("--design", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_estimate)

    args = ap.parse_args(argv)
    if args.cmd == "kosis-data" and args.start and not args.end:
        ap.error("--start를 쓰면 --end도 필요합니다.")
    if getattr(args, "frac", None) is not None and not 0 < args.frac <= 1:
        ap.error("--frac은 0~1 사이여야 합니다.")
    load_env(args.env_file)
    args.func(args)


if __name__ == "__main__":
    main()
