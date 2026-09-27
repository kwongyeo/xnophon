#!/usr/bin/env python3
"""ComfyUI + YuE2 음악 자동 생성 클라이언트.

실행 중인 ComfyUI 서버의 API(/prompt)에 YuE2 Text-to-Music 워크플로우를 보내고,
완성된 음악 파일을 ./output 폴더로 내려받는다. 표준 라이브러리만 사용한다.

예시:
    python generate_music.py --song songs/example_ko_ballad.json
    python generate_music.py --style "Korean, female vocal, ballad, 72 BPM, piano" \
        --lyrics-file lyrics.txt --duration 150 --format mp3

ComfyUI가 꺼져 있으면 config.json의 comfy_dir(설치 스크립트가 기록)을 이용해
자동으로 서버를 띄운다.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
DEFAULT_CKPT = "yue2_3b_int8_convrot.safetensors"

# 공식 템플릿(audio_yue2_text2music.json)의 기본값
KSAMPLER = {"steps": 32, "cfg": 1.0, "sampler_name": "dpm_2", "scheduler": "sgm_uniform", "denoise": 1.0}
ABC_PARAMS = {"max_abc_tokens": 8192, "temperature": 0.7, "top_p": 0.9, "top_k": 30,
              "repetition_penalty": 1.005, "penalty_window": 100}
MUSIC_PARAMS = {"temperature": 1.0, "top_p": 0.95, "top_k": 100, "repetition_penalty": 1.2}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def build_workflow(style: str, lyrics: str, *, seed: int, mode: str, abc_planning: bool,
                   duration: float, ckpt: str, fmt: str, prefix: str) -> dict:
    """YuE2 Text-to-Music API 워크플로우를 만든다 (ComfyUI 공식 템플릿과 동일한 그래프)."""
    wf: dict = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "3": {"class_type": "YuE2GenerateMusic", "inputs": {
            "clip": ["1", 1], "style": style, "lyrics": lyrics, "abc": "",
            "seed": seed, "mode": mode, "max_duration": duration, **MUSIC_PARAMS}},
        "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
        "5": {"class_type": "EmptyYuE2LatentAudio", "inputs": {"seconds": ["3", 1], "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, **KSAMPLER,
            "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveAudioAdvanced", "inputs": {
            "audio": ["7", 0], "filename_prefix": prefix, "format": fmt}},
    }
    if fmt == "mp3":
        wf["8"]["inputs"]["format.quality"] = "V0"
    elif fmt == "opus":
        wf["8"]["inputs"]["format.quality"] = "128k"
    if abc_planning:
        # 1단계: 멜로디/코드 악보(ABC) 계획 → 2단계: 그 악보로 실제 오디오 생성
        wf["2"] = {"class_type": "YuE2GenerateABC", "inputs": {
            "clip": ["1", 1], "style": style, "lyrics": lyrics, "seed": seed, "mode": mode, **ABC_PARAMS}}
        wf["3"]["inputs"]["abc"] = ["2", 0]
        wf["9"] = {"class_type": "PreviewAny", "inputs": {"source": ["2", 0]}}
    return wf


class ComfyClient:
    def __init__(self, server: str):
        self.base = server.rstrip("/")
        if not self.base.startswith("http"):
            self.base = "http://" + self.base

    def _req(self, path: str, data: dict | None = None, timeout: float = 30):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=body,
                                     headers={"Content-Type": "application/json"} if body else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def alive(self) -> bool:
        try:
            self._req("/system_stats", timeout=3)
            return True
        except (urllib.error.URLError, OSError):
            return False

    def system_stats(self) -> dict:
        return json.loads(self._req("/system_stats"))

    def checkpoints(self) -> list[str]:
        info = json.loads(self._req("/object_info/CheckpointLoaderSimple"))
        return info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]

    def queue(self, workflow: dict, client_id: str) -> str:
        try:
            res = json.loads(self._req("/prompt", {"prompt": workflow, "client_id": client_id}))
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise SystemExit(f"[오류] ComfyUI가 워크플로우를 거부함 (HTTP {e.code}):\n{detail}")
        return res["prompt_id"]

    def history(self, prompt_id: str) -> dict | None:
        return json.loads(self._req(f"/history/{prompt_id}")).get(prompt_id)

    def download(self, item: dict, dest: Path) -> Path:
        q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                                    "type": item.get("type", "output")})
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._req(f"/view?{q}", timeout=300))
        return dest


def start_comfy(cfg: dict, client: ComfyClient, wait: int = 300) -> subprocess.Popen | None:
    comfy_dir = cfg.get("comfy_dir")
    python = cfg.get("python")
    if not comfy_dir or not python:
        return None
    main_py = Path(comfy_dir) / "main.py"
    if not main_py.exists():
        return None
    port = urllib.parse.urlparse(client.base).port or 8188
    args = [python, "-s", str(main_py), "--port", str(port)] + cfg.get("extra_args", [])
    log = open(HERE / "comfyui.log", "ab")
    print(f"[정보] ComfyUI 서버가 꺼져 있어 자동 실행함: {' '.join(args)}")
    proc = subprocess.Popen(args, cwd=str(Path(comfy_dir).parent), stdout=log, stderr=subprocess.STDOUT)
    for _ in range(wait):
        if client.alive():
            print("[정보] ComfyUI 서버 준비 완료")
            return proc
        if proc.poll() is not None:
            raise SystemExit(f"[오류] ComfyUI 실행 실패. 로그 확인: {HERE / 'comfyui.log'}")
        time.sleep(1)
    raise SystemExit("[오류] ComfyUI 서버가 시간 안에 뜨지 않음")


def slugify(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|\s]+", "_", text.strip())
    return text[:60] or "song"


def main() -> None:
    cfg = load_config()
    p = argparse.ArgumentParser(description="ComfyUI YuE2로 노래 자동 생성")
    p.add_argument("--song", help="곡 정의 JSON 파일 (title/style/lyrics/duration 등)")
    p.add_argument("--title", help="곡 제목 (파일명에 사용)")
    p.add_argument("--style", help="음악 스타일 설명 (언어, 장르, 보컬, BPM, 악기)")
    p.add_argument("--lyrics", help="가사 ([Verse]/[Chorus] 태그 포함)")
    p.add_argument("--lyrics-file", help="가사 텍스트 파일")
    p.add_argument("--duration", type=float, help="최대 길이(초), 기본 120")
    p.add_argument("--seed", type=int, help="시드 (생략 시 랜덤)")
    p.add_argument("--mode", choices=["full", "melody"], help="ABC 계획 모드 (full=멜로디+코드)")
    p.add_argument("--no-abc", action="store_true", help="ABC 악보 계획 단계 생략 (더 빠름)")
    p.add_argument("--format", choices=["mp3", "flac", "opus"], help="저장 형식 (기본 mp3)")
    p.add_argument("--count", type=int, default=1, help="시드를 바꿔 몇 곡 만들지")
    p.add_argument("--ckpt", default=cfg.get("ckpt", DEFAULT_CKPT), help="체크포인트 파일명")
    p.add_argument("--server", default=cfg.get("server", "127.0.0.1:8188"), help="ComfyUI 주소")
    p.add_argument("--out", default=str(HERE / "output"), help="결과 저장 폴더")
    p.add_argument("--print-workflow", action="store_true", help="워크플로우 JSON만 출력하고 종료")
    a = p.parse_args()

    song: dict = {}
    if a.song:
        song = json.loads(Path(a.song).read_text(encoding="utf-8"))
    title = a.title or song.get("title") or "song"
    style = a.style or song.get("style")
    lyrics = a.lyrics or song.get("lyrics")
    if a.lyrics_file:
        lyrics = Path(a.lyrics_file).read_text(encoding="utf-8")
    if isinstance(lyrics, list):
        lyrics = "\n".join(lyrics)
    if not style or not lyrics:
        p.error("style 과 lyrics 가 필요함 (--song 또는 --style/--lyrics)")
    duration = a.duration or song.get("duration", 120)
    mode = a.mode or song.get("mode", "full")
    abc = not (a.no_abc or song.get("abc_planning") is False)
    fmt = a.format or song.get("format", "mp3")
    base_seed = a.seed if a.seed is not None else song.get("seed", random.randint(0, 2**48))
    prefix = f"YuE2/{slugify(title)}"

    if a.print_workflow:
        wf = build_workflow(style, lyrics, seed=base_seed, mode=mode, abc_planning=abc,
                            duration=duration, ckpt=a.ckpt, fmt=fmt, prefix=prefix)
        print(json.dumps(wf, ensure_ascii=False, indent=2))
        return

    client = ComfyClient(a.server)
    if not client.alive():
        if start_comfy(cfg, client) is None:
            raise SystemExit(f"[오류] ComfyUI({client.base})에 연결할 수 없음. 먼저 ComfyUI를 실행하거나 "
                             "install 스크립트로 config.json을 만들어 주세요.")
    ver = client.system_stats().get("system", {}).get("comfyui_version", "?")
    print(f"[정보] ComfyUI 버전: {ver}")
    if a.ckpt not in client.checkpoints():
        raise SystemExit(f"[오류] models/checkpoints 에 {a.ckpt} 가 없음. 모델을 먼저 넣어 주세요.")

    out_dir = Path(a.out)
    client_id = str(uuid.uuid4())
    for i in range(a.count):
        seed = base_seed + i
        wf = build_workflow(style, lyrics, seed=seed, mode=mode, abc_planning=abc,
                            duration=duration, ckpt=a.ckpt, fmt=fmt, prefix=prefix)
        pid = client.queue(wf, client_id)
        print(f"[{i + 1}/{a.count}] 생성 요청 완료 (prompt_id={pid}, seed={seed}) — 기다리는 중...")
        t0 = time.time()
        while True:
            h = client.history(pid)
            if h and h.get("status", {}).get("completed") or (h and h.get("status", {}).get("status_str") == "error"):
                break
            time.sleep(3)
            if int(time.time() - t0) % 60 < 3:
                print(f"    ... {int(time.time() - t0)}초 경과")
        status = h.get("status", {})
        if status.get("status_str") == "error":
            for kind, msg in status.get("messages", []):
                if kind == "execution_error":
                    raise SystemExit(f"[오류] 생성 실패: {msg.get('node_type')}: {msg.get('exception_message')}")
            raise SystemExit("[오류] 생성 실패 (ComfyUI 콘솔 확인)")
        outputs = h.get("outputs", {})
        saved = []
        for item in outputs.get("8", {}).get("audio", []):
            saved.append(client.download(item, out_dir / item["filename"]))
        abc_text = "".join(outputs.get("9", {}).get("text", []))
        for f in saved:
            meta = {"title": title, "style": style, "lyrics": lyrics, "seed": seed, "mode": mode,
                    "abc_planning": abc, "duration": duration, "elapsed_sec": round(time.time() - t0, 1)}
            f.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            if abc_text:
                f.with_suffix(".abc").write_text(abc_text, encoding="utf-8")
            print(f"[완료] {f}  ({time.time() - t0:.0f}초)")
        if not saved:
            print("[경고] 출력 오디오를 찾지 못함:", json.dumps(outputs)[:500])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
