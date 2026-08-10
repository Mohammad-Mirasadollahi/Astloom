# Change Society Frontend Tests

State-to-view mapping checks live here because the judged UI must stay aligned with backend run states without requiring a browser harness for every gate.

| File | Focus |
| --- | --- |
| `demo-state.test.mjs` | Run state → demo view, `statusTone` |
| `cinematic-beats.test.mjs` | Cinematic beat ordering |
| `api-errors.test.mjs` | `parseApiError` |
| `org-policy-intake.test.mjs` | Guided intake wizard helpers (`firstPendingChallenge`, activation gating) |
| `evaluation-view.test.mjs` | Evaluation display helpers |
| `routes.test.mjs` | Sidebar route registry and `routeByPath` |
| `utils-workspace.test.mjs` | `cn`, `panelClass` |
| `scenario-cinematic.test.mjs` | Scenario narration and captions |
| `metric-display.test.mjs` | Metric cell formatting |

```bash
bash tests/frontend/change-society/run-frontend-tests.sh
# or from archives/hackathon/frontend:
npm test
```

Run `npm run typecheck` in `frontend` for the full TypeScript surface.
