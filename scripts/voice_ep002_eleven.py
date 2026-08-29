"""
[보이스] episode-002 — 유나 대사 최종 (ElevenLabs v3 + 오디오 태그)

디렉션: 발랄하고 감정기복이 크고 들뜬 톤. 태그는 감정 단어가 아니라
연기 지문으로 쓴다. sigh 계열은 허탈하게 들려서 금지 — 기쁨은 터뜨린다.
감정 낙차(들뜸 → 5만 원 추락 → 재점화)가 이 영상의 리듬이다.

자막=대사 규칙: 여기 대사가 곧 자막이다. 태그([...])는 소리 연기일 뿐
자막에는 넣지 않는다.

실행: python3 -m scripts.voice_ep002_eleven
"""

import subprocess
import urllib.request
import json
from pathlib import Path

from rich.console import Console

import config
from src.providers.gemini_tts import duration_of

console = Console()

VOICE_ID = "Lb7qkOn5hF8p7qfCDH8q"  # 사용자 선택 (G)
MODEL = "eleven_v3"
OUT_DIR = Path("output/ep002/voice_g")

# (파일명, 대사(자막과 동일), 태그·안정성)
LINES = [
    ("01_hook_a", "우와… 이 잔 뭐야…", "[excited whisper, giddy]", 0.25),
    ("01_cool", "보기만 해도 시원하잖아…", "[giddy, delighted]", 0.25),
    ("01_imagine", "여기에 맥주 딱 하면…", "[playful, dreamy excitement]", 0.25),
    ("01_kya", "크으~", "[gleeful, savoring the imaginary sip]", 0.3),
    ("01_hook_b", "5만 원…?", "[stunned, deflating]", 0.3),
    ("02_sulk", "아무리 그래도 잔 하나에 5만 원은…", "[pouting, whiny but cute]", 0.3),
    ("03_idea", "혹시… 쿠팡…?", "[hushed, suspenseful hope building]", 0.3),
    ("03_yes", "2만 원?! 아싸!", "[overjoyed shout, jumping with joy]", 0.25),
    ("05_arrive", "왔다…!", "[thrilled gasp, giddy]", 0.3),
    ("08_kya", "캬아~", "[delighted refreshed exclamation, bursting with pleasure]", 0.25),
    ("08_final", "기다린 보람이 있잖아~!", "[triumphant, laughing with joy]", 0.3),
    ("08_best", "최고!", "[beaming, punchy cheer]", 0.3),
]

SILENCE = ("silenceremove=start_periods=1:start_silence=0.05:"
           "start_threshold=-45dB:detection=peak")


def synthesize(text: str, tags: str, stability: float, path: Path):
    body = json.dumps({
        "text": f"{tags} {text}",
        "model_id": MODEL,
        "voice_settings": {"stability": stability, "similarity_boost": 0.75},
    }).encode()
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        data=body, headers={"xi-api-key": config.ELEVENLABS_API_KEY,
                            "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = path.with_suffix(".raw.mp3")
        raw.write_bytes(response.read())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw),
                    "-af", f"{SILENCE},areverse,{SILENCE},areverse", str(path)],
                   check=True, capture_output=True)
    raw.unlink()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[bold blue]━━ 유나 보이스 (ElevenLabs {MODEL}) ━━[/bold blue]\n")
    total = 0.0
    for name, text, tags, stability in LINES:
        path = OUT_DIR / f"{name}.mp3"
        synthesize(text, tags, stability, path)
        dur = duration_of(path)
        total += dur
        console.print(f"  [green]✓[/green] {name:<11} {dur:>4.2f}초  “{text}”")
    console.print(f"\n[dim]총 발화 {total:.1f}초[/dim]\n")


if __name__ == "__main__":
    if not config.ELEVENLABS_API_KEY:
        console.print("[red]✗ ELEVENLABS_API_KEY가 .env에 없습니다.[/red]")
        raise SystemExit(1)
    main()
