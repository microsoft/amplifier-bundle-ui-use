import asyncio
import os
from pathlib import Path

from aiohttp import web
import pytest
import pytest_asyncio

from amplifier_ui_use.browser import Browser
from amplifier_ui_use import Controller, Selection
from amplifier_ui_use.controller import verify_conditions

HTML='''<!doctype html><html><head><title>Synthetic form</title></head><body>
<h1>Contact preferences</h1><label>Name <input id="name" value=""></label>
<label>Team <select id="team"><option value="red">Red</option><option value="blue">Blue</option></select></label>
<button id="save" onclick="document.querySelector('#status').textContent='Saved '+document.querySelector('#name').value+' '+document.querySelector('#team').value">Save</button>
<button disabled>Disabled</button><button style="display:none">Hidden</button>
<label>Password <input type="password"></label><div id="status">Not saved</div>
<button id="covered" style="position:absolute;left:500px;top:300px">Covered</button>
<div style="position:absolute;left:490px;top:290px;width:200px;height:100px;background:white;z-index:10"></div>
</body></html>'''


@pytest_asyncio.fixture
async def browser():
    app=web.Application();app.router.add_get('/',lambda request:web.Response(text=HTML,content_type='text/html'))
    runner=web.AppRunner(app);await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    async def allow(action):return True
    value=Browser(allowed_origins=[f'http://127.0.0.1:{port}'],authorize=allow,
        executable_path=os.environ.get('UI_USE_CHROMIUM_EXECUTABLE'),
        launch_args=['--no-sandbox','--single-process','--no-zygote','--disable-gpu'] if os.environ.get('DTU_CHROMIUM_SINGLE_PROCESS') else [])
    await value.open(f'http://127.0.0.1:{port}/')
    try:yield value
    finally:await value.close();await runner.cleanup()


async def test_observed_candidates_exclude_hidden_disabled_password_occluded(browser):
    observed=await browser.observe()
    names={c.get('name') for c in observed['candidates']}
    assert {'Name','Team','Save'} <= names
    assert not {'Hidden','Disabled','Password','Covered'} & names
    assert {'done','blocked','wait'} <= {c['id'] for c in observed['candidates']}
    assert (await browser.observe())['revision']==observed['revision']


async def test_actual_browser_type_select_click_verified_flow(browser):
    class Selector:
        name='scripted-general-fixture'
        async def select(self,goal,obs):
            state=obs['state'];rows=state['elements']
            if 'Saved Ada blue' in state['text']:return Selection('done')
            field=next(r for r in rows if r['name']=='Name')
            if field['value']!='Ada':return Selection(next(c['id'] for c in obs['candidates'] if c.get('name')=='Name'),'Ada')
            team=next(r for r in rows if r['name']=='Team')
            if team['value']!='blue':return Selection(next(c['id'] for c in obs['candidates'] if c.get('name')=='Team' and c.get('value')=='blue'))
            return Selection(next(c['id'] for c in obs['candidates'] if c.get('name')=='Save'))
    result=await Controller(browser,Selector(),verifier=lambda obs:verify_conditions(obs,{'text':'Saved Ada blue'})).run('Enter Ada, select Blue and save')
    assert result['status']=='completed',result
    assert [e['operation'] for e in result['events']]==['TYPE_TEXT','SELECT','CLICK']


async def test_page_change_during_approval_prevents_action(browser):
    observed=await browser.observe();candidate=next(c for c in observed['candidates'] if c.get('name')=='Save')
    async def approve(action):
        await browser.page.evaluate("document.querySelector('#status').textContent='Changed while asking'")
        return True
    browser.authorize=approve
    result=await browser.execute(observed,candidate)
    assert result['status']=='stale'
    assert await browser.page.locator('#status').inner_text()=='Changed while asking'


async def test_denial_no_action_and_unapproved_origin(browser):
    async def deny(action):return False
    browser.authorize=deny
    observed=await browser.observe();candidate=next(c for c in observed['candidates'] if c.get('name')=='Save')
    assert (await browser.execute(observed,candidate))['status']=='denied'
    assert await browser.page.locator('#status').inner_text()=='Not saved'
    assert (await browser.open('https://other.example/'))['reason']=='origin_not_allowed'


async def test_detached_target_and_expired_observation(browser):
    observed=await browser.observe();candidate=next(c for c in observed['candidates'] if c.get('name')=='Save')
    await browser.page.locator('#save').evaluate('(el)=>el.remove()')
    assert (await browser.execute(observed,candidate))['status']=='stale'
    observed=await browser.observe();browser.observations[observed['revision']]['created_at']-=20
    assert (await browser.execute(observed,next(c for c in observed['candidates'] if c['id']=='wait')))['reason']=='observation_expired'


async def test_truncation_keeps_control_options(browser):
    await browser.page.evaluate("document.body.innerHTML=Array.from({length:180},(_,i)=>'<button>'+i+'</button>').join('')")
    observed=await browser.observe()
    assert observed['truncated'] and len(observed['candidates'])<=250
    assert {'done','blocked'} <= {c['id'] for c in observed['candidates']}


async def test_public_observation_and_approver_cannot_rewrite_action(browser):
    observed=await browser.observe();candidate=next(c for c in observed['candidates'] if c.get('name')=='Save')
    candidate['operation']='TYPE_TEXT'
    assert (await browser.execute(observed,candidate))['status']=='stale'
    observed=await browser.observe();candidate=next(c for c in observed['candidates'] if c.get('name')=='Save')
    async def approve(action):
        candidate['operation']='TYPE_TEXT'
        action['operation']='TYPE_TEXT'
        return True
    browser.authorize=approve
    assert (await browser.execute(observed,candidate))['status']=='completed'
    assert await browser.page.locator('#status').inner_text()=='Saved red'


async def test_human_reading_time_does_not_expire_unchanged_approved_target(browser):
    observed=await browser.observe();candidate=next(c for c in observed['candidates'] if c.get('name')=='Save')
    async def approve(action):
        browser.observations[observed['revision']]['created_at']-=20
        return True
    browser.authorize=approve
    assert (await browser.execute(observed,candidate))['status']=='completed'
    assert await browser.page.locator('#status').inner_text()=='Saved red'


async def test_requested_origin_needs_explicit_policy_and_grant(browser):
    target=browser.page.url;site=next(iter(browser.allowed_origins));seen=[]
    browser.allowed_origins=frozenset();browser.allow_requested_origins=True
    async def deny(action):seen.append(action);return False
    browser.authorize=deny
    assert (await browser.open(target))['status']=='denied' and not browser.allowed_origins
    async def allow(action):seen.append(action);return True
    browser.authorize=allow
    assert 'revision' in await browser.open(target)
    assert browser.allowed_origins=={site}
    assert all(row['allow_origin_for_conversation']==site for row in seen)


async def test_native_and_aria_checked_state_is_observed_without_hidden_controls(browser):
    await browser.page.set_content('''<label>Checked <input type="checkbox" checked></label>
      <label>Unchecked <input type="checkbox"></label><label>Mixed <input id="mixed" type="checkbox" checked></label>
      <label>Radio selected <input type="radio" name="team" checked></label>
      <label>Radio empty <input type="radio" name="team"></label>
      <button role="checkbox" aria-checked="mixed">ARIA mixed</button>
      <button role="checkbox" aria-checked="false">ARIA empty</button>
      <button role="radio" aria-checked="true">ARIA radio</button>
      <button role="checkbox">ARIA unknown</button>
      <button role="checkbox" aria-checked="true" aria-disabled="true">ARIA disabled</button>
      <label style="display:none">Hidden <input type="checkbox" checked></label>
      <label>Secret <input type="password" value="never-observe"></label>''')
    await browser.page.locator('#mixed').evaluate('(el)=>el.indeterminate=true')
    observed = await browser.observe()
    rows = {row['name']: row for row in observed['state']['elements']}
    assert rows['Checked']['checked'] is True and rows['Unchecked']['checked'] is False
    assert rows['Mixed']['checked'] is True and rows['Mixed']['indeterminate'] is True
    assert rows['Radio selected']['checked'] is True and rows['Radio empty']['checked'] is False
    assert rows['ARIA mixed']['checked'] == 'mixed' and rows['ARIA empty']['checked'] is False
    assert rows['ARIA radio']['checked'] is True and rows['ARIA unknown']['checked'] is None
    assert not {'Hidden', 'Secret', 'ARIA disabled'} & rows.keys()
    assert 'never-observe' not in str(observed)


@pytest.mark.parametrize('change', ['checked', 'indeterminate'])
async def test_checked_change_while_approving_rejects_stale_toggle(browser, change):
    await browser.page.set_content('<label>Choice <input id="choice" type="checkbox"></label>')
    observed = await browser.observe()
    candidate = next(c for c in observed['candidates'] if c.get('name') == 'Choice')
    async def approve(action):
        await browser.page.locator('#choice').evaluate('(el,property)=>el[property]=true', change)
        return True
    browser.authorize = approve
    assert (await browser.execute(observed, candidate))['status'] == 'stale'
    assert await browser.page.locator('#choice').evaluate('(el,property)=>el[property]', change)


async def test_aria_checkbox_and_radio_use_existing_observed_click_guard(browser):
    await browser.page.set_content('''<div role="checkbox" aria-label="Custom choice" aria-checked="false"
      onclick="this.setAttribute('aria-checked','true')" style="width:150px;height:30px">Choose</div>
      <div role="radio" aria-label="Custom radio" aria-checked="true" style="width:150px;height:30px">Radio</div>''')
    observed = await browser.observe()
    assert await verify_conditions(observed, {'fields': [{'name': 'Custom choice', 'checked': False}, {'name': 'Custom radio', 'checked': True}]})
    candidate = next(c for c in observed['candidates'] if c.get('name') == 'Custom choice')
    assert candidate['operation'] == 'CLICK'
    assert (await browser.execute(observed, candidate))['status'] == 'completed'
    assert await verify_conditions(await browser.observe(), {'field': {'name': 'Custom choice', 'checked': True}})


async def test_observed_checkbox_click_then_verification(browser):
    await browser.page.set_content('<label>Choice <input type="checkbox"></label>')
    observed = await browser.observe()
    candidate = next(c for c in observed['candidates'] if c.get('name') == 'Choice')
    assert await verify_conditions(observed, {'field': {'name': 'Choice', 'checked': False}})
    assert (await browser.execute(observed, candidate))['status'] == 'completed'
    current = await browser.observe()
    assert current['revision'] != observed['revision']
    assert await verify_conditions(current, {'field': {'name': 'Choice', 'checked': True}})
