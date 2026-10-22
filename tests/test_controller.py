import asyncio
import copy
import sys
from types import SimpleNamespace

import pytest

from amplifier_ui_use import Controller, Selection, StandardSelector, selector_for
from amplifier_ui_use.controller import verify_conditions


def observation(revision="a"):
    return {"revision": revision, "state": {"text": "Not saved", "url": "https://test/", "elements": []},
        "candidates": [{"id": "save", "operation": "CLICK"}, {"id": "text", "operation": "TYPE_TEXT"},
                       {"id": "done", "operation": "DONE"}, {"id": "blocked", "operation": "BLOCKED"}]}


class Executor:
    def __init__(self, status="completed"):
        self.status, self.calls, self.reads = status, [], 0
    async def observe(self): self.reads += 1; return observation()
    async def execute(self, obs, candidate, text):
        self.calls.append((candidate["id"], text)); return {"status": self.status}


class Sequence:
    name="fixture"
    def __init__(self, *values): self.values=iter(values)
    async def select(self, goal, obs):
        value=next(self.values);return value if isinstance(value,Selection) else Selection(value)


async def yes(obs): return True
async def no(obs): return False


async def test_standard_path_has_no_decision_import_or_backend_call(monkeypatch):
    called=[]
    async def model(prompt): called.append(prompt);return '{"candidate":"save"}'
    standard=StandardSelector(model)
    poison=SimpleNamespace(decide=lambda _: (_ for _ in ()).throw(AssertionError("decision called")))
    for config in (None, {}, {"mode":"off","backend":"configured"}, {"mode":"standard","backend":"configured"}):
        selected,fallback=selector_for(config,{"configured":poison},standard)
        assert selected is standard and fallback is None
        assert (await selected.select("save",observation())).candidate=="save"
    assert len(called)==4


@pytest.mark.parametrize("status", ["denied","failed","unknown"])
async def test_unconfirmed_or_denied_execution_never_replayed(status):
    executor=Executor(status)
    result=await Controller(executor,Sequence("save","done"),verifier=no).run("Save")
    assert result["status"]==status and len(executor.calls)==1


async def test_done_requires_independent_fresh_verification():
    executor=Executor()
    result=await Controller(executor,Sequence("done"),verifier=no).run("Save")
    assert result["status"]=="blocked" and result["reason"]=="completion_unverified"
    assert executor.reads==2 and not executor.calls


async def test_stale_reobserves_and_reselects_before_next_action():
    executor=Executor("stale")
    async def verified_after_fresh_done(obs):return executor.reads==3
    result=await Controller(executor,Sequence("save","done"),verifier=verified_after_fresh_done).run("Save")
    assert result["status"]=="completed" and executor.reads==3
    assert result["events"][0]["execution"]=="stale" and len(executor.calls)==1


async def test_fallback_only_before_execution_and_keeps_receipt():
    executor=Executor("unknown")
    result=await Controller(executor,Sequence(Selection(reason="decision_unavailable")),
        fallback=Sequence("save"),verifier=no).run("Save")
    assert result["status"]=="unknown" and len(executor.calls)==1
    assert result["events"][0]["fallback"]=="decision_unavailable"


async def test_unobserved_target_is_blocked():
    executor=Executor()
    result=await Controller(executor,Sequence("invented"),verifier=no).run("Save")
    assert result["reason"]=="unobserved_candidate" and not executor.calls


async def test_cycles_and_step_budget_are_bounded():
    executor=Executor()
    result=await Controller(executor,Sequence(*(["save"]*9)),verifier=no,max_cycles=2).run("Save")
    assert result["reason"]=="cycle" and len(executor.calls)==2
    executor=Executor()
    result=await Controller(executor,Sequence("save"),verifier=no,max_steps=1).run("Save")
    assert result["status"]=="budget" and len(executor.calls)==1


async def test_writer_is_used_only_for_selected_type_action():
    calls=[]
    async def writer(goal,obs,candidate): calls.append(candidate["id"]);return "Ada"
    executor=Executor()
    async def entered(obs):return executor.calls==[("text","Ada")]
    result=await Controller(executor,Sequence("text","done"),verifier=entered,writer=writer).run("Enter Ada")
    assert result["status"]=="completed" and calls==["text"] and executor.calls==[("text","Ada")]


async def test_deadline_during_action_is_unknown_and_cancellation_propagates():
    executor=Executor()
    started=asyncio.Event()
    async def slow(*args): started.set();await asyncio.sleep(10)
    executor.execute=slow
    result=await Controller(executor,Sequence("save"),verifier=no,deadline_seconds=.01).run("Save")
    assert result["status"]=="unknown"
    started.clear()
    task=asyncio.create_task(Controller(executor,Sequence("save"),verifier=no).run("Save"))
    await started.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task


@pytest.mark.parametrize("status,p,margin,expected",[("answered",.95,.9,"save"),("answered",.6,.2,None),("refused",.99,.98,None),("invalid",.99,.98,None)])
async def test_decision_abstention_and_refusal(monkeypatch,status,p,margin,expected):
    from amplifier_decisions import Answer,DecisionResult,Capabilities
    class Backend:
        capabilities=Capabilities()
        async def decide(self,req):
            assert req.questions[0].choices.keys()=={"save","text","done","blocked"}
            return DecisionResult("fixture","requested","reported",{"next":Answer("next","choice",status,"save",{"save":p,"text":1-p,"done":0,"blocked":0},.97)},10)
    selected,_=selector_for({"mode":"decision","backend":"selection","allow_external_state":True},{"selection":Backend()},None)
    value=await selected.select("Save",observation())
    assert value.candidate==expected
    assert value.evidence["reported_model"]=="reported"


async def test_candidate_coverage_abstains_before_inference():
    class Backend:
        capabilities=SimpleNamespace(max_choices=255)
        async def decide(self,req): raise AssertionError("must not call")
    selected,_=selector_for({"mode":"decision","backend":"selection"},{"selection":Backend()},None)
    obs=observation();obs["truncated"]=True
    assert (await selected.select("Save",obs)).reason=="candidate_coverage"


async def test_success_conditions_are_explicit_observable_assertions():
    obs=observation();obs["state"]["text"]="Saved successfully";obs["state"]["elements"]=[{"name":"Name","value":"Ada"}]
    assert await verify_conditions(obs,{"text":"Saved successfully","url":"https://test/","field":{"name":"Name","value":"Ada"}})
    for criteria in ({},None,{"text":""},{"text":"Oops"},{"arbitrary_script":"true"},{"field":{"name":"Name","value":"Other"}}):
        assert not await verify_conditions(obs,criteria)


async def test_verified_effect_stops_before_model_can_repeat_successful_click():
    executor=Executor()
    async def saved(obs):return len(executor.calls)==1
    result=await Controller(executor,Sequence("save","save","save"),verifier=saved).run("Save")
    assert result["status"]=="completed" and executor.calls==[("save",None)]
    assert result["events"][0]["verified"] is True


async def test_dom_replacement_cannot_evade_cycle_detection_and_escalates_before_dispatch():
    class Rerender(Executor):
        async def observe(self):
            self.reads += 1
            return {'revision': str(self.reads), 'state': {'text': 'Invalid form', 'document': str(self.reads),
                'elements': [{'id': str(self.reads), 'name': 'Validate'}]},
                'candidates': [{'id': str(self.reads), 'target': str(self.reads), 'name': 'Validate', 'operation': 'CLICK'},
                    {'id': 'repair', 'name': 'Edit', 'operation': 'CLICK'}]}
    class Confident:
        name = 'decision'
        async def select(self, goal, obs):
            return Selection(obs['candidates'][0]['id'], evidence={'probability': .999})
    class Recover:
        name = 'standard'
        async def select(self, goal, obs):
            assert obs['recovery']['reason'] == 'repeated_action_without_progress'
            assert obs['recent_actions'][-1] == {'operation': 'CLICK', 'name': 'Validate', 'execution': 'completed'}
            return Selection('repair')
    executor = Rerender()
    async def repaired(obs): return any(key == 'repair' for key, text in executor.calls)
    result = await Controller(executor, Confident(), fallback=Recover(), verifier=repaired, max_cycles=2).run('Repair')
    assert result['status'] == 'completed' and len(executor.calls) == 3
    assert result['events'][-1]['effective_selector'] == 'standard'
    assert result['events'][-1]['fallback'] == 'repeated_action_without_progress'
    assert result['events'][-1]['decision']['probability'] == .999


async def test_repeated_action_is_allowed_when_visible_state_changes():
    executor = Executor()
    async def observe():
        obs = observation(str(len(executor.calls)))
        obs['state']['text'] = 'Page ' + str(len(executor.calls))
        return obs
    executor.observe = observe
    result = await Controller(executor, Sequence('save', 'save', 'save'), verifier=no, max_steps=3, max_cycles=1).run('Next page')
    assert len(executor.calls) == 3 and result['reason'] == 'step_limit'


async def test_fallback_cannot_continue_same_ineffective_action():
    executor = Executor()
    result = await Controller(executor, Sequence('save', 'save'), fallback=Sequence('save'), verifier=no, max_cycles=1).run('Save')
    assert result['reason'] == 'no_progress_after_fallback' and len(executor.calls) == 1


@pytest.mark.parametrize('response,code', [('PRIVATE text instead of JSON', 'invalid_json'),
    ({'candidate': 'save', 'unexpected': 'PRIVATE'}, 'invalid_selection_shape')])
async def test_invalid_ordinary_selection_explains_format_without_recording_content(response, code):
    async def complete(prompt): return response
    result = await StandardSelector(complete).select('Save', observation())
    assert result.reason == 'ordinary_model_invalid_selection' and result.candidate is None
    assert result.evidence == {'format_error': code} and 'PRIVATE' not in repr(result)


async def test_unstable_observations_stop_after_three_fresh_attempts():
    executor=Executor('stale')
    result=await Controller(executor,Sequence('save','save','save','save'),verifier=no).run('Save')
    assert result['status']=='blocked' and result['reason']=='unstable_observation'
    assert executor.reads==3 and len(executor.calls)==3
