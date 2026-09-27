# comfyui-music — 내 컴퓨터에서 무료로 AI 노래 자동 생성 (ComfyUI + YuE2)

유튜브 「Suno 말고 내 컴에서 무료로! 말 한마디로 AI 음악 자동 생성 (YuE2 + 코덱스)」(행글라이터)
내용을 그대로 자동화한 폴더임. 준비물은 세 가지:

| # | 준비물 | 이 폴더에서 처리하는 방법 |
|---|---|---|
| 1 | AI 앱 (코덱스 · 클로드 코드 · 안티그래비티 중 하나) | 이 폴더를 열면 `AGENTS.md` / `CLAUDE.md` 지침을 읽고 "노래 만들어줘" 한마디로 동작 |
| 2 | ComfyUI 포터블 **v0.36 이상** | `install_windows.ps1` 이 설치하거나, 기존 설치본을 stable 로 업데이트 |
| 3 | 음악 모델 `yue2_3b_int8_convrot.safetensors` (3.96GB) | 설치 스크립트가 `ComfyUI/models/checkpoints` 로 자동 다운로드 |

> 모델 출처: <https://huggingface.co/Comfy-Org/YuE2> → `checkpoints` 폴더.
> 같은 폴더의 bf16 버전(7.8GB)은 그래픽카드 12GB 이상용. 8GB 카드에서는 10배 느려지므로 int8 버전을 기본으로 씀.

## 1. 설치 (최초 1회)

### Windows (권장)

```powershell
cd comfyui-music
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

- 그래픽카드를 자동 판별해 NVIDIA / AMD / Intel 용 포터블을 받음 (`-Gpu nvidia` 처럼 강제 지정 가능).
- 이미 ComfyUI 포터블이 있다면: `-ComfyRoot "D:\ComfyUI_windows_portable"` → 업데이트 + 모델만 추가.
- 다운로드가 끊겨도 다시 실행하면 이어받음.
- 끝나면 `config.json`, `start_comfyui.bat`, `make_song.bat` 가 생김.

### Linux / macOS

```bash
bash comfyui-music/install_linux_mac.sh ~/ComfyUI
```

## 2. 노래 만들기

### (A) AI 앱에게 말로 시키기 — 영상 방식

코덱스/클로드 코드에서 `comfyui-music` 폴더를 열고:

> "비 오는 날 듣기 좋은 잔잔한 한국어 발라드 하나 만들어줘. 여자 보컬로 2분 30초."

AI 가 `AGENTS.md` 지침대로 가사·스타일을 써서 `songs/*.json` 을 만들고
`generate_music.py` 를 실행해 `output/` 에 mp3 를 떨궈 줌.

### (B) 직접 실행

```bash
# 곡 정의 파일로
python generate_music.py --song songs/example_ko_ballad.json

# 명령줄로 바로
python generate_music.py --title "여름밤" \
  --style "Korean, male vocal, city pop, 110 BPM, electric piano, slap bass, drums" \
  --lyrics-file my_lyrics.txt --duration 180 --count 2
```

Windows 포터블 사용자는 `python` 대신 `config.json` 의 `python` 경로
(`...\python_embeded\python.exe -s`)를 쓰거나 `make_song.bat songs\파일.json` 을 더블클릭/실행.

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--duration` | 120 | 최대 길이(초). 곡 구조에 따라 더 일찍 끝날 수 있음 |
| `--mode` | full | `full`=멜로디+코드 계획, `melody`=멜로디만 |
| `--no-abc` | (꺼짐) | ABC 악보 계획 단계 생략 → 빠르지만 구조가 덜 탄탄 |
| `--format` | mp3 | mp3 / flac / opus |
| `--count` | 1 | 시드를 1씩 바꿔 여러 곡 생성 |
| `--seed` | 랜덤 | 같은 시드 + 같은 설정이면 같은 결과 |
| `--print-workflow` | | ComfyUI API 워크플로우 JSON 만 출력 |

결과물: `output/<제목>_00001.mp3` + 같은 이름의 `.json`(생성 설정), `.abc`(악보 계획).

## 3. 동작 구조

ComfyUI 공식 템플릿 `audio_yue2_text2music` 과 같은 그래프를 API 로 실행함.

```
CheckpointLoaderSimple(yue2_3b_int8_convrot)
 ├─ CLIP ─► YuE2GenerateABC (style, lyrics) ─► abc 악보
 │          └──────────────► YuE2GenerateMusic (style, lyrics, abc) ─► conditioning, seconds
 │                                          seconds ─► EmptyYuE2LatentAudio
 ├─ MODEL ─► KSampler (32 steps, cfg 1, dpm_2, sgm_uniform)
 └─ VAE ───► VAEDecodeAudio ─► SaveAudioAdvanced(mp3)
```

ComfyUI 화면에서 직접 해보고 싶으면: 상단 메뉴 **Workflow → Browse Templates → Audio → YuE2 Text to Music**.

## 4. 스타일 작성 요령

`언어 + 장르 + 보컬 + 템포 + 악기 + 분위기` (영어로)

```
Korean, warm female vocal, emotional ballad, 72 BPM, piano, soft strings, nostalgic
Korean, powerful male vocal, rock, 140 BPM, distorted guitars, bass, live drums, energetic
English, airy female vocal, lo-fi chill pop, 85 BPM, rhodes, vinyl crackle, soft beat
```

가사는 `[Verse]` `[Chorus]` `[Bridge]` `[Outro]` 태그로 나누고 **부를 가사만** 넣을 것.

## 5. 문제 해결

| 증상 | 해결 |
|---|---|
| `YuE2GenerateMusic` 노드 없음 / 빨간 노드 | ComfyUI 가 v0.36 미만 → `update\update_comfyui_stable.bat` |
| 모델 목록에 yue2 없음 | `ComfyUI\models\checkpoints` 에 파일이 있는지, 크기가 3.96GB 인지 확인 |
| 그래픽카드 메모리 부족 | `--duration` 줄이기, `--no-abc`, 다른 프로그램 종료 |
| ComfyUI 가 안 켜짐 | NVIDIA 드라이버 최신화, VC++ 재배포 패키지 설치 (<https://aka.ms/vc14/vc_redist.x64.exe>) |
| 자동 실행 로그 | `comfyui-music/comfyui.log` |
