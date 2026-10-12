# 설치·키 설정 레퍼런스

preflight에서 MCP 서버나 키가 없다고 나올 때만 읽는다.

## MCP 서버 등록 (.mcp.json)

프로젝트 루트의 `.mcp.json`에 아래를 넣는다 (Claude Desktop 등은 각 클라이언트 MCP 설정에 동일하게).
`uvx`가 서버마다 격리된 Python을 받아 실행하므로 프로젝트 venv와 버전이 충돌하지 않는다.
(`korean-stat-mcp`는 Python 3.12+, `data-go-mcp.*`는 3.10+ 필요)

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "uvx",
      "args": ["--python", "3.12", "korean-stat-mcp"],
      "env": { "KOSIS_API_KEY": "${KOSIS_API_KEY}" }
    },
    "data-go-nps-business-enrollment": {
      "command": "uvx", "args": ["data-go-mcp.nps-business-enrollment@latest"],
      "env": { "API_KEY": "${DATA_GO_KR_API_KEY}" }
    },
    "data-go-nts-business-verification": {
      "command": "uvx", "args": ["data-go-mcp.nts-business-verification@latest"],
      "env": { "API_KEY": "${DATA_GO_KR_API_KEY}" }
    },
    "data-go-pps-narajangteo": {
      "command": "uvx", "args": ["data-go-mcp.pps-narajangteo@latest"],
      "env": { "API_KEY": "${DATA_GO_KR_API_KEY}" }
    },
    "data-go-fsc-financial-info": {
      "command": "uvx", "args": ["data-go-mcp.fsc-financial-info@latest"],
      "env": { "API_KEY": "${DATA_GO_KR_API_KEY}" }
    },
    "data-go-presidential-speeches": {
      "command": "uvx", "args": ["data-go-mcp.presidential-speeches@latest"],
      "env": { "API_KEY": "${DATA_GO_KR_API_KEY}" }
    },
    "data-go-msds-chemical-info": {
      "command": "uvx", "args": ["data-go-mcp.msds-chemical-info@latest"],
      "env": { "API_KEY": "${DATA_GO_KR_API_KEY}" }
    }
  }
}
```

원본 서버들의 환경변수 이름은 모두 `API_KEY`로 너무 일반적이다. 그래서 `.env`에는
`DATA_GO_KR_API_KEY`만 두고 각 서버에 매핑한다.
`${VAR}` 치환은 MCP 클라이언트를 띄운 셸의 환경변수에서 읽힌다. `.env`만 만들고
셸에 export하지 않으면 MCP 서버가 키를 받지 못할 수 있으니, 필요하면
`set -a; source .env; set +a` 후 클라이언트를 실행한다. (`acquire.py`는 `.env`를 직접 읽는다.)

## 인증키 발급

- KOSIS: https://kosis.kr/openapi/ → 활용신청 → 즉시 발급 → 마이페이지에서 확인
- data.go.kr: https://www.data.go.kr/ → 데이터셋별 **활용신청**(대부분 자동승인) →
  마이페이지 > 데이터활용 > 인증키(Decoding 권장)

Claude는 사용자의 브라우저 로그인 세션에 접근할 수 없으므로 키를 대신 발급할 수 없다.
사용자가 직접 발급하도록 위 경로를 안내한다.

## 키 취급

- 키는 `.env`(gitignore)에만 둔다. `.gitignore`에 `.env`가 있는지 `git check-ignore .env`로 확인.
- 사용자가 채팅에 키를 붙여넣으면: 값을 다시 출력하지 말고 `.env`에 기록한 뒤
  재발급을 권한다 (채팅 기록에 남고, base64는 암호화가 아니다).
- 원격·클라우드 세션의 `.env`는 세션이 끝나면 사라진다. 사용자 PC의 `.env`는 따로 둬야 한다.

## egress(네트워크 정책) 차단

원격 실행 환경에서는 `kosis.kr`, `apis.data.go.kr`, `api.odcloud.kr`가 조직 정책으로
막혀 있을 수 있다 (프록시 CONNECT 403). 이 경우 MCP 서버도 같은 프록시를 쓰므로 함께 막힌다.
우회하지 말고, 차단된 호스트 이름을 보고한 뒤 사용자 PC에서 같은 명령을 실행하도록 안내한다.
Claude Code on the web 환경이라면 환경 설정의 네트워크 정책에서 허용 도메인을 추가할 수 있다.
