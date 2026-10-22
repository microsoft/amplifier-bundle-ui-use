# CLI + Anchors ecosystem acceptance — 2026-10-19

This is a historical qualification of the October 19 candidate, not a current
release or platform-support claim. Package ownership and installation instructions
are maintained in the repository README.

The portable UI-use behavior ran as an app-level addition to a real installed
`amplifier-app-cli`, with the canonical Anchors root. No CLI, Foundation or Anchors
code changes were required. OpenAI decision inference reused the existing
configured provider client. Work's main root includes the behavior once and
work-amp-dev inherits it.

## Ownership and intended PR order

| Owner | Change |
| --- | --- |
| Shared contract | Finalize a small optional decision interface/package; the current dataclasses remain staged in the original spike package. No mandatory new Core module category or provider method. |
| provider-openai | Optional Decisions registration, wire mapping, metadata and configured-client reuse. This candidate is implemented and tested live. |
| provider-azure-openai | Reuse Azure credential/token management for Decision-1, with an explicitly configured Foundry resource/deployment and its distinct route. Still to migrate; earlier standalone/Unified live qualification remains separate. |
| New provider-jev | Own JEV credentials/transport/capabilities without pretending JEV is a chat provider. Still to migrate from the original spike. |
| loop-streaming, then loop-live | Generic admitted tool dispatch and attributed ordinary inference, shared by both loops. No UI selectors, vendors or thresholds in the runtime. |
| amplifier-bundle-ui-use | Controller, ordinary/decision selection, browser executor, verification and reusable behavior. Browser SDK is an optional extra. |
| amplifier-bundle-computer-use | Existing desktop executor and opt-in observed-candidate interface. Its earlier X11 qualification is unchanged; this CLI run qualifies browser use. |
| amplifier-bundle-work | One include in the main root; work-amp-dev inherits it. Publish the dependency before merging the canonical include. |
| CLI / Foundation / Anchors | Existing app behaviors and source overrides suffice for this acceptance. No speculative implementation PR. |
| Unified, later routing-matrix | Consume provider-owned capabilities in setup/binding/routing. The retained Unified preview still uses its earlier qualified snapshot. |

OpenAI/Gemini provider-owned image backends supplied the ownership precedent.
Capability registration and consumer selection are separate: credentials or an
installed backend never enable decision selection. Per-surface standard choices
and per-call standard recovery remain available. API-compatible chat providers
do not automatically advertise OpenAI's Decisions endpoint. Anthropic/Google
remain ordinary model options unless an actual additional capability is supported.
Perplexity remains excluded.

## Isolated instance

- Environment: task-owned Digital Twin Universe with a dedicated unprivileged CLI account.
- CLI source, Python environment, home, workspace, modules and browser context were isolated.
- Python: 3.13.16. No shared host application or user state was mounted writable.
- Real OpenAI planner/model: `gpt-6-luna`; SDK 3.35.1; Core 2.0.2.
- CLI base: `7199e696ab6033ba70737ee3cf7ba0ca18d66afa`.
- Foundation dependency: `8d26eceb9b7cafe6e93346f8f4294596bd45dcd1`.
- Streaming base: `dd916499344671e0209d4951bc025777e3e891fd`.
- OpenAI provider base: `cd94b6cb0532468fab8a04624cd3e3773acf1094`.

The CLI `bundle add` command registered the candidate behavior by an absolute
local file URI with `--app`. Local module overrides point at unpublished candidates;
there is no fake published repository or change to the user's host CLI. Anchors
retained `loop-streaming`, `context-simple`, its instructions and existing tools.
The CLI app source itself is unchanged.

## Live checks

All UI tasks used the same loopback synthetic form. The planner opened
the page, then called `ui_use` to enter Ada, select Blue and Save. The verifier
required visible `Saved Ada blue`. The harness responded to the real CLI approval
prompts only for those four exact synthetic actions (open, type, select, click).
It did not disable approvals or enable unattended writes.

| Check | Outcome |
| --- | --- |
| Unmodified CLI + Anchors baseline | Exact baseline response |
| Ordinary behavior defaults; no selection override | Verified, 18.683 s, standard selector only |
| Explicit provider-owned Decisions | Verified, 13.525 s, OpenAI Decisions, no fallback |
| Explicit standard override with Decisions configured | Verified, 19.326 s, standard selector only |

Dependencies/application were warm; each CLI process and browser context was new.
These are integration checks across iterations, not a latency comparison or
general reliability benchmark. Two earlier successful flow sessions are retained
as well; the final ordinary/decision cases were repeated after runtime changes.

The final decision trace contains three `decision:request`/`decision:response`
pairs, one attributed `model:complete` for ordinary text writing, three UI steps
and four exact approvals. The actual requested/reported decision model and
backend appear in controller receipts. Ordinary requests count toward the turn's
actual `llm_calls`; they no longer bypass runtime request policy. The nested-call
allowance is separate from the existing foreground iteration budget. Decision
usage is reported separately; unified financial/routing accounting remains work.

## Regression checks

| Suite | Result |
| --- | --- |
| Streaming loop, full suite | 501 passed |
| Live loop, full suite | 120 passed, 4 skipped |
| OpenAI Decisions plus existing image backend tests | 38 passed |
| Original decision adapters/contracts | 42 passed |
| UI controller/browser tests | 26 passed |
| Work composition, amp-dev inheritance and source tracking | 22 passed |
| Retained Unified browser smoke | All 6 flows passed |

Counts overlap where a shared execution contract is exercised in both loops.
Covered regressions include hook denial, approval rejection, parent attribution,
expired/revoked leases, cancellation, serialization, same-client auth reuse,
no automatic retries, ordinary defaults and composition preserving host runtime.
The environment's installed dependencies passed `uv pip check`. The UI-use wheel
is checked separately to ensure browser dependencies are optional.

Initial test-environment setup needed the live loop's explicit local streaming
override and its jsonschema dependency. Tests exposed and repaired a typed-message
size-estimate error and a cancellation-docstring regression. No outstanding test
failure is treated as a pass. None of these setup changes touched the host app or
the retained Unified source.

## Evidence and limits

Source commits, source parity, installed module locations, exact commands,
private session identifiers, cleanup and retained resources were captured in the
owner's private validation receipt and workspace manifest. Private evidence and
credentials are not distributed with this package.

This proves app-level browser integration with a provider-owned OpenAI capability.
It does not qualify JEV/Decision-1 provider migrations, desktop CLI parity, arbitrary
sites, other platforms, calibrated thresholds, production packaging or routing.
The shared contract's final packaging and the public UI-use repository must be
settled before merge/release. At qualification time no PR had been published or merged, and the live
installation had not been updated. Ordinary selection was restored as the CLI default.
