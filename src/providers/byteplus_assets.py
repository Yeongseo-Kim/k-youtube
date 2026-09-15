"""BytePlus ModelArk 자산 라이브러리(Assets API) 클라이언트.

Seedance 2.x는 실사 얼굴 이미지를 직접 넣으면 거부한다
(`InputImageSensitiveContentDetected.PrivacyInformation`).
공식 우회로는 **private virtual portrait library**에 AI 생성 인물을 등록하고
`asset://` URI로 참조하는 것. 이 모듈이 그 등록·조회를 담당한다.

문서
- Private virtual portrait library: docs.byteplus.com/en/docs/ModelArk/2333565
- Advanced Creation Rights(Entry는 무료): docs.byteplus.com/en/docs/modelark/2377608

주의
- Assets API는 Bearer API Key가 아니라 **AK/SK 서명**을 쓴다 (SigV4 계열).
  `.env`에 BYTEPLUS_ACCESS_KEY / BYTEPLUS_SECRET_KEY 필요 (기업 계정에서 발급).
- CreateAsset은 로컬 파일이 아니라 **공개 URL**을 받는다.
- 비동기라서 GetAsset의 Status가 Active가 될 때까지 폴링해야 쓸 수 있다.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
from typing import Any

import requests

import config  # .env 로드 + 키 일원화

HOST = os.getenv("BYTEPLUS_OPEN_HOST", "open.byteplusapi.com")
REGION = os.getenv("BYTEPLUS_REGION", "ap-southeast-1")
SERVICE = "ark"
VERSION = "2024-01-01"


def _keys() -> tuple[str, str]:
    ak = config.BYTEPLUS_ACCESS_KEY
    sk = config.BYTEPLUS_SECRET_KEY
    if not ak or not sk:
        raise RuntimeError(
            "BYTEPLUS_ACCESS_KEY / BYTEPLUS_SECRET_KEY가 없습니다. "
            "ModelArk 콘솔에서 AK/SK를 발급해 .env에 넣어 주세요."
        )
    return ak, sk


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def call(action: str, body: dict[str, Any]) -> dict[str, Any]:
    """Assets API 한 번 호출. action 예: CreateAssetGroup / CreateAsset / GetAsset."""
    ak, sk = _keys()
    payload = json.dumps(body, separators=(",", ":"))
    now = _dt.datetime.now(_dt.timezone.utc)
    xdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = xdate[:8]
    body_hash = hashlib.sha256(payload.encode()).hexdigest()

    query = f"Action={action}&Version={VERSION}"
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical = "\n".join([
        "POST", "/", query,
        f"content-type:application/json\nhost:{HOST}\n"
        f"x-content-sha256:{body_hash}\nx-date:{xdate}\n",
        signed_headers, body_hash,
    ])
    scope = f"{datestamp}/{REGION}/{SERVICE}/request"
    to_sign = "\n".join([
        "HMAC-SHA256", xdate, scope,
        hashlib.sha256(canonical.encode()).hexdigest(),
    ])
    k = _sign(sk.encode(), datestamp)
    k = _sign(k, REGION)
    k = _sign(k, SERVICE)
    k = _sign(k, "request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Host": HOST,
        "X-Date": xdate,
        "X-Content-Sha256": body_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={ak}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }
    r = requests.post(
        f"https://{HOST}/?{query}", headers=headers, data=payload, timeout=120
    )
    data = r.json() if r.content else {}
    if r.status_code != 200 or "Error" in data.get("ResponseMetadata", {}):
        raise RuntimeError(f"{action} 실패 — HTTP {r.status_code}: {r.text[:400]}")
    return data.get("Result", data)


def create_group(name: str, description: str = "") -> str:
    """가상 인물 자산 그룹 생성 → 그룹 ID. GroupType 기본값이 AIGC(가상 인물)."""
    return create_group_raw(name, description)["Id"]


def create_group_raw(name: str, description: str = "") -> dict[str, Any]:
    return call("CreateAssetGroup", {
        "Name": name, "Description": description, "ProjectName": "default",
    })


def create_asset(group_id: str, url: str, name: str = "",
                 asset_type: str = "Image") -> str:
    """공개 URL의 자산을 등록 → 자산 ID (아직 Active 아님).

    asset_type은 Image / Video / Audio. Seedance 2.5는 카메라 무빙 참고용으로
    Video 자산을 받는다 (권장 구성: 얼굴 1 + 전신 1 + 씬 1 + 무빙영상 1).
    """
    body = {
        "GroupId": group_id, "URL": url,
        "AssetType": asset_type, "ProjectName": "default",
    }
    if name:
        body["Name"] = name
    return call("CreateAsset", body)["Id"]


def get_asset(asset_id: str) -> dict[str, Any]:
    return call("GetAsset", {"Id": asset_id})


def list_groups(group_type: str = "AIGC") -> dict[str, Any]:
    """자산 그룹 목록. Filter.GroupType은 필수 (실측 2026-09-14)."""
    return call("ListAssetGroups", {"Filter": {"GroupType": group_type}})


def list_assets(group_id: str) -> dict[str, Any]:
    return call("ListAssets", {"Filter": {"GroupId": group_id}})


def wait_active(asset_id: str, timeout: int = 900, interval: int = 10) -> dict[str, Any]:
    """전처리가 끝나 Status가 Active가 될 때까지 폴링."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        info = get_asset(asset_id)
        status = info.get("Status", "")
        if status == "Active":
            return info
        if status == "Failed":
            raise RuntimeError(f"자산 전처리 실패: {asset_id} — {info}")
        time.sleep(interval)
    raise TimeoutError(f"자산이 {timeout}초 안에 Active가 되지 않음: {asset_id}")
