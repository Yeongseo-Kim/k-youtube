# episode-002 컷 생성 보고

- 일시: 2026-08-28
- 실행 환경: Claude Code 원격 컨테이너 (`/home/user/k-youtube`)
- 브랜치: `claude/c-dance-video-production-d2huo8` @ `f607178`

## 결과 — 생성 0/8, 전량 실패

**원인: 모델 미활성화.** 계정 `3004081739`이 `dreamina-seedance-2-5-260628`을
활성화하지 않아 태스크 제출 단계(HTTP 404)에서 전부 거부됐습니다.

```
{"error":{"code":"ModelNotOpen","message":"Your account 3004081739 has not
activated the model dreamina-seedance-2-5-260628. Please activate the model
service in the Ark Console.","type":"Not Found"}}
```

| 컷 | 결과 | 파일 크기 | 비고 |
|---|---|---|---|
| cut1 | ✗ 제출 실패 | — | ModelNotOpen |
| cut2 | ✗ 제출 실패 | — | ModelNotOpen |
| cut3 | ✗ 제출 실패 | — | ModelNotOpen |
| cut5 | 미시도 | — | 웨이브 1에서 중단 |
| cut6 | 미시도 | — | 〃 |
| cut7 | 미시도 | — | 〃 |
| cut8a | 미시도 | — | 〃 |
| cut8b | 미시도 | — | 〃 |

**토큰·사용량: 0.** 생성이 시작되지 않아 과금이 없습니다.
**재시도: 하지 않음.** 재시도해도 같은 결과이므로 웨이브 1에서 멈췄습니다.

## 사전 점검 (전부 통과)

- `MODELARK_API_KEY` 존재 확인 (`python3 config.py`, 값 미출력)
- `assets/yuna/` 레퍼런스 12개 전부 존재
- `pip install -r requirements.txt` 정상

즉 막힌 건 코드·자산·키가 아니라 **콘솔의 모델 활성화 하나**입니다.

## 필요한 조치

1. Ark Console에서 `dreamina-seedance-2-5-260628` 활성화
   (Seedance 2.x 계열은 계정 잔액 USD 30 이상 또는 그에 준하는 리소스팩이 조건.
   ep001에 쓴 `dreamina-seedance-2-0-mini-260615`는 이미 활성화돼 있음)
2. 활성화 후 `python3 -m scripts.gen_ep002` 재실행

## 대안 — 2.0 mini로 내리기

`scripts/gen_ep002.py`의 `MODEL`만 `dreamina-seedance-2-0-mini-260615`로 바꾸면
활성화된 모델로 돌아갑니다. 이 스크립트는 컷당 레퍼런스를 최대 3장만 쓰므로
2.0의 9장 한도에 걸리지 않습니다. 다만 화질·캐릭터 일관성이 2.5보다 떨어지고,
ep002를 2.5로 잡은 건 의도적인 선택으로 보여 임의로 바꾸지 않았습니다.
