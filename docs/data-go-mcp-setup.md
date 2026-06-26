# 공공데이터포털(data.go.kr) 데이터 수집 시스템 설정 가이드

공공데이터포털(data.go.kr) API를 가져오기 위해 **[`Koomook/data-go-mcp-servers`](https://github.com/Koomook/data-go-mcp-servers)**
(Python, Apache-2.0, 285★)의 MCP 서버들을 이 레포에 등록했다.

- KOSIS와 달리 **단일 통합 API가 아니라 데이터셋별 개별 MCP 서버**다. 각 서버는
  `uvx data-go-mcp.<이름>@latest`로 격리 실행되며, 공통 환경변수 `API_KEY`를 받는다.
- 등록 설정: 레포 루트의 [`.mcp.json`](../.mcp.json)

## 등록된 서버 (전체 6개)

| MCP 서버 이름 | PyPI 패키지 | 데이터 |
|---|---|---|
| `data-go-nps-business-enrollment` | `data-go-mcp.nps-business-enrollment` | 국민연금 가입 사업장 정보 |
| `data-go-nts-business-verification` | `data-go-mcp.nts-business-verification` | 국세청 사업자등록 상태/진위확인 |
| `data-go-pps-narajangteo` | `data-go-mcp.pps-narajangteo` | 조달청 나라장터 입찰/조달 |
| `data-go-fsc-financial-info` | `data-go-mcp.fsc-financial-info` | 금융위 기업 재무정보 |
| `data-go-presidential-speeches` | `data-go-mcp.presidential-speeches` | 대통령기록관 연설기록 |
| `data-go-msds-chemical-info` | `data-go-mcp.msds-chemical-info` | 화학물질 안전정보(MSDS) |

## 왜 uvx 격리 / API_KEY 매핑 방식인가

- 각 패키지는 Python 3.10+ 를 요구한다. `uvx`로 격리 실행해 프로젝트 venv와 분리한다.
- 원본 서버들의 환경변수 이름은 모두 `API_KEY`(매우 일반적)다. 이름 충돌과 혼동을
  피하기 위해 `.env`에는 명시적인 **`DATA_GO_KR_API_KEY`** 하나만 두고,
  `.mcp.json`에서 각 서버에 `"API_KEY": "${DATA_GO_KR_API_KEY}"`로 주입한다.
- data.go.kr은 계정당 **일반 인증키(서비스키) 1개**를 발급하며, 그 키가 승인된 모든
  API에 공통으로 쓰인다. 따라서 6개 서버가 동일한 `DATA_GO_KR_API_KEY`를 공유한다.

## 1) data.go.kr 인증키 발급 + API별 활용신청

> ⚠️ KOSIS와 달리 **API마다 개별 활용신청이 필요**하다. 인증키는 하나지만, 각
> 데이터셋(위 6종)에 대해 "활용신청"을 해야 해당 API 호출이 승인된다.

1. <https://www.data.go.kr/> 로그인(회원가입 무료).
2. 사용하려는 데이터(예: "국세청 사업자등록 상태조회") 검색 → **활용신청**.
3. 마이페이지 → **데이터활용 → 인증키(일반 인증키, Encoding/Decoding)** 확인.
   - 보통 **Decoding** 키를 서비스키로 사용한다(서버 구현에 따라 다를 수 있으니
     인증 오류 시 Encoding 키로 교체해 본다).
4. 발급 키를 `.env`에 등록:

```bash
cp .env.example .env   # 최초 1회
# .env 파일에서 아래 값을 채운다
DATA_GO_KR_API_KEY=발급받은_인증키
```

`.env`는 `.gitignore`로 커밋 제외된다.

## 2) 동작 확인

레포 루트의 `.mcp.json`이 Claude Code에서 자동 감지된다. 세션에서 신뢰하면 위 6개
서버의 도구가 노출된다. (예: 사업자등록번호 진위확인, 입찰공고 조회 등 자연어 호출)

```bash
# 패키지 단독 실행 확인 (Python 3.10+ 자동 확보)
uvx data-go-mcp.nts-business-verification@latest
```

### 다른 클라이언트(Claude Desktop 등) 등록 예시

```json
{
  "mcpServers": {
    "data-go-nts-business-verification": {
      "command": "uvx",
      "args": ["data-go-mcp.nts-business-verification@latest"],
      "env": { "API_KEY": "발급받은_인증키" }
    }
  }
}
```

## 참고: 필요 없는 서버 제거

6개를 모두 등록했지만, 활용신청하지 않은 데이터셋 서버는 호출 시 인증 오류가 난다.
사용하지 않을 서버는 `.mcp.json`의 `mcpServers`에서 해당 항목을 삭제하면 된다.
