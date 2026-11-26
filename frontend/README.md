# SIGNALFLOW frontend

Next.js App Router, TypeScript, Tailwind and manually installed shadcn/ui Radix primitives. See the [root README](../README.md) for full three-process setup, authentication, test commands and current environment restrictions.

```sh
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. Configure the backend demo code and matching APP_ORIGIN first. The API proxy uses server-only BACKEND_URL; do not expose OpenAI credentials here. No mock data mode or mock API fallback is bundled.

`src/components` contains the workspace shell, dashboard, form, history, workflow timeline, evidence/signals and revisioned draft review. `src/components/ui` contains shadcn-style Button/Card/Input primitives; `components.json` supports later shadcn additions. `src/hooks` owns abortable resource loading and SSE reconnect/replay handling. `src/lib` holds generated contracts, safe API transport, runtime response checks and status mappings.

Commands: `npm run typecheck`, `npm test`, `npm run test:integration`, `npm run test:dom`, `npm run build`. Browser acceptance tests have their own package in `browser-tests/`; installation and real listeners are required. `npm run test:e2e` runs that suite once installed.

Current checkpoint: [../ENGINEERING_REPORT.md](../ENGINEERING_REPORT.md). Installed/locked Next.js 16.4.6, React/React DOM 19.3.1 and PostCSS 8.5.33 now match the checked targets; jsdom is 29.1.1. `npm run build` uses Webpack and passes. The default Turbopack build could not bind its internal port in this environment. `npm run security:check` passes; it is not a full advisory scan. `npm run test:security` exercises the PostCSS fixes. Fresh npm audit, real PostgreSQL/OpenAI/browser checks and deployment remain blocked.

The earlier [security audit](SECURITY_AUDIT.md) is a historical snapshot. No current claim of zero vulnerabilities or deployment readiness is made.
