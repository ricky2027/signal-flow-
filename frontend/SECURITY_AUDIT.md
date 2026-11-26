# Frontend dependency security audit — 2026-11-26

Historical milestone. See [the current readiness report](../ENGINEERING_REPORT.md) for the installed Next.js 16.4.6 / React 19.3.1 checkpoint, current test results and remaining manual-access blockers.

## Outcome

**Partial remediation; deployment remains blocked.** The installed/locked Next.js and React versions could not be upgraded because fresh npm registry access fails DNS resolution. No target lockfile or successful upgrade is being claimed. The working manifest and lockfile remain consistent, with an actual PostCSS security upgrade applied.

The complete `package.json`, root lockfile, installed versions, framework configuration and separate browser-test manifest were inspected. Root dependencies were reinstalled with `npm ci`, followed by build/type/application/security tests. Nothing was deployed.

## Exact versions

| Package/path | Before | Installed and locked after | Checked upgrade target |
|---|---|---|---|
| next | 14.2.18 | **14.2.18 — blocked** | **16.4.6** |
| react | 18.3.1 | **18.3.1 — blocked** | **19.3.1** |
| react-dom | 18.3.1 | **18.3.1 — blocked** | **19.3.1** |
| postcss, direct | 8.4.49 | **8.5.33** | 8.5.33 |
| next/node_modules/postcss | 8.4.31 | Removed; deduplicated to **8.5.33** | Shared 8.5.33 override |
| @types/react | 18.3.20 | 18.3.20 | 19.3.0 (compatible type line) |
| @types/react-dom | 18.3.5 | 18.3.5 | 19.3.0 (compatible type line) |
| jsdom, test only | 16.7.0 | 16.7.0 | Not changed without a resolved audit |
| @playwright/test, separate browser package | Declared 1.60.0; not installed | Declared 1.60.0; not installed | Installation remains blocked |

Targets are stable releases verified from official sources, not canary/RC versions. The [Next.js official latest release](https://github.com/vercel/next.js/releases/tag/v16.4.6) is 16.4.6; the [React official latest release](https://github.com/react/react/releases/tag/v19.3.1) is 19.3.1; the [PostCSS official latest release](https://github.com/postcss/postcss/releases/tag/8.5.33) is 8.5.33. These are the latest official stable releases observed on the audit date, not a guarantee about future releases.

The [Next.js support policy](https://nextjs.org/support-policy) lists 16.x as Active LTS and 14.x as unsupported. Fresh registry queries fail; cached metadata misleadingly reports an older Next.js latest tag (16.2.7). It was not used to select a security target.

## Official advisories and applicability

### Remediated PostCSS findings

Both previously locked PostCSS versions fall in the affected ranges below. The root exact pin and `overrides.postcss = "$postcss"` now ensure all package-manager-resolved PostCSS copies use 8.5.33, including Next.js and Tailwind consumers.

| Official advisory | Severity | Patched minimum | Status |
|---|---|---|---|
| [GHSA-qx2v-qp2m-jg93](https://github.com/postcss/postcss/security/advisories/GHSA-qx2v-qp2m-jg93): unsafe HTML style termination during CSS serialization | Moderate | 8.5.10 | Patched |
| [GHSA-6g55-p6wh-862q](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q): source-map file disclosure | High | 8.5.12 | Patched |
| [GHSA-r28c-9q8g-f849](https://github.com/postcss/postcss/security/advisories/GHSA-r28c-9q8g-f849): source-map path traversal | High | 8.5.18 | Patched |
| [GHSA-fxqj-rqcc-2cmp](https://github.com/postcss/postcss/security/advisories/GHSA-fxqj-rqcc-2cmp): incomplete source-map fix without `from` | Moderate | 8.5.23 | Patched |

The app does not expose a user-CSS processing endpoint. This lowers direct application exposure, but does not excuse vulnerable dependency versions. Regression tests verify safe style serialization and rejection of outside-directory, symlink and missing-`from` map reads using harmless test-owned temporary files. The override changes package-manager dependencies, not arbitrary code vendored inside Next.js; the framework itself still needs upgrading.

### Remaining confirmed framework findings

- [Next.js December advisory](https://nextjs.org/blog/security-update-2025-12-11): the installed 14.2.18 App Router package is below the 14.2.35 fix for the high-severity RSC denial-of-service issues, including the incomplete-fix follow-up CVE-2025-67779. This remains unresolved.
- [GHSA-f82v-jwr5-mffw / CVE-2025-29927](https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw): 14.2.18 is below the 14.2.25 critical middleware authorization-bypass fix. This app currently performs ownership checks in FastAPI and has no Next middleware authorization implementation, so the documented middleware exploit condition is absent. The dependency still falls in the affected range and remains unsupported.

These are confirmed remaining package findings, **not an exhaustive vulnerability count**. Both full and production-only npm audit requests failed; therefore “zero vulnerabilities” cannot be asserted for the rest of the graph. jsdom and its test-only dependencies also need a successful full advisory scan; age/deprecation alone was not labelled a confirmed vulnerability.

### Current framework release checks

The [October 14 Next.js release](https://nextjs.org/blog/nextjs-security-update-october-14-2026) fixes critical upstream RSC typed-array and image decoder issues and a high-severity Server Functions denial of service. The [November 3 security release](https://nextjs.org/blog/november-2026-security-release) fixes cache disclosure/poisoning, compressed-response framing, Edge-cookie exposure and image validation issues in the supported release lines. Next.js 16.4.6 is newer than that release's 16.4.5 fix.

The [React RSC RCE advisory](https://github.com/react/react/security/advisories/GHSA-xqc2-xf4c-x3h3) and [Server Functions DoS advisory](https://github.com/react/react/security/advisories/GHSA-h3gv-c5rc-p453) identify 19.3.1 as a patched server-dom release. These affected-package ranges must not be misreported as proof that direct `react@18.3.1` has those React 19 vulnerabilities. Upgrading direct React alone also does not patch the RSC code shipped by Next.js.

SIGNALFLOW uses a Node route handler that reconstructs response headers and does not forward compression/content-length headers blindly. Cache Components, Edge routes and next/image are not used in the app source. No exploit tests were performed against public services. Conditional applicability is not treated as permission to deploy an unsupported framework.

The locked nanoid 3.3.20 is above the 3.3.12 patch for its [maintainer overflow advisory](https://github.com/ai/nanoid/security/advisories/GHSA-xwg4-73v4-xw9w). This narrow check is not a full clean bill of health for nanoid or other transitive packages.

## Compatibility work completed

The [official Next.js 16 migration guide](https://nextjs.org/docs/app/guides/upgrading/version-16) requires asynchronous request parameters and React 19 type updates. The dynamic run page and API handler now await promised params, integration tests supply the asynchronous context, and previously uninitialized refs now have explicit undefined initial values. These changes pass the existing application's build and tests; they do **not** establish execution compatibility with the unavailable Next.js 16/React 19 install.

The target framework supports React 19 through its [published peer ranges](https://raw.githubusercontent.com/vercel/next.js/v16.4.6/packages/next/package.json). Node 20.20.1 satisfies the documented Node 20.9+ minimum; TypeScript 5.8.3 satisfies the TypeScript 5.1+ minimum. Tailwind/shadcn components and FastAPI behavior were retained.

`security/targets.json` records exact targets. `npm run security:upgrade` resolves a full candidate lockfile in a temporary directory first. On resolution failure it preserves the working manifest, lockfile and node_modules. Only a successfully resolved target tree is committed to the project manifests, followed by `npm ci`. It never fabricates integrity hashes, uses canary versions, bypasses peers with --force/--legacy-peer-deps, or deploys. An installation failure after lock resolution is reported as incomplete and requires finishing npm ci.

`npm run security:check` compares the actual installed and locked versions with these explicit targets. **It currently fails as intended** because the framework upgrade is incomplete. It is a target-consistency check, not a replacement for a full audit.

## Commands actually executed and results

| Command/check | Result |
|---|---|
| Fresh npm view for Next.js 16.4.6 | BLOCKED: registry ENOTFOUND |
| Direct npm install Next.js 16.4.6 / React 19.3.1 / React DOM 19.3.1 | BLOCKED: registry ENOTFOUND; versions unchanged |
| npm run security:upgrade | BLOCKED: registry ENOTFOUND; staged resolution preserved working tree |
| npm install --offline for PostCSS + override | PASS; generated genuine updated lockfile |
| npm ci --offline --cache /tmp/signalflow-npm-cache --no-audit --no-fund | PASS; **183 packages** freshly installed from integrity-checked cached tarballs |
| npm run typecheck | PASS |
| npm run build | PASS on actual **Next.js 14.2.18**, with PostCSS 8.5.33 |
| npm test | **5 passed** |
| npm run test:security | **3 passed** |
| npm run test:integration | **3 passed**, actual FastAPI/isolated persistence through ASGI transport |
| npm run test:dom | **1 passed**, actual API-backed DOM interaction audit |
| npm run test:e2e | BLOCKED: Playwright not installed; no browser passes claimed |
| npm audit --json; npm audit --omit=dev --json | BLOCKED: audit endpoint DNS failure, not a successful scan |
| npm run security:check | EXPECTED FAILURE: actual Next/React/type versions do not match targets |

All 12 executable frontend test cases passed after clean reinstall. Browser checks remain unexecuted. The existing listener/Chrome restrictions also remain relevant to running browser acceptance. No production build on the target Next.js/React versions occurred.

Artifacts are in [audit/security/](audit/security/): before snapshots, actual before/after versions and lock hash, install/reinstall logs, failed full/production audit responses, upgrade-resolution failure, target-check failure and test/build logs. Historic earlier-milestone audit files outside that directory are not evidence of an upgraded framework.

## Finish when registry and browser access are available

From `frontend/`:

```sh
npm run security:upgrade
npm run security:check
npm audit
npm audit --omit=dev
npm run typecheck
npm run build
npm test
npm run test:security
npm run test:integration
npm run test:dom
npm --prefix browser-tests install
npm --prefix browser-tests exec -- playwright install chromium
npm run test:e2e
```

Start the real backend, worker and frontend before the Playwright tests as described in the root README. The failure/SSE test cases require their documented scenario flags. Audit the separate browser-test package too: `npm --prefix browser-tests audit`.

Review/fix any remaining target-version failures, transitive audit findings and browser regressions, then update this report with the real installed versions. **Do not deploy this working tree until the framework upgrade and post-upgrade checks are complete.**
