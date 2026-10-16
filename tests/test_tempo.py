from types import SimpleNamespace

import pytest

from agent.agent import StrategyProvider, TempoAgent
from examples.llm.providers import ProviderError


class Provider:
    model = "test-model"

    def complete_structured(self, messages, name, schema, **kwargs):
        self.call = (messages, name, schema, kwargs)
        return {"ok": True}


def test_strategy_preserves_schema_and_limits_timeout():
    base = Provider()
    provider = StrategyProvider(base, "fixed strategy", clock=lambda: 10)
    provider.deadline = 14
    schema = {"type": "object"}
    assert provider.complete_structured(
        [{"role": "system", "content": "base"}, {"role": "user", "content": "state"}],
        "choice", schema, timeout=20
    ) == {"ok": True}
    messages, _, passed_schema, kwargs = base.call
    assert passed_schema is schema
    assert "fixed strategy" in messages[1]["content"]
    assert messages[-1]["content"] == "state"
    assert kwargs["timeout"] == 4


def test_exhausted_budget_does_not_call_provider():
    base = Provider()
    provider = StrategyProvider(base, "policy", clock=lambda: 10)
    provider.deadline = 10
    with pytest.raises(ProviderError):
        provider.complete_structured([], "choice", {})
    assert not hasattr(base, "call")


@pytest.mark.parametrize("game,phase,expected", [
    ("pokemon_vgc_doubles_draft", "draft", 8),
    ("pokemon_vgc_doubles_draft", "moving", 12),
    ("red_alert", "playing", 6),
])
def test_policy_routing_and_budget(monkeypatch, game, phase, expected):
    class Delegate:
        def __init__(self, provider, **kwargs):
            self.provider = provider
        def choose_action(self, state, context):
            return self.provider.strategy
    monkeypatch.setattr("agent.agent.LLMAgent", Delegate)
    agent = TempoAgent(Provider(), clock=lambda: 100)
    text = agent.choose_action(
        SimpleNamespace(raw={"observation": {}}, phase=phase),
        SimpleNamespace(game_type=game),
    )
    assert ("Red Alert Agent" if game == "red_alert" else "Pokémon VGC") in text
    assert agent.strategy_provider.deadline == 100 + expected


def test_low_bank_reduces_budget_and_cross_game_reuse_is_rejected(monkeypatch):
    class Delegate:
        def __init__(self, *args, **kwargs): pass
        def choose_action(self, *args): return "action"
    monkeypatch.setattr("agent.agent.LLMAgent", Delegate)
    agent = TempoAgent(Provider(), clock=lambda: 100)
    state = SimpleNamespace(raw={"observation": {"clock": {"bank_seconds_left": 3}}}, phase="moving")
    agent.choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
    assert agent.strategy_provider.deadline == 101
    with pytest.raises(ValueError, match="shared"):
        agent.choose_action(state, SimpleNamespace(game_type="red_alert"))


def test_unknown_game_rejected():
    with pytest.raises(ValueError, match="supports"):
        TempoAgent(Provider()).choose_action(None, SimpleNamespace(game_type="unknown"))
