"""
[프로바이더] Gemini TTS — 세린 보이스 생성

gemini-3.1-flash-tts-preview는 SSML 대신 자연어 지시로 톤을 조절한다.
지시문을 대사 앞에 붙이면 모델이 그 연기로 읽는다.

출력은 24kHz 16bit mono PCM(base64)이라 ffmpeg으로 mp3 변환이 필요하다.

실행: python3 -m src.providers.gemini_tts
"""

import base64
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from rich.console import Console

import config

console = Console()

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Zephyr"
TEMPO = 1.12  # 생성 후 속도 보정 — atempo는 피치를 유지한다

# 채택된 톤(F3): 무억양이 핵심이다. "낮게"가 아니라 "평탄하게"여야
# 냉담함이 나온다 — 낮게 지시하면 음역만 내려가 걸걸해진다.
STYLE = (
    "Brisk, matter-of-fact pace — quick but not rushed, slightly clipped. "
    "Do not drag the syllables. Young woman muttering to herself. "
    "Completely flat monotone delivery. Zero melodic contour — every syllable lands on "
    "the same note. No rising inflection, no dramatic falls, no word stress. "
    "Emotionless but still human. She is stating a fact to herself and does not care."
)

# (파일명, 영상 내 시작초, 대사) — 시작초는 생성 후 실측으로 재조정한다
LINES = [
    ("01_hook_a", 0.5, "…또 누레졌네."),
    ("02_id_a", 4.2, "이건 물때가 아니라 요석이야."),
    ("02_id_b", 8.0, "락스는 색만 빼거든."),
    ("03_fix_a", 10.8, "알칼리라 산으로 녹여야 돼."),
    ("03_fix_b", 14.4, "구연산 뿌리고, 휴지 덮어."),
    ("04_result_a", 18.7, "이제 한 번만."),
    ("04_result_b", 20.7, "힘 안 줘도 벗겨져."),
    ("05_outro", 25.8, "…깨끗하네."),
]

OUT_DIR = Path("output/ep001/voice")


class GeminiTTSError(RuntimeError):
    """Gemini TTS 호출 실패."""


def _request_audio(text: str) -> bytes:
    """지시문 + 대사를 보내고 PCM 바이트를 받는다."""
    body = {
        "contents": [{"parts": [{"text": f"{STYLE}\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}
            },
        },
    }
    request = urllib.request.Request(
        f"{API_BASE}/{MODEL}:generateContent?key={config.GEMINI_API_KEY}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)

    candidate = (payload.get("candidates") or [{}])[0]
    parts = (candidate.get("content") or {}).get("parts")
    if not parts:
        # 안전 필터가 간헐적으로 오탐한다(대사 자체엔 문제가 없다). 재시도로 통과한다.
        raise GeminiTTSError(f"오디오 없음 (finishReason={candidate.get('finishReason')})")
    return base64.b64decode(parts[0]["inlineData"]["data"])


def synthesize(text: str, output_path: Path) -> Path:
    """대사 한 줄을 mp3로 만든다. 무음 트림과 속도 보정까지 끝낸다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    last_error = ""
    for attempt in range(1, 4):
        try:
            pcm = _request_audio(text)
            break
        except (GeminiTTSError, urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
            console.print(f"  [yellow]⚠ {attempt}회차 재시도: {exc}[/yellow]")
    else:
        raise GeminiTTSError(f"생성 실패 — {last_error}")

    raw = output_path.with_suffix(".pcm")
    raw.write_bytes(pcm)

    silence = ("silenceremove=start_periods=1:start_silence=0.05:"
               "start_threshold=-45dB:detection=peak")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw),
         "-af", f"{silence},areverse,{silence},areverse,atempo={TEMPO}",
         str(output_path)],
        check=True, capture_output=True,
    )
    raw.unlink()
    return output_path


def duration_of(path: Path) -> float:
    """오디오 길이(초)."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def run() -> list[tuple[str, float, Path, float]]:
    """대본 전체를 컷별 음성 파일로 생성하고 겹침을 검사한다."""
    console.print(f"\n[bold blue]━━ 보이스 생성 (Gemini / {VOICE} / x{TEMPO}) ━━[/bold blue]\n")
    results = []

    for name, start, text in LINES:
        path = synthesize(text, OUT_DIR / f"{name}.mp3")
        dur = duration_of(path)
        results.append((name, start, path, dur))
        console.print(f"  [green]✓[/green] {name:<13}{start:>5.1f}s  {dur:>4.1f}초  “{text}”")

    console.print()
    prev_end = 0.0
    for name, start, _, dur in results:
        if start < prev_end:
            console.print(f"  [yellow]⚠ {name}: 앞 대사와 {prev_end - start:.1f}초 겹침[/yellow]")
        prev_end = start + dur

    console.print(f"\n[dim]총 발화 {sum(r[3] for r in results):.1f}초 / 영상 28.6초 "
                  f"(마지막 대사 끝 {prev_end:.1f}s)[/dim]\n")
    return results


if __name__ == "__main__":
    if not config.GEMINI_API_KEY:
        console.print("[red]✗ GEMINI_API_KEY가 .env에 없습니다.[/red]")
        raise SystemExit(1)
    run()
