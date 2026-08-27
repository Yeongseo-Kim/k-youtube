---
description: 에피소드 제작 → 업로드 실행 방법
---

# 세린 파이프라인 실행 워크플로우

## 사전 요구사항
1. `.env`에 API 키 설정 (`.env.example` 참고 — ELEVENLABS · MODELARK · OPENAI · GEMINI)
2. `credentials/youtube_oauth.json` 존재
3. **시스템 ffmpeg** 설치 (`ffmpeg -version`) — imageio-ffmpeg 번들은 drawtext가 없어 사용 불가

## 에피소드 제작 흐름

1. **대본·에셋 준비** — `assets/serin/episode-NNN.md`(대본), `episode-NNN-voice.md`(보이스 노트), 캐릭터 레퍼런스는 `assets/serin/` 고정본 사용
2. **영상 컷 생성** — `src/providers/modelark_video.py` (image-to-video, 첫 프레임 확정 후 i2v)
3. **보이스·효과음·BGM** — `src/providers/elevenlabs_tts.py` (의미 단위로 묶어 생성), 오디션은 `src/providers/voice_audition.py`
4. **조립** — `src/assemble_ep001.py` (단일 ffmpeg filtergraph; 새 에피소드는 컷·보이스·자막·효과음 테이블 교체)
5. **업로드** — 산출물을 `output/<오늘날짜>/final_video.mp4` + `metadata.json`으로 배치 후:

```
python3 -m src.uploader --auth-only   # 최초 1회 또는 스코프 변경 시
python3 -m src.uploader
```

업로드 후 댓글은 자동 작성됨(`commentThreads.insert`). 댓글 **고정**은 API가 없어 스튜디오에서 수동 (⋮ → 고정).

## 주의사항
- 캐릭터 프레이밍은 가슴 위로 (전신은 콘텐츠 필터에 걸림, 전신 필요 시 치비)
- TTS 발음 교정표는 `assets/serin/` 참고 (예: "변기에" → 입력만 "병기에")
- `output/`은 git 미추적 — 생성물은 따로 백업
