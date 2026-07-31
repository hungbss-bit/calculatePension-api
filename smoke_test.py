from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(url: str, path: str, payload: dict, api_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(
        url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def main() -> int:
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("API_KEY")
    payload = json.loads(
        Path("examples/request_normal.json").read_text(encoding="utf-8")
    )

    validation = call(
        base_url,
        "/v1/validateContributionHistory",
        payload,
        api_key,
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if not validation.get("validation"):
        print("Validation failed; calculatePension was not called.", file=sys.stderr)
        return 1

    calculation = call(
        base_url,
        "/v1/calculatePension",
        payload,
        api_key,
    )
    print(json.dumps(calculation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
