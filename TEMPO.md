# Tempo tournament setup

Tempo plays Pokémon VGC doubles draft and Red Alert through the official starter.
Its default `agent.agent:create_agent` loads a fixed game-specific strategy and
uses the starter's schema validation, fallback behavior, and match supervisor.
The strategy documents are in `agent/strategies/`.

## Install

Use Python 3.11 or newer:

```sh
git clone https://github.com/KayMayReplit/tempo-agent.git
cd tempo-agent
git checkout tempo-agent-setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

On Windows use `.venv\Scripts\activate` to activate the environment.
Choose **Self-hosted** in the tournament dashboard. Put the Official Agent Key
and your OpenAI key in the local `.env` using a private editor; never paste
either into chat, GitHub, screenshots, or logs. Required names:

- `ALTRUAGENT_CONTROL_URL`: `https://api.altruagent-game.com`
- `ALTRUAGENT_OFFICIAL_AGENT_KEY`: generated on the tournament dashboard
- `OPENAI_API_KEY`: your model provider credential
- `OPENAI_MODEL`: optional, defaults to the starter's `gpt-4o-mini`

Model usage is billed to your provider account, not the AWS tournament allowance.
Configure a provider-side spending limit. The starter's model-call cap is not a
dollar cap.

## Verify and run

```sh
python -m pytest -q
python -m agent --check-tournament
python -m agent --match
```

The connection check does not prove gameplay. If organizers permit Testing,
select **Mine (self-hosted)** and complete one match of each game. Stop the test
process before launching the tournament runner:

```sh
python -m agent --tournament
```

Register the agent for BOTH tournaments on the dashboard. Run only one copy.
Keep the machine powered, awake, and connected throughout the event. A GitHub
repository stores the code; it does not keep the agent running. A development
sandbox is not a guaranteed always-on host.

## Submission and disclosure

This branch is an implementation candidate, not an already-approved competitive
version. With organizer authorization, merge the setup into the default branch
and submit its full latest commit ID and model/configuration before the approved
lock. Do not assume a branch commit satisfies the default-branch submission rule.
Do not change strategy, code, model, or configuration during competitive play.
Retain the submitted version, configuration, and private audit logs for the
required preservation period. Do not commit credentials or private match logs.

The upstream SDK and example LLM adapters handle authentication, assignments,
structured action validation, and recovery. Tempo injects the selected Markdown
strategy into each model decision. Model history is not retained between calls;
the agent uses the current supplied observations and adapter records.
Pokémon uses a short shared model-attempt budget, further reduced by observed
clock/bank limits. Red Alert uses a six-second request budget and inherits the
starter's WAIT/backoff behavior on provider failure; no autonomous emergency
orders are generated during model outages.

HTTP timeouts are transport safeguards, not hard wall-clock guarantees.
The implementation and strategies require live testing; unit tests use fakes.
