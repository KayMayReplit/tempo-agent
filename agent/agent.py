"""Tempo: game-specific strategy atop the official validated LLM runtime."""

import time
from pathlib import Path

from examples.llm.providers import ProviderError, provider_from_env
from examples.llm_agent import LLMAgent

STRATEGIES = {
    "pokemon_vgc_doubles_draft": "pokemon.md",
    "red_alert": "red_alert.md",
}


class StrategyProvider:
    """Inject a fixed policy without changing the adapter's output schema."""

    def __init__(self, provider, strategy, clock=time.monotonic):
        self.provider = provider
        self.strategy = strategy
        self.model = provider.model
        self.clock = clock
        self.deadline = 0.0

    def complete_structured(self, messages, schema_name, schema, *, timeout=None):
        remaining = self.deadline - self.clock()
        if remaining < 0.5:
            raise ProviderError("Decision budget exhausted")
        limit = min(remaining, timeout) if timeout is not None else remaining
        policy = {
            "role": "system",
            "content": (
                "Apply this fixed strategy to the current decision only. "
                "The supplied JSON schema is authoritative. The Python runtime "
                "handles tools, waiting, authentication, retries and submission. "
                "Do not emit tool calls. No previous model conversation is retained; "
                "use only the current supplied state and records.\n\n" + self.strategy
            ),
        }
        return self.provider.complete_structured(
            [*messages[:1], policy, *messages[1:]], schema_name, schema, timeout=limit
        )


class TempoAgent:
    def __init__(self, provider, clock=time.monotonic):
        self.provider = provider
        self.clock = clock
        self.game_type = None
        self.delegate = None
        self.strategy_provider = None

    def choose_action(self, state, context):
        game = context.game_type
        if game not in STRATEGIES:
            raise ValueError("Tempo supports Pokémon doubles draft and Red Alert only")
        if self.game_type is not None and self.game_type != game:
            raise ValueError("A Tempo instance must not be shared across games")
        if self.delegate is None:
            self.game_type = game
            policy = (Path(__file__).parent / "strategies" / STRATEGIES[game]).read_text()
            self.strategy_provider = StrategyProvider(self.provider, policy, self.clock)
            self.delegate = LLMAgent(self.strategy_provider, clock=self.clock)
        # Include all model attempts in one budget. Leave time for transport.
        budget = 6.0 if game == "red_alert" else (8.0 if state.phase == "draft" else 12.0)
        observation = state.raw.get("observation") or {}
        clock_info = observation.get("clock") or {}
        for key in ("decision_seconds_left", "bank_seconds_left"):
            value = clock_info.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                budget = min(budget, max(0.0, value - 2.0))
        self.strategy_provider.deadline = self.clock() + budget
        return self.delegate.choose_action(state, context)

    def on_action_result(self, result, context):
        if self.delegate is not None:
            self.delegate.on_action_result(result, context)


def create_agent():
    return TempoAgent(provider_from_env())
