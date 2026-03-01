# K-Content YouTube Shorts — 프로젝트 규칙

## 1. 언어 & 인코딩
- 코드 내 주석, docstring은 **한국어** 작성 (영어 OK)
- 모든 파일 인코딩은 `utf-8`
- Python 버전: **3.10+** 필수 (match/case, type hints 사용 가능)

## 2. 코드 스타일
- 스타일 가이드: **PEP 8** 준수
- 함수/변수: `snake_case`
- 상수: `UPPER_CASE` (config.py에만 선언)
- 최대 줄 길이: **100자**
- 타입 힌트: 모든 public 함수 파라미터 및 반환값에 필수

## 3. 파일 구조 규칙
- 새 기능은 무조건 `src/` 하위 모듈로 분리
- 각 모듈은 `run(output_dir: Path, ...) -> Path` 또는 tuple 형태의 진입점 통일
- 모듈 최상단에 역할 설명 docstring 필수
- 설정값은 `config.py`에서만 관리, 하드코딩 금지

## 4. 에러 핸들링
- 치명적 오류: `raise` (파이프라인 중단)
- 비치명적 오류 (에셋 부족 등): 경고 출력 후 다음 단계 진행
- 모든 외부 API 호출은 `try/except`로 감싸기
- 에러 로그는 반드시 `console.print(f"[red]...")`로 출력 (스킵 금지)

## 5. API 호출 규칙
- OpenAI 클라이언트는 **함수 내부에서** 초기화 (`OpenAI(api_key=config.OPENAI_API_KEY)`)
- 재시도 로직: 외부 API는 최대 3회 재시도, `try/except` 내에서 처리
- API 응답 JSON 파싱은 항상 `try/except json.JSONDecodeError` 처리

## 6. 의존성 관리
- `requirements.txt`는 **major.minor 버전 고정** (`package>=X.Y,<X.Z` 형태)
- 주요 패키지 버전:
  - `moviepy<2.0` (2.x API 호환 불가)
  - `openai>=1.0,<2.0`
  - `google-generativeai>=0.8,<1.0`
- 신규 패키지 추가 시 `requirements.txt`에 버전 범위 명시 필수

## 7. .env & 시크릿 관리
- API 키는 반드시 `.env`에서 로드 (`config.py` 경유)
- `.env`, `credentials/` 디렉토리는 절대 git 커밋 금지
- 새 환경변수 추가 시 `.env.example`에도 동시 업데이트

## 8. 테스트 & 검증
- 새 기능은 `python src/<모듈>.py` 단독 실행으로 검증 가능하도록 `if __name__ == "__main__":` 블록 포함
- 전체 파이프라인 테스트는 `python main.py --dry-run` 사용
- 업로드 테스트 시 `UPLOAD_PRIVACY=private` 유지

## 9. 로깅 규칙
- 터미널 출력은 `rich.console.Console` 사용
  - 성공: `[green]✓ ...[/green]`
  - 경고: `[yellow]⚠ ...[/yellow]`
  - 오류: `[red]✗ ...[/red]`
  - 진행: `[dim]... [/dim]`
- 단계 시작 시: `[bold blue]━━ [N/6] 단계명 시작 ━━[/bold blue]`

## 10. Gemini 모델 사용 규칙
- 모델명은 `config.py`에 상수로 선언 후 사용
- 이미지 생성: `gemini-2.0-flash-exp-image-generation`
- 텍스트: 별도 지정 없으면 OpenAI GPT-4o 우선 사용
