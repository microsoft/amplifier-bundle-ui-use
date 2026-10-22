"""An owned browser context with observed DOM actions, no model-authored code."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

OBSERVER = Path(__file__).with_name("dom.js").read_text()


def origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTP(S) URL without credentials")
    return f"{parsed.scheme}://{parsed.netloc}"


def observation_for(state, revision, *, allowed_origins=(), allow_web_navigation=True):
    candidates = []
    for el in state["elements"]:
        if el["tag"] == "select":
            for i, option in enumerate(el["options"]):
                candidates.append({"id": f'{el["id"]}:select:{i}', "operation": "SELECT", "target": el["id"],
                    "name": el["name"], "option": option["label"], "value": option["value"]})
        elif el["editable"]:
            candidates.append({"id": el["id"]+":type", "operation": "TYPE_TEXT", "target": el["id"], "name": el["name"]})
        else:
            if el["href"]:
                try: allowed = origin(el["href"]) in allowed_origins or allow_web_navigation
                except ValueError: allowed = False
                if not allowed: continue
            candidates.append({"id": el["id"]+":click", "operation": "CLICK", "target": el["id"], "name": el["name"]})
    truncated = state["truncated"] or len(candidates)>245
    candidates = candidates[:245] + [{"id": op.lower(), "operation": op} for op in ("SCROLL_DOWN", "SCROLL_UP", "WAIT", "DONE", "BLOCKED")]
    observed = {"revision": revision, "state": state, "candidates": candidates,
        "truncated": truncated, "created_at": time.monotonic()}
    return observed


class Browser:
    def __init__(self, *, allowed_origins, authorize, executable_path=None, launch_args=(), headless=True,
                 allow_requested_origins=False, allow_web_navigation=False):
        self.allowed_origins = frozenset(origin(x) for x in allowed_origins)
        self.allow_requested_origins = allow_requested_origins
        self.allow_web_navigation = allow_web_navigation
        self.authorize = authorize
        self.executable, self.launch_args, self.headless = executable_path, list(launch_args), headless
        self.driver = self.context = self.engine = self.page = None
        self.lock = asyncio.Lock()
        self.observations = {}

    async def _start(self):
        if self.page is not None: return
        from playwright.async_api import async_playwright
        self.driver = await async_playwright().start()
        try:
            self.engine = await self.driver.chromium.launch(headless=self.headless, executable_path=self.executable,
                args=self.launch_args)
            self.context = await self.engine.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=False)
            async def guard(route):
                request = route.request
                if request.is_navigation_request() and request.frame == self.page.main_frame:
                    try: allowed = origin(request.url) in self.allowed_origins or self.allow_web_navigation
                    except ValueError: allowed = False
                    if not allowed:
                        await route.abort(); return
                await route.continue_()
            await self.context.route("**/*", guard)
            self.page = await self.context.new_page()
            self.page.on("popup", lambda page: asyncio.create_task(page.close()))
            self.page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
        except BaseException:
            await self.close()
            raise

    async def open(self, url):
        requested_origin = origin(url)
        new_origin = requested_origin not in self.allowed_origins
        if new_origin and not self.allow_requested_origins:
            return {"status": "denied", "reason": "origin_not_allowed"}
        async with self.lock:
            action = {"operation": "OPEN", "url": url}
            if new_origin:
                action["allow_origin_for_conversation"] = requested_origin
            if await self.authorize(action) is not True:
                return {"status": "denied", "reason": "approval_denied"}
            if new_origin:
                self.allowed_origins = self.allowed_origins | {requested_origin}
            await self._start()
            await self.page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            return await self._observe()

    async def observe(self):
        async with self.lock:
            if self.page is None: raise RuntimeError("Open an explicitly allowed URL first")
            for attempt in range(3):
                try: return await self._observe()
                except Exception:
                    if attempt == 2: raise
                    await asyncio.sleep(.25)

    async def _observe(self):
        state = await self.page.evaluate(OBSERVER)
        revision = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        observed = observation_for(state,revision,allowed_origins=self.allowed_origins,allow_web_navigation=self.allow_web_navigation)
        self.observations[revision] = observed
        while len(self.observations)>16: self.observations.pop(next(iter(self.observations)))
        return copy.deepcopy(observed)

    async def execute(self, observation, candidate, text=None):
        async with self.lock:
            owned = self.observations.get(observation.get("revision"))
            if owned is None or candidate not in owned["candidates"]:
                return {"status": "stale", "reason": "unrecognized_observation"}
            # Public observations and an awaiting approver cannot rewrite the
            # operation whose provenance was just checked.
            candidate = copy.deepcopy(candidate)
            if candidate["operation"] in {"DONE", "BLOCKED"}:
                return {"status": "failed", "reason": "control_operation_not_executable"}
            if time.monotonic()-owned["created_at"] > 15:
                return {"status": "stale", "reason": "observation_expired"}
            if candidate["operation"] == "TYPE_TEXT" and (not isinstance(text, str) or len(text)>10000):
                return {"status": "failed", "reason": "invalid_text"}
            if await self.authorize(copy.deepcopy({**candidate, "text": text})) is not True:
                return {"status": "denied", "reason": "approval_denied"}
            # Approval can wait; reacquire evidence and compare after it returns.
            current = await self._observe()
            # An approver may take time to read. Exact fresh state comparison
            # remains mandatory; approval latency alone does not stale a target.
            if current["revision"] != owned["revision"]:
                return {"status": "stale", "reason": "observation_changed"}
            expected = json.dumps(current["state"], separators=(",", ":"), ensure_ascii=False)
            try:
                result = await self.page.evaluate("""({expected,candidate,text})=>{
                  const registry=window[Symbol.for('amplifier.ui.observer.v1')];
                  if(!registry||JSON.stringify(registry.observe())!==expected)return {status:'stale',reason:'dispatch_observation_changed'};
                  const op=candidate.operation,el=registry.nodes.get(candidate.target);
                  if(op==='CLICK'){if(!el||!el.isConnected)return {status:'stale'};el.click();}
                  else if(op==='TYPE_TEXT'){
                    if(!el||!el.isConnected)return {status:'stale'};el.focus();
                    if(el.isContentEditable)el.textContent=text;
                    else {const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,text);}
                    el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:text}));el.dispatchEvent(new Event('change',{bubbles:true}));
                  }else if(op==='SELECT'){el.value=candidate.value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}
                  else if(op==='SCROLL_DOWN'||op==='SCROLL_UP')window.scrollBy(0,(op==='SCROLL_DOWN'?1:-1)*innerHeight*.75);
                  else if(op!=='WAIT')return {status:'failed',reason:'unknown_operation'};
                  return {status:'completed'};
                }""", {"expected": expected, "candidate": candidate, "text": text})
                if candidate["operation"] in {"CLICK", "SELECT", "WAIT"}: await asyncio.sleep(.2)
                return result
            except asyncio.CancelledError: raise
            except Exception:
                # Navigation/context loss can occur after input; do not replay.
                return {"status": "unknown", "reason": "browser_execution_unconfirmed"}

    async def close(self):
        try:
            if self.context is not None: await self.context.close()
            if self.engine is not None: await self.engine.close()
        finally:
            if self.driver is not None: await self.driver.stop()
            self.driver = self.context = self.engine = self.page = None
