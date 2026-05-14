# data/

3단 데이터 레이어. 모든 파일은 git 추적 제외(`.gitignore` 참조). 메타만 커밋.

```
raw/        다운로드 원본 (불변, 절대 수정 금지)
  kosis/<table_id>/<YYYYMMDD>.json
  lofin/<year>/세출예산_분야별_<sido>_<year>.csv
  jumin/<year>/<month>.csv
interim/    정제 중간 산출물 (parquet 권장)
processed/  최종 패널 (xlsx, csv)
MANIFEST.csv  raw 파일 출처·다운로드일 추적 (커밋 대상)
```

## MANIFEST.csv 형식

| 컬럼 | 설명 |
|---|---|
| relpath | data/ 기준 상대경로 |
| source  | 출처 식별자 (kosis/lofin/jumin/...) |
| url     | 원본 URL 또는 페이지 |
| downloaded_at | YYYY-MM-DD |
| sha256  | 무결성 해시 (선택) |
| notes   | 비고 |
