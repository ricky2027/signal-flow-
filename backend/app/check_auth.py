"""Inspect the running same-origin login flow without logging credentials.

Run from backend/: uv run python -m app.check_auth
Uses APP_ORIGIN and DEMO_ACCESS_CODE from backend settings. Creates one real
login session, performs no research, and never prints tokens or response bodies.
"""

import json

import httpx

from app.config import settings


def main():
    cfg = settings()
    results = {"configured_secure_cookie": cfg.cookie_secure}
    headers = {"Origin": cfg.app_origin, "X-Signalflow-Client": "web"}
    try:
        with httpx.Client(base_url=cfg.app_origin, headers=headers, timeout=15) as client:
            initial = client.get("/api/v1/runs?limit=1")
            results["before_login_status"] = initial.status_code
            login = client.post("/api/v1/session", json={"access_code": cfg.demo_access_code.get_secret_value()})
            results["login_status"] = login.status_code
            results["set_cookie_present"] = "set-cookie" in login.headers
            cookie = next((c for c in client.cookies.jar if c.name == "signalflow_session"), None)
            results["cookie_retained"] = cookie is not None
            if cookie is not None:
                results["cookie_attributes"] = {
                    "secure": cookie.secure,
                    "path": cookie.path,
                    "host_only": not cookie.domain_specified,
                    "httponly": cookie.has_nonstandard_attr("HttpOnly"),
                    "samesite": cookie.get_nonstandard_attr("SameSite"),
                    "expired": cookie.is_expired(),
                }
            response = client.get("/api/v1/runs?limit=1")
            results["authenticated_history_status"] = response.status_code
            if response.status_code == 401:
                code = response.json().get("error", {}).get("code")
                results["history_error_code"] = code if code in ("session_required", "session_expired") else "unexpected_error_code"
            # A new HTTP client verifies retention independently of the login request.
            with httpx.Client(base_url=cfg.app_origin, cookies=client.cookies, timeout=15) as reopened:
                results["reopened_client_status"] = reopened.get("/api/v1/runs?limit=1").status_code
    except Exception as exc:
        results["connection_error"] = type(exc).__name__
    print(json.dumps(results, indent=2))
    return 0 if results.get("login_status") == 200 and results.get("authenticated_history_status") == 200 and results.get("reopened_client_status") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
