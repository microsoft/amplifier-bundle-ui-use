# Optional bounded UI use

This development candidate provides a portable browser/computer controller and an
Amplifier adapter. Ordinary model selection is the default. The portable library
has no Core, Foundation, application or decision-library dependency. The `browser`
extra installs Playwright; the controller imports it only when a browser is opened.
Provision that extra and a compatible browser in the owned environment when
enabling browser access. Work's default include installs no browser SDK or decision
SDK or desktop executor. Installation opens no browser and performs no inference.

`Controller` shares one executor and verifier between `StandardSelector` and an
explicit `DecisionSelector`. The latter imports `amplifier_decisions` only when
selected. A caller supplies ordinary completion, text writing and observable
success conditions. Missing backends, unavailable answers or local abstention may
use the configured ordinary fallback. A model's blocked vote ends the task; the
caller can explicitly recover using ordinary selection.

Every iteration observes, checks whether the goal is already met, selects an
observed candidate, authorizes/executes it, then verifies the visible result.
DONE alone is never sufficient. Step, cycle and time budgets are finite.
Cancellation propagates. Stale evidence causes re-observation; unknown execution
stops without replay or a new-model retry. Effects are not rolled back.
Repeated ineffective choices are detected across DOM replacements. With an
ordinary fallback configured, the controller asks it for a different observed
action before another dispatch; continued repetition returns control for a new
plan. Transient action history includes target names and chosen options. Public
progress receipts still omit page contents and typed text.

The optional local browser creates a private context, requires explicit origins and approval,
and rejects unknown candidates. It rechecks evidence after approval and in the
same JavaScript turn as DOM dispatch. Model outputs are opaque candidate IDs,
not raw selectors, code or coordinates. Observations are untrusted page content.
An ordinary model writes text only after a field is chosen. Progress receipts
omit typed text, screenshots and page contents.

## Amplifier composition

Add `behaviors/ui-use.yaml` to an existing host. In the CLI:

```sh
amplifier bundle use anchors
amplifier bundle add git+https://github.com/microsoft/amplifier-bundle-ui-use@main#subdirectory=behaviors/ui-use.yaml --app
```

Development acceptance can use the behavior's absolute local file URI and explicit
module source overrides. Work's main bundle includes this behavior
once; work-amp-dev inherits it. The behavior selects no orchestrator, context or
provider. Its module declares `ui_use` as a bounded programmatic caller for only
`browser` and `computer`; explicit host dispatch restrictions still win.
The adapter binds `tools.dispatch`, so
inner calls pass through ordinary tool hooks and execution locks. Missing dispatch
returns blocked, with individual tools available for recovery.

For a local Playwright executor, install the optional `browser` extra and a browser
binary in the consuming host's owned environment. A host-managed or connected
browser can provide its own executor without that extra. The `decisions` extra is
needed only for optional decision selection:

```sh
uv pip install 'amplifier-bundle-ui-use[browser,decisions] @ git+https://github.com/microsoft/amplifier-bundle-ui-use@main'
python -m playwright install chromium
```

Select only the extras needed by the host. OS/browser requirements and device
permissions remain separate from package installation. Hosts should record
installed revisions and qualify updates before activation.

`model.complete()` supplies attributed ordinary inference for selection/writing.
It uses the selected provider/account, applies request policy, counts internal
calls, checks input limits and observes cancellation. It is a stateless request,
not another conversation turn. The new streaming implementation and live adapter
share that service. A separate per-turn internal-call allowance bounds its use;
unified routing/financial budgets are later work.

```yaml
tools:
  - module: tool-ui-use
    config:
      browser:
        enabled: true
        allowed_origins: [https://example.com]
      selection:
        browser:
          mode: standard
        computer:
          mode: standard
```

Explicit decision selection uses `{mode: decision, backend: selection,
allow_external_state: true}` after a provider registers that named capability.
OpenAI and Azure OpenAI expose decisions from their existing provider modules;
the Jev provider adds the new vendor. Install each selected provider’s `decisions`
extra where offered. All three use `amplifier-lib-decisions`; no decision bundle
or duplicate credential configuration is needed. For example, an OpenAI account
can add `decisions: {enabled: true, backends: {selection: {enabled: true,
model: gpt-6-luna}}}`. Multiple named models share the account.
The tool's `mode: standard` argument always permits an ordinary run.
Requesting decision mode cannot activate an unconfigured backend. Keys, metadata
and installed packages never change the default.

When the host sets `browser.allow_requested_origins: true`, opening a new origin
asks for exact URL and origin permission before adding it to this conversation’s
in-memory allowlist. The default is false. Cross-origin redirects stay blocked.

`browser.open` starts an allowed URL; observe/act remain individually available.
`ui_use` takes a task, surface and nonempty success criteria: visible text, exact
URL and/or a field name/value. Browser input requires the host approval system unless the
owner explicitly enables unattended writes. Browser access and selection settings
are independent.

Computer tasks use the existing `computer` tool's opt-in observe/act extension.
The base behavior does not install a desktop executor. A host with a canonical
`computer` tool can enable its `observed_control` option, or compose this bundle's
separate `behaviors/computer.yaml`, which includes canonical computer-use and
enables that option. Adding Work alone does not grant desktop access. The initial
observed lane is local X11 OCR and click/wait only. OCR
requires Tesseract; labels are regions, not accessibility controls. Both selectors
revalidate the observed target after human approval; reading time alone does not
expire an unchanged target. Every receipt identifies the configured selector,
effective selector, decision outcome and any ordinary fallback. Ordinary computer tools
retain their full existing repertoire.

## Optional host-managed browser targets

A host can supply the `ui.use.host` capability for a managed browser or a connected device. Set
`browser.host_adapter: true` to use it. The adapter forwards open, observe and act
operations through that host capability; it does not install an extension, pair
a device, choose an account or start a browser itself. Host target selection,
leases, consent, Stop and unknown-effect recovery remain authoritative. Other
hosts can continue using the local Playwright executor or individual tools.

An unavailable selected target is reported with its recovery information rather
than silently switching signed-in accounts. An absent host capability does not
claim computer or browser access. Optional decision models select actions over
the same observation and executor as ordinary selection; they do not bypass
host permissions or supply a separate device-control transport.

## Limits and evaluation

DOM observation covers the visible top document, labels and controls; it is not a
full accessibility tree. Frames and shadow DOM need later work. Dispatch uses DOM
click/input/change, not trusted native browser input, so some apps will not respond.
Truncated coverage prevents decision selection. Downloads, popups and dialogs are
not interactive workflows. Visible success criteria do not prove hidden business
correctness.

Thresholds (probability .8, margin .15) are experimental and vendor specific.
Preserve failures and compare on identical fixtures/executors. Report verified
success before latency, with warm/cold state, fallbacks and usage. A held-out task
used for debugging is no longer untouched evaluation. Box execution is not enabled.
Neither confidence nor a valid box conveys permission or presence.

Run `pytest` in an owned environment. Browser tests use Playwright's installed
browser, or `UI_USE_CHROMIUM_EXECUTABLE`. The DTU-only
`DTU_CHROMIUM_SINGLE_PROCESS` option enables ARM64 development launch flags.
Component tests use no external inference or human desktop.

## Repeatable multi-record exercise

[`tests/fixtures/triage.html`](tests/fixtures/triage.html) is a standalone support
triage exercise that can be served from an allowed local origin in any host.
Its [task prompt](tests/fixtures/triage-prompt.txt) asks the agent to identify
eligible tickets, apply conditional routing and urgency rules, write notes, save
individual records, and validate the batch while preserving excluded records.
Replace `[fixture URL]` in the prompt with your owned fixture URL. This fixture
changes no external systems.

Progress is local to the browser context and survives page reloads. A fresh
context or **Reset this exercise** starts over. The final validator checks every
required field and note against an independent expected state and checks that
the three excluded records are unchanged. Completion requires explicit validation
and confirmation. Use visible **Saved <ticket ID>** checkpoints for individual
updates, and **Triage batch complete: 3 updated, 3 unchanged.** for the final goal.
The workflow needs at least 24 actions and supports multiple bounded UI-use calls.
This is a development exercise, not a held-out benchmark or general-site acceptance.
