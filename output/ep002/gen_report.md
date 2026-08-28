# episode-002 컷 생성 보고

- 일시: 2026-08-28
- 모델: `dreamina-seedance-2-0-mini-260615` (720p · 9:16)
- 브랜치: `claude/c-dance-video-production-d2huo8`
- 실행 환경: Claude Code 원격 컨테이너

## 결과 — 8/8 성공

| 컷 | 결과 | 크기 | 스펙 | 토큰 |
|---|---|---|---|---|
| cut1 | ✓ | 2.8MB | 720x1280 · 4.0초 | 87,300 |
| cut2 | ✓ | 2.6MB | 720x1280 · 4.0초 | 87,300 |
| cut3 | ✓ | 2.6MB | 720x1280 · 4.0초 | 87,300 |
| cut5 | ✓ | 2.9MB | 720x1280 · 4.0초 | 87,300 |
| cut6 | ✓ | 3.1MB | 720x1280 · 4.0초 | 87,300 |
| cut7 | ✓ | 2.8MB | 720x1280 · 5.0초 | 108,900 |
| cut8a | ✓ | 2.6MB | 720x1280 · 4.0초 | 87,300 |
| cut8b | ✓ | 2.7MB | 720x1280 · 4.0초 | 87,300 |
| **합계** | **8/8** | **22.2MB** | **33초** | **720,000** |

CUT 4(택배 스틸)는 계획대로 생성하지 않았습니다 — 조립에서 켄번즈 처리.

## 재시도 내역 — 컷 실패 0회, 사전 오류 3종

생성 자체는 한 번도 실패하지 않았습니다. 대신 제출 단계에서 세 가지 제약에
연달아 걸렸고, 각각 고친 뒤 통과했습니다. **실패한 제출은 과금되지 않습니다.**

### 1. 모델 미활성화 → 2.0 mini로 교체

```
ModelNotOpen: account 3004081739 has not activated dreamina-seedance-2-5-260628
```

계정에 Seedance 2.5가 열려 있지 않습니다. 2.5를 쓰려면 Ark Console에서
활성화해야 합니다(2.x 계열은 잔액 USD 30 이상 조건).

### 2. 레퍼런스 이미지가 최소 크기 미달

```
expected the width to be at least 300px, but received a 97x107px image
```

`character_sheet.png`가 713x1063이라 거기서 뜬 크롭이 80~130px밖에 안 됐습니다.
원본에서 다시 잘라도 300px이 안 나오므로 **LANCZOS로 확대 후 약한 언샵**을
적용했습니다(가장 짧은 변 320px 기준, 배율 2.5~4.0x).

| 파일 | 이전 | 이후 |
|---|---|---|
| exp_excited | 107x107 | 320x320 |
| exp_happy | 97x107 | 320x353 |
| exp_hmm | 107x117 | 320x350 |
| exp_surprised | 112x105 | 341x320 |
| exp_thinking | 102x105 | 320x329 |
| exp_yummy | 112x107 | 335x320 |
| pose_glass | 130x145 | 320x357 |
| ref_front | 80x283 | 320x1132 → 472x1132 |

> ⚠️ 확대는 없는 정보를 만들어내지 못합니다. 캐릭터 일관성이 아쉬우면
> 시트를 더 큰 해상도로 다시 뽑아 크롭하는 편이 근본적입니다.

### 3. 레퍼런스 종횡비 초과

```
expected the aspect ratio to be between 0.40 and 2.50, but received 3.54
```

확대된 `ref_front.png`가 1:3.54가 됐습니다. 가장자리에서 뽑은 배경색
`RGB(253,244,235)`으로 좌우에 여백을 덧대 1:2.40으로 맞췄습니다.

### 4. camera_fixed 미지원 (cut7)

```
camera_fixed is not supported for model dreamina-seedance-2-0-mini in r2v
```

2.0 mini의 reference-to-video는 이 파라미터를 받지 않습니다.
`scripts/gen_ep002.py`에 `SUPPORTS_CAMERA_FIXED` 가드를 넣어 2.5일 때만
보내도록 했습니다. cut7 프롬프트에 "Camera does not move"가 이미 있어
의도는 유지됩니다.

## 다음 단계

`output/ep002/cuts/`의 8개 클립으로 조립을 이어가면 됩니다.
