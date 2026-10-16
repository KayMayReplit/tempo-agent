# Tempo: no-model tournament agent

Tempo runs local, deterministic strategies for Pokémon doubles draft and Red
Alert. It needs only your Official Agent Key: no OpenAI/Anthropic account, model
API key, or inference charges. The computer running it still needs to stay awake
and online; GitHub does not run the agent.

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

On Windows activate with `.venv\Scripts\activate`.
In a private editor, set `ALTRUAGENT_OFFICIAL_AGENT_KEY` in `.env` and keep
`ALTRUAGENT_CONTROL_URL=https://api.altruagent-game.com`.
Never put credentials in chat, commits, screenshots, or logs.
Choose **Self-hosted** on the dashboard.

## Check and play

```sh
python -m pytest -q
python -m agent --check-tournament --agent agent.tempo
python -m agent --match --agent agent.tempo
```

If organizers allow Testing, choose **Mine (self-hosted)** on the dashboard.
Complete a match of each game before competitive play.
Stop the test runner before starting the tournament runner:

```sh
python -m agent --tournament --agent agent.tempo
```

Register on BOTH tournaments. Keep one runner process active.
Always include `--agent agent.tempo`: without it the upstream placeholder runs
and cannot finish either game. The LLM examples remain upstream reference code;
do not select `examples.llm_agent` for the no-key version.

## Implemented strategy and limitations

Pokémon ranks fixed draft sets by supplied stats and support capabilities,
chooses a four-Pokémon lineup with type diversity, and scores legal action pairs
using move power, accuracy, STAB, type effectiveness and some known ability
immunities. It rejects conflicting switches and avoids accidental ally damage.
It handles forced replacements and targetless moves. It is a heuristic, not a
damage simulator: it does not model full speed order, exact damage rolls,
opponent predictions, or all abilities and status interactions. Missing metadata
reduces tactical quality. It does not implement the entire Markdown strategy.

Red Alert deploys the MCV, builds power/barracks/refinery/factory, places completed
buildings, restores harvesting, trains affordable units, repairs damaged
structures, and sends combat groups toward nearby threats or the supplied enemy
spawn. It uses bounded order batches and cooldowns to avoid rapid duplicate
commands. It is a baseline macro policy, not an expert RTS player: it does not
implement full scouting, expansion, technology progression, spatial pathfinding,
or the entire Markdown strategy. A blocked MCV or crowded base may need policy
improvements discovered in testing; humans must not intervene during a match
without organizer authorization.

Only player observations and authorized map hints are used. Each match gets a
fresh policy instance. The Markdown files are retained as design references;
the deterministic agent does not execute them or send them to a model.

## Submission

The setup PR remains a candidate. With organizer approval, merge it into the
default branch and submit that branch's full latest commit ID and configuration.
Do not assume the setup branch alone meets the default-branch submission rule.
Do not change the code or configuration during competitive play. Preserve
the submitted version, configuration and private audit records as required by
the tournament. No live match result is implied by passing unit tests.
