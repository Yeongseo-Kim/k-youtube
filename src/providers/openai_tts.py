"""
[프로바이더] OpenAI TTS — 세린 보이스 생성

gpt-4o-mini-tts는 `instructions`로 톤을 직접 지시할 수 있다. 냉미녀 톤은
목소리 선택보다 지시문으로 잡히는 영역이라 이 모델을 쓴다.
(tts-1 계열은 instructions를 받지 않는다.)

대본: assets/serin/episode-001-voice.md
실행: python3 -m src.providers.openai_tts
"""

import subprocess
from pathlib import Path

from openai import OpenAI
from rich.console import Console

import config

console = Console()

# 컷별 대사 — (파일명, 영상 내 시작초, 대사)
# 시작초는 episode-001.mp4 기준. 조립 시 이 위치에 얹는다.
LINES = [
    ("01_hook_a", 0.4, "…또 누레졌네."),
    ("01_hook_b", 1.9, "닦아도 또 생기는 건, 이유가 있어."),
    ("02_id_a", 4.1, "이건 물때가 아니라 요석이야."),
    ("02_id_b", 6.5, "락스는 색만 빼거든."),
    ("03_fix_a", 9.2, "알칼리라 산으로 녹여야 돼."),
    ("03_fix_b", 11.8, "구연산 뿌리고, 휴지 덮어."),
    ("03_fix_c", 14.2, "세로면은 그냥 흘러내리거든."),
    ("04_result_a", 18.2, "이제 한 번만."),
    ("04_result_b", 20.0, "힘 안 줘도 벗겨져."),
    ("05_outro", 25.5, "…깨끗하네."),
]

# 마지막 줄만 톤이 미세하게 풀린다 — 갭모에가 이 한 줄에 걸려 있다
INSTRUCTIONS_BASE = (
    "Speak in a low, flat, composed female voice with minimal pitch variation. "
    "Let sentence endings fall, never rise. This is muttering to oneself, "
    "not addressing an audience — detached and matter-of-fact, no warmth, "
    "no perkiness. Speak slowly and deliberately, around 4.5 syllables per second."
)
INSTRUCTIONS_OUTRO = (
    INSTRUCTIONS_BASE
    + " For this final line only, let it soften just barely — a trace of quiet "
    "satisfaction, almost imperceptible. Still no smile in the voice."
)

OUT_DIR = Path("output/ep001/voice")


def synthesize(text: str, output_path: Path, instructions: str, voice: str = "sage") -> Path:
    """대사 한 줄을 음성 파일로 만든다."""
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    last_error = ""
    for attempt in range(1, 4):
        try:
            response = client.audio.speech.create(
                model=config.TTS_MODEL,
                voice=voice,
                input=text,
                instructions=instructions,
                response_format="mp3",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            response.stream_to_file(str(output_path))
            return output_path
        except Exception as exc:  # 외부 API는 어떤 예외든 재시도 대상
            last_error = str(exc)
            console.print(f"  [yellow]⚠ {attempt}회차 실패, 재시도: {exc}[/yellow]")

    raise RuntimeError(f"TTS 생성 실패 — {last_error}")


def duration_of(path: Path) -> float:
    """ffprobe로 오디오 길이를 잰다. 컷 길이를 넘기는지 확인하는 용도."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def run(voice: str = "sage") -> list[tuple[str, float, Path, float]]:
    """대본 전체를 컷별 음성 파일로 생성한다."""
    console.print(f"\n[bold blue]━━ 보이스 생성 (voice={voice}) ━━[/bold blue]\n")
    results = []

    for name, start, text in LINES:
        instructions = INSTRUCTIONS_OUTRO if name.startswith("05") else INSTRUCTIONS_BASE
        path = OUT_DIR / f"{name}.mp3"
        synthesize(text, path, instructions, voice)
        dur = duration_of(path)
        results.append((name, start, path, dur))
        console.print(f"  [green]✓[/green] {name}  {start:>5.1f}s  {dur:.1f}초  “{text}”")

    total = sum(r[3] for r in results)
    console.print(f"\n[dim]총 발화 {total:.1f}초 / 영상 28.6초[/dim]\n")
    return results


if __name__ == "__main__":
    if not config.OPENAI_API_KEY:
        console.print("[red]✗ OPENAI_API_KEY가 .env에 없습니다.[/red]")
        raise SystemExit(1)
    run()
