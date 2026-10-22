from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import time


def semantic_state(observation):
    """Progress identity only; never used as execution authorization/freshness.

    DOM replacements can change every target ID without changing the visible
    page. Preserve values, text, order, geometry and scroll position, but omit
    observer-assigned identities from this internal repetition check.
    """
    state = observation['state']
    normalized = {key: value for key, value in state.items() if key not in {'document', 'revision'}}
    if isinstance(state.get('elements'), list):
        normalized['elements'] = [{key: value for key, value in row.items() if key != 'id'} for row in state['elements']]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def semantic_action(observation, candidate, text=None):
    target = next((i for i, row in enumerate(observation['state'].get('elements', []))
                   if row.get('id') == candidate.get('target')), None)
    description = {key: value for key, value in candidate.items() if key not in {'id', 'target'}}
    return json.dumps([description, target, text], sort_keys=True, ensure_ascii=False)


def action_history(candidate, outcome):
    # Transient model context; text entered by the writer is never retained here
    # or added to public progress receipts.
    return {**{key: candidate[key] for key in ('operation', 'name', 'option') if key in candidate},
            'execution': outcome}


@dataclass(frozen=True)
class Selection:
    candidate: str | None = None
    text: str | None = None
    reason: str | None = None
    evidence: dict = field(default_factory=dict)


class Controller:
    """Observe/select/execute/verify. Executor owns authorization and fresh validation.

    execute(observation, candidate, text) must authorize the exact action then
    revalidate the observation at dispatch. It returns completed/stale/denied/
    failed/unknown. No completed action is replayed and unknown ends the run.
    """
    def __init__(self, executor, selector, *, verifier, fallback=None, writer=None,
                 progress=None, max_steps=12, deadline_seconds=60, max_cycles=3):
        if not 1 <= max_steps <= 50 or not 0 < deadline_seconds <= 300 or max_cycles < 1:
            raise ValueError("Invalid controller budget")
        self.executor, self.selector, self.verifier = executor, selector, verifier
        self.fallback, self.writer, self.progress = fallback, writer, progress
        self.max_steps, self.deadline, self.max_cycles = max_steps, deadline_seconds, max_cycles

    async def run(self, goal):
        started, events, visits, history, dispatched = time.monotonic(), [], {}, [], False
        stale_count = 0
        def finish(status, reason=None):
            return {"status": status, "reason": reason, "steps": len(events), "events": events,
                "elapsed_ms": round((time.monotonic()-started)*1000, 3), "effects": "not_rolled_back"}
        try:
            async with asyncio.timeout(self.deadline):
                for step in range(self.max_steps):
                    observed = await self.executor.observe()
                    if await self.verifier(observed) is True:
                        return finish("completed", "observable_goal_satisfied")
                    observed = {**observed, "recent_actions": history[-8:]}
                    selection = await self.selector.select(goal, observed)
                    decision_evidence = selection.evidence
                    fallback_reason = None
                    proposed = next((c for c in observed['candidates'] if c['id'] == selection.candidate), None)
                    state_key = semantic_state(observed)
                    # Escalate a confident but ineffective choice before another
                    # dispatch. The ordinary selector must still choose an
                    # observed target, and every executor check remains intact.
                    if proposed and visits.get((state_key, semantic_action(observed, proposed)), 0) >= self.max_cycles:
                        if self.fallback is None:
                            return finish('blocked', 'cycle')
                        fallback_reason = 'repeated_action_without_progress'
                        observed = {**observed, 'recovery': {'reason': fallback_reason,
                            'previous_action': action_history(proposed, 'no_observable_progress')}}
                        selection = await self.fallback.select(goal, observed)
                    if selection.candidate is None and self.fallback is not None:
                        if fallback_reason is None:
                            fallback_reason = selection.reason or "selector_abstained"
                            selection = await self.fallback.select(goal, observed)
                    event = {"step": step, "observation": observed["revision"],
                        "selector": getattr(self.selector, "name", "custom"), "fallback": fallback_reason,
                        "effective_selector": getattr(self.fallback if fallback_reason else self.selector, "name", "custom"),
                        "decision": decision_evidence,
                        "fallback_evidence": selection.evidence if fallback_reason else None}
                    events.append(event)
                    if selection.candidate is None:
                        return finish("blocked", selection.reason or "no_selection")
                    candidate = next((c for c in observed["candidates"] if c["id"] == selection.candidate), None)
                    if candidate is None:
                        return finish("blocked", "unobserved_candidate")
                    event.update(candidate=candidate["id"], operation=candidate["operation"])
                    if candidate["operation"] == "DONE":
                        # A selector's DONE vote never supplies its own verification.
                        verified = await self.verifier(await self.executor.observe())
                        event["verified"] = verified is True
                        return finish("completed" if verified is True else "blocked", None if verified is True else "completion_unverified")
                    if candidate["operation"] == "BLOCKED":
                        return finish("blocked", "selector_blocked")
                    text = selection.text
                    if candidate["operation"] == "TYPE_TEXT" and text is None:
                        if self.writer is None: return finish("blocked", "writer_unavailable")
                        text = await self.writer(goal, observed, candidate)
                    if candidate["operation"] == "TYPE_TEXT" and (not isinstance(text, str) or len(text) > 10_000):
                        return finish("blocked", "invalid_text")
                    key = (state_key, semantic_action(observed, candidate))
                    visits[key] = visits.get(key, 0) + 1
                    if visits[key] > self.max_cycles:
                        return finish("blocked", "no_progress_after_fallback" if fallback_reason else "cycle")
                    if self.progress is not None: await self.progress(dict(event))
                    dispatched = True
                    outcome = await self.executor.execute(observed, candidate, text)
                    dispatched = False
                    event["execution"] = outcome.get("status", "unknown")
                    if self.progress is not None: await self.progress(dict(event))
                    history.append(action_history(candidate, event['execution']))
                    stale_count = stale_count + 1 if event['execution']=='stale' else 0
                    if stale_count >= 3:
                        return finish('blocked','unstable_observation')
                    if event["execution"] == "completed" and await self.verifier(await self.executor.observe()) is True:
                        event["verified"] = True
                        if self.progress is not None: await self.progress(dict(event))
                        return finish("completed", "observable_goal_satisfied")
                    if event["execution"] not in {"completed", "stale"}:
                        return finish(event["execution"] if event["execution"] in {"denied", "failed", "unknown"} else "unknown",
                                      outcome.get("reason"))
                return finish("budget", "step_limit")
        except TimeoutError:
            return finish("unknown" if dispatched else "budget", "deadline_during_execution" if dispatched else "deadline")
        except asyncio.CancelledError:
            # Preserve host cancellation and let its dispatcher record unknown effects.
            raise
        except Exception:
            return finish("unknown" if dispatched else "blocked", "execution_unconfirmed" if dispatched else "observation_or_selection_unavailable")


async def verify_conditions(observation, conditions):
    """Deliberate caller assertions; no selector-provided success claim."""
    if not isinstance(conditions, dict) or not conditions or set(conditions) - {"text", "url", "field"}:
        return False
    state = observation["state"]
    if "text" in conditions and (not isinstance(conditions["text"], str) or not conditions["text"] or conditions["text"] not in state.get("text", "")):
        return False
    if "url" in conditions and conditions["url"] != state.get("url"):
        return False
    if "field" in conditions:
        field = conditions["field"]
        if not isinstance(field, dict) or set(field) != {"name", "value"}:
            return False
        if not any(row.get("name") == field["name"] and row.get("value") == field["value"] for row in state.get("elements", [])):
            return False
    return True
