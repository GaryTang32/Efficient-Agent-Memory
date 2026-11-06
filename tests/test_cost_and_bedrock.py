from eam.cost import CostMeter, usage_cost
from eam.llm.bedrock import BedrockClient
from eam.llm.types import CachePlan, Request, Usage


def test_usage_cost(models):
    m = models["mock-strong"]  # 3 / 15 / 3.75 / 0.30 per 1M
    cost = usage_cost(Usage(1_000_000, 1_000_000, 1_000_000, 1_000_000), m)
    assert abs(cost - (3 + 15 + 0.30 + 3.75)) < 1e-9


def test_meter_hit_rate_and_tags(models):
    meter = CostMeter()
    meter.record("main", models["mock-strong"], Usage(100, 10, 900, 0), 5)
    meter.record("aux:summarize", models["mock-cheap"], Usage(50, 5, 0, 0), 5)
    assert abs(meter.cache_hit_rate() - 900 / 1050) < 1e-9
    assert set(meter.by_tag()) == {"main", "aux"}


class FakeBoto:
    def __init__(self):
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"role": "assistant", "content": [{"text": "hi"}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 12, "outputTokens": 3, "cacheReadInputTokens": 2000, "cacheWriteInputTokens": 7},
                "metrics": {"latencyMs": 321}}


def test_bedrock_client_shapes_request_and_parses_usage(models):
    fake = FakeBoto()
    client = BedrockClient(client=fake)
    resp = client.converse(Request(model=models["mock-strong"], system=[{"text": "sys"}],
                                   messages=[{"role": "user", "content": [{"text": "q"}]}],
                                   cache=CachePlan(system=True)))
    sent = fake.calls[0]
    assert sent["modelId"] == "mock-strong"
    assert sent["system"] == [{"text": "sys"}, {"cachePoint": {"type": "default"}}]
    assert "toolConfig" not in sent
    assert resp.usage == Usage(12, 3, 2000, 7)
    assert resp.latency_ms == 321 and resp.text == "hi"
