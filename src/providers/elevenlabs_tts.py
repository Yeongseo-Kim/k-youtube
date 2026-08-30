"""
[프로바이더] ElevenLabs TTS — 세린 보이스 생성

Gemini/OpenAI는 톤을 자연어 지시로만 조절하는데, ElevenLabs는 수치 파라미터를
제공한다. 특히 stability가 높을수록 억양 변화가 줄어 무억양에 가까워진다 —
지금 필요한 "평탄한 톤"을 프롬프트로 빌지 않고 직접 잡을 수 있다.

실행:
    python3 -m src.providers.elevenlabs_tts voices   # 보유 음성 + 한국어 라이브러리 조회
    python3 -m src.providers.elevenlabs_tts test <voice_id>   # 톤 3종 비교 샘플
    python3 -m src.providers.elevenlabs_tts run <voice_id>    # 대본 8줄 생성
"""

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from rich.console import Console

import config
from src.providers.gemini_tts import LINES, duration_of

console = Console()

API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"  # 한국어 지원 다국어 모델
OUT_DIR = Path("output/ep001/voice")
TEST_DIR = Path("output/ep001/eleven_test")

# stability를 올릴수록 억양이 평탄해진다. style은 감정 과장이라 0으로 둔다.
TONE_PRESETS = {
    "flat_max": {"stability": 1.0, "similarity_boost": 0.75, "style": 0.0,
                 "use_speaker_boost": True, "speed": 1.05},
    "flat_high": {"stability": 0.85, "similarity_boost": 0.75, "style": 0.0,
                  "use_speaker_boost": True, "speed": 1.05},
    "flat_mid": {"stability": 0.65, "similarity_boost": 0.8, "style": 0.0,
                 "use_speaker_boost": True, "speed": 1.0},
}


class ElevenLabsError(RuntimeError):
    """ElevenLabs API 호출 실패."""


def _get(path: str, params: dict | None = None) -> dict:
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"xi-api-key": config.ELEVENLABS_API_KEY})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise ElevenLabsError(f"HTTP {exc.code}: {exc.read().decode()[:300]}") from exc


def list_voices() -> None:
    """계정에 추가된 음성과, 라이브러리의 한국어 음성을 함께 보여준다."""
    mine = _get("/voices").get("voices", [])
    console.print(f"\n[bold]내 음성 {len(mine)}개[/bold]")
    for v in mine:
        labels = v.get("labels") or {}
        tags = ", ".join(f"{k}={x}" for k, x in labels.items() if x)
        console.print(f"  {v['name']:<22} {v['voice_id']}  [dim]{tags}[/dim]")

    try:
        shared = _get("/shared-voices", {"language": "ko", "page_size": 25}).get("voices", [])
        console.print(f"\n[bold]라이브러리 한국어 음성 {len(shared)}개[/bold] "
                      f"[dim](쓰려면 웹에서 Add to My Voices 필요)[/dim]")
        for v in shared:
            console.print(f"  {v.get('name',''):<22} {v.get('voice_id','')}  "
                          f"[dim]{v.get('gender','')} / {v.get('age','')} / "
                          f"{v.get('descriptive','')}[/dim]")
    except ElevenLabsError as exc:
        console.print(f"[yellow]⚠ 라이브러리 조회 실패: {exc}[/yellow]")


def synthesize(text: str, voice_id: str, output_path: Path, settings: dict) -> Path:
    """대사 한 줄을 mp3로 만든다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": settings,
    }).encode()
    request = urllib.request.Request(
        f"{API}/text-to-speech/{voice_id}",
        data=body,
        headers={"xi-api-key": config.ELEVENLABS_API_KEY,
                 "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
    )

    last_error = ""
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                output_path.write_bytes(response.read())
            return _trim(output_path)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            detail = exc.read().decode()[:200] if isinstance(exc, urllib.error.HTTPError) else str(exc)
            last_error = detail
            console.print(f"  [yellow]⚠ {attempt}회차 재시도: {detail}[/yellow]")
    raise ElevenLabsError(f"생성 실패 — {last_error}")


def _trim(path: Path) -> Path:
    """앞뒤 무음 제거 — 타이밍을 초 단위로 맞추려면 필수다."""
    silence = ("silenceremove=start_periods=1:start_silence=0.05:"
               "start_threshold=-45dB:detection=peak")
    tmp = path.with_suffix(".trim.mp3")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path),
         "-af", f"{silence},areverse,{silence},areverse", str(tmp)],
        check=True, capture_output=True,
    )
    tmp.replace(path)
    return path


def test_tones(voice_id: str) -> None:
    """stability 3단계를 한 파일로 이어 붙여 비교용 샘플을 만든다."""
    text = "이건 물때가 아니라 요석이야. 락스는 색만 빼거든."
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    files = []
    for name, settings in TONE_PRESETS.items():
        path = synthesize(text, voice_id, TEST_DIR / f"{name}.mp3", settings)
        files.append(path)
        console.print(f"  [green]✓[/green] {name:<11} stability={settings['stability']}  "
                      f"{duration_of(path):.2f}초")

    inputs, filters = [], []
    for i, path in enumerate(files):
        inputs += ["-i", str(path)]
        filters.append(f"[{i}:a]apad=pad_dur=0.9[p{i}]")
    chain = (";".join(filters) + ";" + "".join(f"[p{i}]" for i in range(len(files)))
             + f"concat=n={len(files)}:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", chain,
                    "-map", "[out]", str(TEST_DIR / "compare.mp3")], check=True)
    console.print(f"\n순서: {' → '.join(f.stem for f in files)}")


def run(voice_id: str, preset: str = "flat_high") -> None:
    """대본 8줄을 생성하고 겹침을 검사한다."""
    settings = TONE_PRESETS[preset]
    console.print(f"\n[bold blue]━━ 보이스 생성 (ElevenLabs / {preset}) ━━[/bold blue]\n")

    results = []
    for name, start, text in LINES:
        path = synthesize(text, voice_id, OUT_DIR / f"{name}.mp3", settings)
        dur = duration_of(path)
        results.append((name, start, dur))
        console.print(f"  [green]✓[/green] {name:<13}{start:>5.1f}s  {dur:>4.1f}초  “{text}”")

    console.print()
    prev_end = 0.0
    for name, start, dur in results:
        if start < prev_end:
            console.print(f"  [yellow]⚠ {name}: 앞 대사와 {prev_end - start:.1f}초 겹침[/yellow]")
        prev_end = start + dur
    console.print(f"\n[dim]총 발화 {sum(r[2] for r in results):.1f}초 / 영상 28.6초[/dim]\n")


if __name__ == "__main__":
    if not config.ELEVENLABS_API_KEY:
        console.print("[red]✗ ELEVENLABS_API_KEY가 .env에 없습니다.[/red]")
        raise SystemExit(1)

    command = sys.argv[1] if len(sys.argv) > 1 else "voices"
    if command == "voices":
        list_voices()
    elif command == "test":
        test_tones(sys.argv[2])
    elif command == "run":
        run(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "flat_high")
    else:
        console.print(f"[red]알 수 없는 명령: {command}[/red]")
