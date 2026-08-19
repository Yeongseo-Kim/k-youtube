"""
[프로바이더] BytePlus ModelArk — Dreamina Seedance 영상 생성 래퍼

캐릭터 일관성이 필요한 컷은 omni reference-to-video(레퍼런스 이미지 최대 9장,
Seedance 2.5는 30장)로 생성한다. 얼굴이 없는 B-roll 컷은 first_frame 방식을 쓴다.

API 문서: https://docs.byteplus.com/en/docs/ModelArk/1520757
"""

import base64
import mimetypes
import time
from pathlib import Path
from typing import Literal

import requests
from rich.console import Console

import config

console = Console()

# 이미지 역할 — omni reference와 first/last frame 방식은 서로 배타적이다
ImageRole = Literal["reference_image", "first_frame", "last_frame"]
TaskType = Literal["reference", "edit", "extend"]

# 모델별 레퍼런스 이미지 허용 개수 (API 문서 기준)
MAX_REFERENCE_IMAGES = {
    "dreamina-seedance-2-5": 30,
    "dreamina-seedance-2-0": 9,
    "dreamina-seedance-2-0-fast": 9,
    "dreamina-seedance-2-0-mini": 9,
}

# 단일 이미지 업로드 제한
MAX_IMAGE_BYTES = 30 * 1024 * 1024
ALLOWED_IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp", ".bmp", ".tiff", ".gif"}


class ModelArkError(RuntimeError):
    """ModelArk API 호출 실패."""


def _headers() -> dict:
    if not config.MODELARK_API_KEY:
        raise ModelArkError("MODELARK_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")
    return {
        "Authorization": f"Bearer {config.MODELARK_API_KEY}",
        "Content-Type": "application/json",
    }


def encode_image(source: str | Path) -> str:
    """로컬 파일이면 base64 data URI로, URL이면 그대로 반환한다."""
    if isinstance(source, str) and source.startswith(("http://", "https://", "asset://", "data:")):
        return source

    path = Path(source)
    if not path.exists():
        raise ModelArkError(f"이미지 파일을 찾을 수 없습니다: {path}")
    if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        raise ModelArkError(f"지원하지 않는 이미지 형식입니다: {path.suffix}")

    raw = path.read_bytes()
    if len(raw) > MAX_IMAGE_BYTES:
        raise ModelArkError(f"이미지가 30MB를 초과합니다: {path.name} ({len(raw) / 1e6:.1f}MB)")

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def _build_content(prompt: str, images: list[str | Path], role: ImageRole) -> list[dict]:
    """텍스트 프롬프트 + 이미지 목록을 API content 배열로 변환."""
    content: list[dict] = []
    if prompt:
        content.append({"type": "text", "text": prompt})

    for image in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": encode_image(image)},
            "role": role,
        })
    return content


def create_task(
    prompt: str,
    reference_images: list[str | Path] | None = None,
    first_frame: str | Path | None = None,
    last_frame: str | Path | None = None,
    model: str | None = None,
    resolution: str = "720p",
    ratio: str = "9:16",
    duration: int = 5,
    generate_audio: bool = False,
    camera_fixed: bool = False,
    watermark: bool = False,
    seed: int | None = None,
    task_type: TaskType = "reference",
) -> str:
    """영상 생성 태스크를 만들고 task_id를 반환한다 (비동기 API).

    reference_images와 first_frame/last_frame은 함께 쓸 수 없다 (API 제약).
    """
    model = model or config.MODELARK_VIDEO_MODEL
    reference_images = reference_images or []

    if reference_images and (first_frame or last_frame):
        raise ModelArkError(
            "reference_images와 first_frame/last_frame은 함께 쓸 수 없습니다 (API 배타 조건)."
        )

    if reference_images:
        # 접두사가 겹치므로(2-0 vs 2-0-mini) 가장 긴 매칭을 택한다
        matches = [v for k, v in MAX_REFERENCE_IMAGES.items() if model.startswith(k)]
        limit = MAX_REFERENCE_IMAGES[
            max((k for k in MAX_REFERENCE_IMAGES if model.startswith(k)), key=len)
        ] if matches else 9
        if len(reference_images) > limit:
            raise ModelArkError(
                f"{model}의 레퍼런스 이미지 한도는 {limit}장인데 {len(reference_images)}장이 들어왔습니다."
            )
        content = _build_content(prompt, reference_images, "reference_image")
    else:
        content = _build_content(prompt, [first_frame] if first_frame else [], "first_frame")
        if last_frame:
            content += _build_content("", [last_frame], "last_frame")

    payload = {
        "model": model,
        "content": content,
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "camera_fixed": camera_fixed,
        "watermark": watermark,
        "generate_audio": generate_audio,
    }
    if seed is not None:
        payload["seed"] = seed
    if reference_images:
        payload["task_type"] = task_type

    url = f"{config.MODELARK_BASE_URL}/contents/generations/tasks"
    console.print(f"  [dim]🎬 생성 요청: {model} / {resolution} {ratio} {duration}초[/dim]")

    last_error = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(url, headers=_headers(), json=payload, timeout=60)
            if response.status_code == 200:
                task_id = response.json().get("id", "")
                if not task_id:
                    raise ModelArkError(f"task id가 응답에 없습니다: {response.text[:300]}")
                console.print(f"  [green]✓ 태스크 생성됨: {task_id}[/green]")
                return task_id

            last_error = f"HTTP {response.status_code}: {response.text[:400]}"
            # 4xx는 재시도해도 동일하므로 즉시 중단
            if 400 <= response.status_code < 500:
                break
            console.print(f"  [yellow]⚠ {attempt}회차 실패, 재시도: {last_error}[/yellow]")
        except requests.RequestException as exc:
            last_error = str(exc)
            console.print(f"  [yellow]⚠ {attempt}회차 네트워크 오류, 재시도: {exc}[/yellow]")
        time.sleep(2 ** attempt)

    raise ModelArkError(f"태스크 생성 실패 — {last_error}")


def get_task(task_id: str) -> dict:
    """태스크 상태를 조회한다."""
    url = f"{config.MODELARK_BASE_URL}/contents/generations/tasks/{task_id}"
    try:
        response = requests.get(url, headers=_headers(), timeout=30)
    except requests.RequestException as exc:
        raise ModelArkError(f"태스크 조회 실패: {exc}") from exc

    if response.status_code != 200:
        raise ModelArkError(f"태스크 조회 실패 — HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


def wait_for_task(task_id: str, timeout: int = 600, interval: int = 5) -> str:
    """태스크가 끝날 때까지 폴링하고 완성된 영상 URL을 반환한다."""
    deadline = time.time() + timeout
    last_status = ""

    while time.time() < deadline:
        result = get_task(task_id)
        status = result.get("status", "")

        if status != last_status:
            console.print(f"  [dim]… 상태: {status}[/dim]")
            last_status = status

        if status == "succeeded":
            video_url = (result.get("content") or {}).get("video_url", "")
            if not video_url:
                raise ModelArkError(f"완료됐으나 video_url이 없습니다: {result}")
            usage = result.get("usage") or {}
            console.print(
                f"  [green]✓ 생성 완료 (토큰: {usage.get('total_tokens', '?')})[/green]"
            )
            return video_url

        if status in ("failed", "cancelled"):
            error = result.get("error") or result
            raise ModelArkError(f"생성 실패 ({status}): {error}")

        time.sleep(interval)

    raise ModelArkError(f"타임아웃 {timeout}초 초과 — task_id={task_id}")


def download_video(video_url: str, output_path: Path) -> Path:
    """생성된 영상을 로컬에 저장한다. video_url은 24시간 후 만료된다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(video_url, stream=True, timeout=180) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except requests.RequestException as exc:
        raise ModelArkError(f"영상 다운로드 실패: {exc}") from exc

    size_mb = output_path.stat().st_size / 1e6
    console.print(f"  [green]✓ 저장 완료: {output_path} ({size_mb:.1f}MB)[/green]")
    return output_path


def generate(
    prompt: str,
    output_path: Path,
    reference_images: list[str | Path] | None = None,
    first_frame: str | Path | None = None,
    **kwargs,
) -> Path:
    """생성 → 대기 → 다운로드를 한 번에 수행하는 편의 함수."""
    task_id = create_task(
        prompt,
        reference_images=reference_images,
        first_frame=first_frame,
        **kwargs,
    )
    video_url = wait_for_task(task_id)
    return download_video(video_url, output_path)


if __name__ == "__main__":
    # 단독 실행: API 키와 모델 활성화 상태를 점검한다 (실제 생성은 하지 않음)
    console.print("\n[bold]ModelArk 연결 점검[/bold]\n")
    console.print(f"  Base URL: {config.MODELARK_BASE_URL}")
    console.print(f"  Model:    {config.MODELARK_VIDEO_MODEL}")
    console.print(f"  API Key:  {'✓ 설정됨' if config.MODELARK_API_KEY else '✗ 미설정'}")

    if not config.MODELARK_API_KEY:
        console.print("\n[red]✗ MODELARK_API_KEY를 .env에 설정하세요.[/red]")
        raise SystemExit(1)

    # 존재하지 않는 태스크를 조회해 인증/권한 상태만 확인한다
    try:
        get_task("probe-nonexistent-task")
        console.print("\n[green]✓ 인증 통과[/green]")
    except ModelArkError as exc:
        message = str(exc)
        if "404" in message or "NotFound" in message:
            console.print("\n[green]✓ 인증 통과 (태스크 없음은 정상)[/green]")
        else:
            console.print(f"\n[red]✗ {message}[/red]")
