"""
[보이스] episode-002 — 유나 대사 생성 (Gemini TTS)

자막=대사 규칙(branding.md §8)에 따라 여기 대사가 곧 자막 원본이다.
유나 톤은 세린과 정반대 — 하이톤·텐션 업다운 큼·감탄사 살림.
세린은 공통 STYLE 하나로 충분했지만 유나는 컷마다 감정이 널뛰므로
라인별 지시문을 쓴다.

실행: python3 -m scripts.voice_ep002          # 기본 보이스(Leda)
      python3 -m scripts.voice_ep002 Zephyr   # 다른 보이스로 오디션
"""

import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from rich.console import Console

import config
from src.providers.gemini_tts import GeminiTTSError, duration_of

console = Console()

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Leda"   # youthful — 세린(Zephyr)과 음색 분리
TEMPO = 1.05

BASE = (
    "A bright, high-energy young Korean woman in her mid-20s, like an anime "
    "character who lives for good food and drinks. High pitch, big pitch swings, "
    "emotions fully out, natural Korean. "
)

# (파일명, 영상 내 시작초(가안), 대사, 라인별 톤 지시)
LINES = [
    ("01_hook_a", 0.3, "우와… 이 잔 뭐야…",
     "Enchanted whisper — falling in love with an object at first sight, breathy awe."),
    ("01_hook_b", 2.8, "5만 원…?",
     "Stunned. The excitement dies instantly — flat, low, hollow disbelief."),
    ("02_sulk", 4.8, "아무리 그래도 잔 하나에 5만 원은…",
     "Deflated and sulky, trailing off with a small sigh, shoulders-drooping energy."),
    ("03_idea", 8.5, "혹시… 인터넷?!",
     "A lightbulb moment — starts hushed and suspicious, then bursts upward with hope."),
    ("03_yes", 10.8, "2만 원?! 아싸!",
     "Explosive cheer, jackpot joy, almost jumping. Maximum energy."),
    ("05_arrive", 14.8, "왔다…!",
     "Giddy anticipation boiling over, gasping with delight."),
    ("08_kya", 27.3, "캬아~",
     "The satisfied exhale right after downing a cold beer — long, refreshed, blissful."),
    ("08_final", 28.6, "기다린 보람이 있잖아~!",
     "Triumphant and overjoyed, almost singing the line, grinning audibly."),
    ("08_best", 31.2, "최고!",
     "One punchy, sparkling exclamation straight at the camera. Short and proud."),
]

OUT_DIR = Path("output/ep002/voice")


def request_audio(text: str, style: str, voice: str) -> bytes:
    body = {
        "contents": [{"parts": [{"text": f"{BASE}{style}\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
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
        raise GeminiTTSError(f"오디오 없음 (finishReason={candidate.get('finishReason')})")
    return base64.b64decode(parts[0]["inlineData"]["data"])


def synthesize(text: str, style: str, output_path: Path, voice: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""
    for attempt in range(1, 4):
        try:
            pcm = request_audio(text, style, voice)
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


def run(voice: str = VOICE):
    console.print(f"\n[bold blue]━━ 유나 보이스 생성 (Gemini / {voice} / x{TEMPO}) ━━[/bold blue]\n")
    results = []
    for name, start, text, style in LINES:
        path = synthesize(text, style, OUT_DIR / f"{name}.mp3", voice)
        dur = duration_of(path)
        results.append((name, start, dur))
        console.print(f"  [green]✓[/green] {name:<11}{start:>5.1f}s  {dur:>4.1f}초  “{text}”")

    console.print()
    prev_end = 0.0
    for name, start, dur in results:
        if start < prev_end:
            console.print(f"  [yellow]⚠ {name}: 앞 대사와 {prev_end - start:.1f}초 겹침[/yellow]")
        prev_end = start + dur
    console.print(f"\n[dim]총 발화 {sum(r[2] for r in results):.1f}초 / 영상 32초 "
                  f"(마지막 대사 끝 {prev_end:.1f}s)[/dim]\n")


if __name__ == "__main__":
    if not config.GEMINI_API_KEY:
        console.print("[red]✗ GEMINI_API_KEY가 .env에 없습니다.[/red]")
        raise SystemExit(1)
    run(sys.argv[1] if len(sys.argv) > 1 else VOICE)
