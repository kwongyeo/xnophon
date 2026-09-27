# AI 앱용 작업 지침 — ComfyUI YuE2 노래 자동 생성

이 폴더는 로컬 ComfyUI + YuE2 모델로 노래를 만드는 자동화 도구임.
사용자가 "○○한 노래 만들어줘"라고 하면 아래 순서를 그대로 따를 것.

## 0. 최초 1회 설치 (config.json 이 없을 때만)

- Windows: `powershell -ExecutionPolicy Bypass -File .\install_windows.ps1`
  - 기존 포터블이 있으면 `-ComfyRoot "경로\ComfyUI_windows_portable"` 추가
- Linux/macOS: `bash install_linux_mac.sh`
- 설치가 끝나면 `config.json` 이 생김. 모델 파일은
  `ComfyUI/models/checkpoints/yue2_3b_int8_convrot.safetensors` (3.96GB).

## 1. 곡 정의 파일 만들기

`songs/<영문-슬러그>.json` 으로 저장. 형식은 `songs/example_ko_ballad.json` 참고.

| 키 | 설명 |
|---|---|
| `title` | 곡 제목 (출력 파일명) |
| `style` | **영어로**, `언어 + 장르 + 보컬 + BPM + 악기 + 분위기` 순서. 예: `Korean, warm female vocal, K-pop ballad, 72 BPM, piano, strings` |
| `lyrics` | 줄 배열 또는 문자열. `[Verse]` `[Chorus]` `[Bridge]` `[Outro]` 태그로 구성. **노래로 부를 가사만** 넣고 연주 지시는 style 에 둘 것 |
| `duration` | 최대 길이(초). 기본 120, 가사 길이에 맞춰 90~240 권장 |
| `mode` | `full`(멜로디+코드, 기본) / `melody`(멜로디만) |
| `abc_planning` | `true`(기본, 품질↑) / `false`(더 빠름) |
| `format` | `mp3`(기본) / `flac` / `opus` |

가사 작성 규칙
- 한국어 노래면 style 첫 단어를 `Korean` 으로.
- 한 줄은 짧게(8~14음절), 후렴은 반복해서 기억에 남게.
- 사용자가 가사를 직접 주면 그대로 쓰고 섹션 태그만 붙일 것.

## 2. 생성 실행

```
# Windows (포터블 내장 파이썬)
<config.json 의 python> -s generate_music.py --song songs/<파일>.json
# Linux/macOS
python3 generate_music.py --song songs/<파일>.json
```

- ComfyUI 가 꺼져 있으면 스크립트가 config.json 을 보고 자동 실행함.
- 여러 버전을 원하면 `--count 3` (시드만 바꿔 3곡).
- 결과: `output/<제목>_00001.mp3` 와 같은 이름의 `.json`(설정) · `.abc`(악보 계획).
- 생성 시간: RTX 4070 8GB 노트북 기준 2분짜리 곡이 약 80초(영상 설명 기준). 끝날 때까지 기다린 뒤 파일 경로를 사용자에게 알려줄 것.

## 3. 문제 해결

- `models/checkpoints 에 ... 가 없음` → 설치 스크립트 재실행(이어받기 됨).
- `YuE2GenerateMusic` 노드를 모른다는 오류 → ComfyUI 가 v0.36 미만. `update\update_comfyui_stable.bat` 실행.
- VRAM 부족(OOM) → `duration` 을 줄이거나 `abc_planning:false`.
- 결과가 가사를 무시함 → style 을 더 구체적으로, 가사를 더 짧게.
