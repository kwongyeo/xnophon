# KOSIS 데이터 수집 시스템 설정 가이드

국가통계포털(KOSIS) 통계 데이터를 가져오기 위해 **`korean-stat-mcp`** MCP 서버를
이 레포에 등록했다. Claude Code / Claude Desktop 등 MCP 클라이언트가 자연어로 KOSIS
통계표를 검색·조회·분석할 수 있다.

- 출처: <https://github.com/seolcoding/korean-stat-mcp> (Python, FastMCP, MIT)
- PyPI: `korean-stat-mcp`
- 등록 설정: 레포 루트의 [`.mcp.json`](../.mcp.json)

## 왜 MCP 서버 방식인가

- `korean-stat-mcp`는 **Python 3.12+**를 요구한다. 이 프로젝트(`literature-review`)는
  Python ≥3.10 venv에서 동작하므로, 서버를 venv에 직접 설치하면 버전이 충돌한다.
- 그래서 `uvx`로 **격리 실행**한다. `uvx`가 전용 Python 3.12 환경을 자동으로 받아
  서버를 띄우므로 프로젝트 의존성과 완전히 분리된다. 별도 `pip install` 불필요.

## 1) KOSIS API 키 발급

1. <https://kosis.kr/openapi/> 접속 → 로그인(회원가입 무료).
2. **활용신청** → 사용자 정보/활용 목적 입력 → 즉시 인증키 발급.
3. 발급된 키를 `.env`에 등록한다.

```bash
cp .env.example .env   # 최초 1회
# .env 파일에서 KOSIS_API_KEY 값을 채운다
KOSIS_API_KEY=발급받은_키
```

`.mcp.json`은 `${KOSIS_API_KEY}`로 이 값을 주입하므로, 키를 코드/설정에 하드코딩하지
않는다. (`.env`는 `.gitignore`로 커밋 제외됨)

## 2) 사전 준비물

- [`uv`](https://docs.astral.sh/uv/) 설치 (이미 설치돼 있으면 생략):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  `uvx`는 `uv`에 포함된다.

## 3) 동작 확인

```bash
# 환경변수 로드 후 서버 헬프 확인 (Python 3.12 자동 다운로드)
uvx --python 3.12 korean-stat-mcp --help
```

Claude Code에서는 레포 루트의 `.mcp.json`이 자동 감지된다. 세션에서 MCP 서버를 신뢰하면
`korean-stat` 서버의 KOSIS 도구(통계표 검색, 메타데이터, 데이터 조회, 기초 분석 등
12개)가 노출된다.

### Claude Desktop / Cursor 등 다른 클라이언트

각 클라이언트의 MCP 설정에 동일하게 등록한다:

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "uvx",
      "args": ["--python", "3.12", "korean-stat-mcp"],
      "env": { "KOSIS_API_KEY": "발급받은_키" }
    }
  }
}
```

### (참고) HTTP 모드 / 호스팅

- 로컬 HTTP 서버: `uvx --python 3.12 korean-stat-mcp --http` → `http://localhost:8000/mcp`
- 키 발급만으로 바로 쓰는 호스팅 엔드포인트도 제공된다:
  `https://korean-stat-mcp.seolcoding.com/mcp?apiKey=<YOUR_KEY>`

## 제공 도구(요약)

통계표 검색, 표 메타데이터 조회, 원자료(raw data) 조회, 기초 분석 등.
정확한 도구 목록과 인자는 위 서버를 실행해 MCP 클라이언트에서 확인한다.
