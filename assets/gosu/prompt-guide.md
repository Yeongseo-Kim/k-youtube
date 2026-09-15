# 영상 프롬프트 작성 규칙 (공식 문서 기반)

출처는 항목마다 표기. [공식]은 모델 제공사 문서, [실무]는 검증된 실무 가이드.

## 0. 우리 실패의 원인 (2026-09-14)

지금까지 쓰던 프롬프트는 한 컷에 100단어 넘게, 인물·피부·의상·필름스톡·톤·카메라·소리를
전부 담았다. 이게 연출이 밋밋한 주된 이유다.

- **[공식] image-to-video에서 이미지에 이미 있는 것을 다시 묘사하면 안 된다.**
  Google Veo 문서: "Re-describe the character, the background, or the lighting depicted in
  the image ... **Redundant prompts confuse the model and lead to poor results.**"
  인물은 `the subject`, `the old man` 같은 일반 명사로만 지칭한다.
  → 우리는 자산(`asset://`)으로 인물을 고정해 두고도 얼굴·피부·의상을 매번 다시 썼다.
  https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/best-practice
- **[공식] Runway i2v는 "모션만" 쓴다.** 구조: `The camera [motion] as the subject [action].`
  https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide
- **[실무] 단일 샷 프롬프트는 ~20단어가 최적.** 길어지면 "faces drift toward a generic
  average, hands lose geometry" — 얼굴이 평균값으로 흐려진다. https://fal.ai/learn/tools/prompting-happy-horse

## 1. 문장 구조

- **[공식] Veo 3.1 5파트**: `[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]`
  https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
- **[공식] Kling 공식**: `Subject + Subject Movement + Scene (+ Camera Language + Lighting + Atmosphere)`
  앞 3개가 필수, 괄호 안은 선택. https://kling.ai/quickstart/text-to-video-prompt-guide
- **[공식] Runway**: 순서는 중요하지 않다. "Structure and order are far less important than
  clearly conveying an idea and reducing ambiguity."
- **[공식] JSON 프롬프트는 무의미**: "JSON formatting is ignored by generative models."

## 2. 카메라 — 공식 문서에 있는 용어만 쓴다

- 무빙 [공식 Veo]: static/fixed, pan(left/right), tilt(up/down), dolly(in/out),
  truck(left/right), pedestal(up/down), zoom(in/out), crane, aerial/drone, handheld,
  whip pan, arc
- 무빙 [공식 Runway]: + push in, pull back, tracking, orbit, crash zoom, steadicam, gimbal
- 샷 사이즈 [공식 Runway]: macro, extreme close up, close up, medium, full, wide,
  extreme wide, establishing
- 앵글 [공식 Veo]: eye-level, low-angle, high-angle, bird's-eye/top-down, worm's-eye,
  dutch/canted, over-the-shoulder, POV
- 포커스 [공식]: shallow/deep focus, soft focus, **rack focus**(무빙 아님·프레이밍 고정)
- **[공식] zoom ≠ dolly**: "This is different from a dolly, as the camera itself doesn't move."
- **[실무] 샷당 카메라 무브는 하나.** 두 개를 쌓으면 결과가 흐려진다.
- **[실무] 무브에는 속도와 종료 지점을 붙인다.** `slowly`, `rapid`, `then settles`.
  안 붙이면 실행마다 속도가 달라진다. https://higgsfield.ai/blog/ai-video-camera-control
- **[실무] 실패하는 표현**: `dynamic camera`, `cinematic`, `make it feel tense` —
  "Models treat camera instructions as spatial direction, not decoration."
  https://runway.com/resources/ai-camera-prompts

## 3. 렌즈·필름 용어

- [공식 Veo] 효과 있는 것: wide-angle/telephoto lens, shallow/deep depth of field,
  lens flare, rack focus, fisheye, vertigo(dolly zoom), "shot on 35mm film",
  "anamorphic widescreen", "film grain", sepia tone
- [공식] 셔터 스피드·셔터 앵글·f값·85mm 같은 구체 수치는 **권장 어휘 목록에 없다**
- [실무] `cinematic`, `4k`, `masterpiece`는 낭비. 형용사를 여러 개 쌓아도 강해지지 않는다

## 4. 속도 연출

- [공식 Veo] `slow-motion`, `fast-paced action`, `time-lapse`는 Temporal elements로 공식 지원
- [공식] **speed ramp와 time freeze는 어느 공식 문서에도 없다** → 후편집으로 처리
- [실무] `1000fps slow-motion` 같은 극단 지시는 안 먹힌다

## 5. 한 클립에 여러 샷

- **[공식 Google] 짧은 영상은 한 장면만**: "Trying to chain multiple distinct events
  (A then B then C) in one prompt for a short video often leads to muddled or incomplete videos."
- **[공식] 다만 타임코드 샷 리스트는 공식 예시로 존재**:
  `[00:00-00:02] Medium shot ... [00:02-00:04] Reverse shot ...`
- [공식 Runway] 의도치 않은 컷이 생기면 duration을 늘리고 `Continuous, seamless shot`을 추가
- [공식 Kling] Video 3.0은 한 번에 최대 6샷·15초, 샷별 duration/shot size/angle/movement 지정

## 6. 컷 간 연속성

- **[공식 Google] 캐릭터 설명을 매 컷에 그대로 복붙하고 액션·배경만 교체 + 같은 seed**
- **[실무] 무브·렌즈·조명 문구까지 글자 그대로 재사용**한다
- [실무] last-frame → 다음 컷 first-frame 체이닝. 단 "your reference frame is a hint,
  not a binding identity contract" — 다중 인물에선 깨진다
- [공식 Kling] 대안으로 element reference / multi-image reference

## 7. 네거티브

- **[공식 Veo] 별도 negativePrompt 필드에 명사만 나열**. "no", "don't" 쓰지 말 것.
  예: `wall, frame`
- **[공식 Runway] 부정 표현 자체가 미지원**: "Negative phrasing is not supported and may
  produce unpredictable or even opposite results." `No camera movement` 대신 `Locked camera.`
- [실무] 네거티브는 3~7개, 구체적 위험에만. 모호한 포지티브를 네거티브로 고칠 수 없다

## 8. 우리 프로젝트 적용 규칙

1. 인물 묘사는 **자산이 담당**한다. 프롬프트에서 얼굴·피부·수염·의상을 다시 쓰지 않는다.
   대신 **`Image 1`로 지칭**한다 (9번 참조 — `asset://`를 본문에 쓰면 연결이 안 된다)
2. 한 컷 = 한 문장 덩어리, **25단어 안쪽**
3. 카메라는 **하나**, 속도와 종료 지점을 붙인다
4. `cinematic`, `anamorphic`, `teal and orange` 같은 룩 형용사는 뺀다
5. 소리는 짧게 한 줄 (`Sound: wind.`)
6. 전투처럼 비트가 여럿이면 한 컷에 욱여넣지 말고 **컷을 나눈다**
7. 연속성은 같은 문구 재사용 + 좌우 위치 고정으로 잡는다

## 9. Seedance 공식 가이드 (우리가 실제로 쓰는 모델)

출처 [공식]: 1.0 pro https://docs.byteplus.com/en/docs/ModelArk/1631633 ·
2.0 https://docs.byteplus.com/en/docs/ModelArk/2222480 ·
2.5 https://docs.byteplus.com/en/docs/ModelArk/2607689

### 🔴 우리 버그: 프롬프트에서 인물을 `Image 1`로 불러야 한다

2.0 가이드 원문:
> "When using the asset library (Asset ID), you still need to use `<Image/Video_N>` to refer
> to the subject. Because the model cannot directly associate the Asset ID with the reference
> content, you must not directly use the Asset ID instead of `<Image/Video_N>`."

즉 `asset://` 는 API의 `reference_images` 필드에만 넣고, **프롬프트 본문에서는 업로드 순서대로
`Image 1`, `Image 2`로 지칭**해야 한다. 우리는 "the reference asset"이라고만 써서 모델이
누구를 가리키는지 연결하지 못했다.

### 공식 프롬프트 공식

- 2.0: `subject + action details + scene/environment + lighting & color tone + camera movement
  + visual style + image quality + constraints`
- 샷 내부 순서: ① 카메라 무빙/전환 ② 동작·표정 ③ 위치 변화 ④ 오디오
- 2.5: `[Asset Bindings] → [One-Sentence Summary] → [Shot 1..N] → [Overall / Strictly exclude]`

### 카메라

- 무빙 [공식 2.5]: push in / pull out / pan / track / follow / orbit / dive / pull back /
  tilt up / handheld shake
- 기법 [공식 2.5]: one-shot(long take), Hitchcock zoom(dolly zoom), aerial, FPV,
  **bullet time, speed ramp** ← Seedance는 공식 지원 (Veo·Runway와 다름)
- 샷 사이즈 [공식 2.5]: extreme wide / wide / medium / medium close-up / close-up
- 앵글 [공식 2.5]: low angle / overhead / first-person
- **[공식] 한 샷에 카메라 무빙은 1종만**: "Try to specify only 1 type of camera movement in a
  single shot. Do not require push, pull, pan, and move at the same time, as this will
  increase image instability."
- 희귀 용어는 설명을 붙인다: "rack focus: the focus shifts smoothly; the trees in the
  foreground become blurred while the character behind gradually becomes clear"

### 화질 어휘는 Seedance에서 공식 요소다

2.0은 "Image quality"를 정식 프롬프트 요소로 규정하고 예시로 `HD, rich details,
cinematic texture, natural colors, soft lighting`을 든다. 2.5 공식 예시에도
`shot on Arri Alexa Mini LF, 35 mm cinema lens`, `film grain`, `shallow depth of field`,
`no excessive beautification or skin smoothing`이 그대로 쓰인다.
→ 다른 모델 가이드에서 "cinematic은 낭비"라고 한 것과 다르다. **Seedance에서는 유효**.

### 타임스탬프

- **2.0은 타임스탬프를 인식하지 못한다.** Shot 1/Shot 2 번호만 쓴다
- 2.5는 정수 초 단위 타임스탬프를 지원. 단 1초 미만 고빈도 동작 지정은 권장하지 않음

### 액션 씬은 나눠 찍고 편집하라 (공식)

> "Scene / action turning points (segmented stitching): suitable for plot turns or complex,
> fast-paced 'action scenes,' such as chases, fights, montages, etc. Independent clips can be
> generated and then edited together to ensure rhythm and visual impact."

→ 우리가 4초 컷을 따로 뽑아 붙이는 방식이 공식 권장안과 같다.

### ⚠️ 격한 동작 경고

> "Prioritize slow, gentle, coherent subtle movements, and try to avoid high-burst,
> large-dynamic actions such as sprinting, big jumps, and violent rolls."

무협 전투와 정면으로 부딪힌다. 결정적 일격 하나만 신체 부위·속도·힘으로 자세히 쓰고,
나머지는 총괄 서술로 두는 편이 실패율이 낮다.

### 참조 이미지

- **참조 이미지가 프롬프트보다 우세**하다. 스타일이 어긋나면 프롬프트가 아니라
  **참조 이미지를 먼저 고쳐야** 한다
- 인물은 **얼굴 클로즈업 1 + 전신 1**이면 충분. 에셋을 상한까지 채우지 말 것
  (권장: 얼굴 1 + 전신 1 + 씬 1 + 카메라무빙 영상 1)
- 중요한 에셋일수록 프롬프트 앞쪽에 배치
- "When the reference asset itself is sufficiently accurate, simply state that it should be
  referenced and **avoid repeatedly describing the scene in detail**"

### 자막·워터마크

- **9:16은 자막이 잘못 생성될 확률이 가로보다 높다** (공식 명시). 100% 차단은 불가
- 제약문을 고정으로 붙인다: `no subtitles`, `do not generate a logo`, `do not generate a watermark`
- 부정문은 **자막·오디오·스타일 배제에만** 공식 지원. 동작·구도는 긍정문으로 쓴다

### 연속성

- `return_last_frame`으로 받은 마지막 프레임을 다음 컷의 first_frame으로 넣는다
- 이어붙일 때 앞 클립 끝 **6프레임**, 뒤 클립 앞 **1프레임**을 트림하면 점프컷이 줄어든다
