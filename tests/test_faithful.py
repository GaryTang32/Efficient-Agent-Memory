"""Each paper-faithful technique uses the official strings and rules (see eam/techniques/third_party/NOTICE.md)."""

from eam.agent.loop import run_agent
from eam.bench.tasks import FAMILIES
from eam.llm.mock import MockLLM, final
from eam.techniques import build
from eam.techniques.third_party import agentdiet as AD
from eam.techniques.third_party import memagent as MA
from eam.techniques.turn_control import EXTENSION, REMINDER


def run(models, family, spec, aux_policy=None, seed=0):
    inst = FAMILIES[family](seed)
    llm = MockLLM(inst.oracle()) if aux_policy is None else MockLLM(inst.oracle(), aux_policy=aux_policy)
    res = run_agent(inst.prompt, llm=llm, model=models["mock-strong"], aux_model=models["mock-cheap"], models=models,
                    env_tools=inst.tools, techniques=build(spec), resources=inst.resources, max_steps=inst.max_steps)
    return inst, res, llm


def user_texts(res):
    return [b["text"] for m in res.messages if m["role"] == "user" for b in m["content"] if "text" in b]


def test_turn_control_fixed_reminds_and_stops(models):
    _, res, _ = run(models, "inventory_ops", "turn_control:limit=6")
    texts = user_texts(res)
    assert REMINDER.format(left=6) in texts and REMINDER.format(left=1) in texts
    assert res.steps <= 7 and not res.finished
    assert any(e["kind"] == "stopped" and e["reason"] == "turn_limit" for e in res.events)


def test_turn_control_dynamic_grants_one_extension(models):
    inst, res, _ = run(models, "inventory_ops", "turn_control:limit=6,mode=dynamic,extension=40")
    assert EXTENSION.format(extra=40) in user_texts(res)
    assert res.finished and inst.check(res.answer)


def test_agentdiet_uses_official_prompt_window_and_rule(models):
    seen = []

    def reflector(req):
        seen.append(req)
        return final("<think>kept the key facts</think>\n<result>... (unrelated filler) In 2023, X reported revenue of $1 million.</result>")

    _, res, _ = run(models, "needle_research", "agentdiet", aux_policy=reflector)
    first = seen[0]
    assert first.system[0]["text"] == AD.SYS_PROMPT and first.temperature == 0.0 and first.stop == ["</step>"]
    prompt = first.messages[0]["content"][0]["text"]
    # step 0 (the short company list) is below θ=500 tokens and skipped; step 1 is the first target
    assert prompt.endswith("Now, compress the step 1.") and first.prefill == AD.PREFILL.format(idx=1)
    assert prompt.count('<step id="') == 4  # context = steps idx-b .. idx+a = 0, 1, 2, 3
    reduced = [e for e in res.events if e["kind"] == "agentdiet_reduced"]
    assert reduced and [e["step"] for e in reduced] == list(range(1, 1 + len(reduced)))
    compressed = [b["text"] for m in res.messages if m["role"] == "assistant" for b in m["content"]
                  if b.get("text", "").startswith(AD.COMPRESSED_MARKER)]
    assert len(compressed) == len(reduced)


def test_agentdiet_keeps_step_when_saving_is_too_small(models):
    def lazy(req):  # returns the target step unchanged → fails the ≥400 tokens / <80% rule
        text = req.messages[0]["content"][0]["text"]
        idx = text.rsplit("compress the step ", 1)[1].rstrip(".")
        start = text.index(f'<step id="{idx}">') + len(f'<step id="{idx}">')
        return final(text[start:text.index("</step>", start)])

    _, res, _ = run(models, "needle_research", "agentdiet", aux_policy=lazy)
    assert any(e["kind"] == "agentdiet_kept" for e in res.events)
    assert not any(e["kind"] == "agentdiet_reduced" for e in res.events)


def test_obs_mask_keeps_last_two_steps_raw(models):
    _, res, _ = run(models, "needle_research", "obs_mask")
    results = [b["toolResult"]["content"][0]["text"] for m in res.messages for b in m["content"] if "toolResult" in b]
    assert results[-1] != "Environment Observation Ommited" and results[-2] != "Environment Observation Ommited"
    assert results.count("Environment Observation Ommited") >= 5


def test_memagent_uses_official_templates(models):
    seen = []

    def mem(req):
        seen.append(req.messages[0]["content"][0]["text"])
        return final("The project codename is KESTREL-7. The launch date was moved to May 3.")

    run(models, "long_document_qa", "memagent", aux_policy=mem)
    assert seen[0].startswith(MA.TEMPLATE.split("{")[0]) and "<memory>\nNo previous memory\n</memory>" in seen[0]
    assert seen[-1].startswith(MA.TEMPLATE_FINAL.split("{")[0])
