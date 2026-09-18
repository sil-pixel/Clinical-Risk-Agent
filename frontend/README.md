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
- Model calculation intentionally remains disabled until the model mapping, legal/licensing review, measurement-equivalence review, and safety release gates are approved.
- The interface must continue to disclose that it is a research-only demonstration, not a diagnosis or medical advice, and that it does not provide personalized genetic interpretation.
