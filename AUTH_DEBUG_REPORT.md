# Authentication investigation — 2026-11-26

## Outcome

The reported repeated post-login 401 has **not been reproduced or fixed**. The current application code passes the login/retention tests below. This tool environment cannot connect to the user's running localhost servers: both ports 3000 and 8000 return PermissionError/EPERM. The report does not substitute in-process tests for browser evidence.

No authentication bypass, domain rewrite, SameSite relaxation, token-storage workaround, or production Secure-cookie change was made. The actual failing request's login status, error code and browser origin are still needed to identify the root cause.

## Inspected flow

1. Browser `api.login` posts to the relative `/api/v1/session` endpoint with `credentials: same-origin` and the custom CSRF header. Browser Origin must equal frontend/backend APP_ORIGIN.
2. Next.js forwards Origin, cookies and CSRF headers to FastAPI and forwards Set-Cookie back. FastAPI compares the code using constant-time comparison. It commits a session containing an HMAC hash of a random token with a seven-day UTC expiry before issuing the cookie.
3. Cookie defaults are Path=/, no Domain (host-only), HttpOnly, SameSite=Strict, Max-Age=604800. COOKIE_SECURE is false in the inspected local settings and defaults to true otherwise. HTTPS production behavior is covered separately by a regression test. No secret values were printed.
4. Subsequent requests include the cookie through the same-origin proxy. Validation hashes the token and requires a matching unexpired persisted session.
5. Inspected configuration: backend/frontend APP_ORIGIN=http://localhost:3000, backend target=http://127.0.0.1:8000, local COOKIE_SECURE=false. These are current file/process settings in this tool; an already-running server can retain earlier cached settings until restarted.

The initial GET /api/v1/runs?limit=1 **before login** correctly returns 401. After a 200 login, `session_required` means no cookie reached FastAPI; `session_expired` means the cookie arrived but its hash has no unexpired matching row. `invalid_access_code` is returned by a failed login itself. Origin rejection is 403, not a session 401.

Use the exact same browser hostname throughout. localhost and 127.0.0.1 are different cookie hosts. The API's internal target does not require a cookie Domain attribute or cross-origin browser requests.

## Added and executed tests

- Four backend authentication cases: successful login and cookie attributes, retained access on later requests/new clients, invalid code with no session/cookie, expired/tampered tokens, and production HTTPS Secure cookies.
- Extended Next proxy ↔ real FastAPI integration with invalid-code handling and a cookie jar enforcing host/path retention. Confirms localhost cookie is not sent to 127.0.0.1 and authenticated history succeeds when using the correct host.
- Added frontend request test for explicit same-origin credentials and preservation of invalid-access-code errors.
- Added native Playwright case for invalid code, valid login, cookie attributes, authenticated history, reload and navigation. It disables tracing before login to avoid recording credentials. It was not executable because Playwright is not installed in this environment.

Executed results: **43 backend passed, 1 PostgreSQL skipped; 6 frontend unit passed; 3 API integration passed; 1 DOM integration passed; TypeScript passed.** Logs: audit/auth/. Playwright invocation fails with missing runner; no native-browser success is claimed.

## Safe diagnosis against the running app

With both services running, use your ordinary terminal:

```sh
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run python -m app.check_auth
```

This new helper reads the configured demo code privately and makes one real login through the frontend proxy. It prints only statuses and cookie attributes, never code/token/header values. It verifies history and retained authentication in a second HTTP client. It creates one session, no research. HTTP clients do not enforce every browser SameSite policy, so a passing helper with failing browser still needs DevTools evidence.

Share its JSON and the exact frontend browser URL, omitting all credential/cookie values. If the helper passes, inspect browser DevTools → Network: the login's status/Set-Cookie attributes and any blocked-cookie reason, then the subsequent history response's error.code. Do not share the cookie value or access code.

## Restart commands

Stop existing API/frontend processes with Ctrl-C in their terminals, then:

```sh
# Terminal 1
cd /Users/ridhhingrover/Desktop/signalflow/backend
uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

```sh
# Terminal 2
cd /Users/ridhhingrover/Desktop/signalflow/frontend
npm run dev
```

Open http://localhost:3000. Authentication does not require restarting the background worker. There is no need to delete historical data, weaken cookies or change session secrets. Changing the session secret invalidates existing sessions.
