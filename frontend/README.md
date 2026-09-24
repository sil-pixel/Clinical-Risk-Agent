# Research Questionnaire Frontend

Accessible React/Vite implementation of the approved public questionnaire copy.

## Run locally

```bash
npm install
npm run dev
```

Use `npm test` for questionnaire contract tests and `npm run build` for a production build.

## Privacy and release constraints

- Answers exist only in React memory. Do not add cookies, browser storage, service-worker caches, URL parameters, analytics payloads, or console logging for questionnaire answers.
- The session clears after exactly 30 minutes without pointer, keyboard, or touch activity.
- Public copy and markup use opaque question IDs only. Internal feature mapping belongs in the backend.
- “I do not remember” is non-scored and prevents model readiness.
- The product owner accepted the current option order as a prototype mapping on 2026-09-24. Model calculation remains disabled in this public UI until a protected backend workflow, safety controls, and release review are implemented. Independent source-instrument equivalence has not been established.
- The interface must continue to disclose that it is a research-only demonstration, not a diagnosis or medical advice, and that it does not provide personalized genetic interpretation.
