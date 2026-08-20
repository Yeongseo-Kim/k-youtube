"""
[유틸] 보이스 오디션 — ElevenLabs 음성 하나로 대본 전체를 뽑아 미리듣기 트랙을 만든다.

오디션은 반드시 본생성과 같은 조건이어야 한다. 짧은 문장을 따로 생성하면
각 문장이 완결된 낭독조가 되어, 문장을 묶어 들었던 인상과 달라진다.
그래서 여기서도 의미 단위 그룹을 그대로 쓴다.

실행: python3 -m src.providers.voice_audition <voice_id> [stability]
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from rich.console import Console

import config

console = Console()

API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"
VIDEO_LEN = 28.6
SILENCE = ("silenceremove=start_periods=1:start_silence=0.05:"
           "start_threshold=-45dB:detection=peak")

# (그룹명, 영상 내 시작초, 대사) — 문장을 쪼개지 않고 묶어서 생성한다
GROUPS = [
    ("G1", 0.5, "…또 누레졌네."),
    ("G2", 4.2, "이건 물때가 아니라 요석이야. 락스는 소용없어."),
    ("G3", 10.8, "알칼리라 산으로 녹여야 돼. 구연산 뿌리고, 휴지 준비해."),
    ("G4", 18.7, "30초 세고 닦으면 싹 사라져."),
    ("G5", 25.8, "…깨끗하지?"),
]


def synthesize(voice_id: str, text: str, output_path: Path, stability: float) -> Path | None:
    """대사 한 그룹을 mp3로 만들고 앞뒤 무음을 잘라낸다."""
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": {
            "stability": stability, "similarity_boost": 0.75, "style": 0.0,
            "use_speaker_boost": True, "speed": 1.05,
        },
    }).encode()
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY,
               "Content-Type": "application/json", "Accept": "audio/mpeg"}

    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                f"{API}/text-to-speech/{voice_id}", data=body, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                output_path.write_bytes(response.read())
            break
        except urllib.error.HTTPError as exc:
            console.print(f"  [yellow]⚠ {attempt}회차 {exc.code}: "
                          f"{exc.read().decode()[:120]}[/yellow]")
    else:
        return None

    trimmed = output_path.with_suffix(".trim.mp3")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(output_path),
         "-af", f"{SILENCE},areverse,{SILENCE},areverse", str(trimmed)],
        check=True, capture_output=True,
    )
    trimmed.replace(output_path)
    return output_path


def duration_of(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def audition(voice_id: str, stability: float = 0.85) -> Path:
    """음성 하나로 대본 전체를 뽑고, 실제 타이밍에 배치한 트랙을 만든다."""
    out_dir = Path(f"output/ep001/audition/{voice_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[bold blue]━━ 오디션 {voice_id} (stability={stability}) ━━[/bold blue]\n")

    placed, prev_end = [], 0.0
    for name, start, text in GROUPS:
        path = synthesize(voice_id, text, out_dir / f"{name}.mp3", stability)
        if not path:
            console.print(f"  [red]✗ {name} 생성 실패[/red]")
            continue
        dur = duration_of(path)
        overlap = "[yellow]⚠ 겹침[/yellow]" if start < prev_end else "ok"
        console.print(f"  [green]✓[/green] {name}  {start:>5.1f}s +{dur:.1f} "
                      f"= {start + dur:>5.1f}s  {overlap}")
        placed.append((start, path))
        prev_end = start + dur

    # 영상 길이만큼의 무음 위에 각 그룹을 시작 초에 얹는다
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono", "-t", str(VIDEO_LEN)]
    for _, path in placed:
        args += ["-i", str(path)]
    delays = "".join(f"[{i + 1}:a]adelay={int(s * 1000)}|{int(s * 1000)}[a{i}];"
                     for i, (s, _) in enumerate(placed))
    mix = "".join(f"[a{i}]" for i in range(len(placed)))
    track = out_dir / "track_preview.mp3"
    subprocess.run(
        args + ["-filter_complex",
                f"{delays}[0:a]{mix}amix=inputs={len(placed) + 1}:normalize=0[o]",
                "-map", "[o]", "-t", str(VIDEO_LEN), str(track)],
        check=True, capture_output=True,
    )

    total = sum(duration_of(p) for _, p in placed)
    console.print(f"\n[dim]총 발화 {total:.1f}초 / {VIDEO_LEN}초  →  {track}[/dim]\n")
    return track


if __name__ == "__main__":
    if not config.ELEVENLABS_API_KEY:
        console.print("[red]✗ ELEVENLABS_API_KEY가 .env에 없습니다.[/red]")
        raise SystemExit(1)
    if len(sys.argv) < 2:
        console.print("[red]사용법: python3 -m src.providers.voice_audition "
                      "<voice_id> [stability][/red]")
        raise SystemExit(1)
    audition(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.85)
