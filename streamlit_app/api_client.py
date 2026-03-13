import json
import os
from urllib import error, request


API_BASE_URL = os.getenv("STREAMLIT_API_BASE_URL", "http://localhost:8000").rstrip("/")
PUBLIC_BASE_URL = os.getenv("STREAMLIT_PUBLIC_BASE_URL", API_BASE_URL).rstrip("/")


def build_public_short_link(short_code: str) -> str:
    return f"{PUBLIC_BASE_URL}/links/{short_code}"


def api_request(
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    token: str | None = None,
    accept_redirects: bool = True,
) -> tuple[int, dict | list | str | None, dict[str, str]]:
    request_url = f"{API_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    class NoRedirectHandler(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    handlers = []
    if not accept_redirects:
        handlers.append(NoRedirectHandler())

    opener = request.build_opener(*handlers)
    api_request_obj = request.Request(
        request_url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with opener.open(api_request_obj, timeout=10) as response:
            response_body = response.read().decode("utf-8")
            return response.status, _parse_body(response_body), dict(response.headers)
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        return exc.code, _parse_body(response_body), dict(exc.headers)
    except error.URLError as exc:
        return 0, {"detail": f"Could not reach API: {exc.reason}"}, {}


def _parse_body(raw_body: str) -> dict | list | str | None:
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body
