from types import SimpleNamespace as NS
import pytest
from agent.tempo import create_agent, effectiveness, RedAlert, Pokemon
from altruagent import WAIT


def test_factory_needs_no_model_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert create_agent().policy is None


def test_type_chart():
    assert effectiveness("electric", {"types": ["ground"]}) == 0
    assert effectiveness("ice", {"types": ["dragon", "flying"]}) == 4
    assert effectiveness("ground", {"ability": "Levitate"}) == 0


def test_double_switch_one_reserve():
    slots = [{"slot": i, "options": [{"type":"switch","species":"a"},{"type":"pass"}]} for i in range(2)]
    state = NS(phase="moving", raw={"observation":{}}, legal_actions=[NS(input={"action":{"type":"doubles_turn","slots":slots}})])
    result = Pokemon().choose(state, None)
    assert result["slot_0"] == {"type":"switch","species":"a"}
    assert result["slot_1"] == {"type":"pass"}


def test_damaging_move_avoids_ally():
    slots = [{"slot":i, "options":[{"type":"move","move_id":"tackle","base_power":40,"targets":[-1,1]}]} for i in range(2)]
    state = NS(phase="moving", raw={"observation":{}}, legal_actions=[NS(input={"action":{"type":"doubles_turn","slots":slots}})])
    result = Pokemon().choose(state, None)
    assert result["slot_0"]["target"] == result["slot_1"]["target"] == 1


def ra(obs, **extra):
    return NS(raw={"phase":"playing","state_version":100,"observation":obs, **extra})


def test_deploy_once_and_wait_without_duplicate():
    agent = RedAlert()
    state = ra({"units":[{"id":1,"type":"mcv"}]})
    ctx = NS(game_config={})
    assert agent.choose(state, ctx)["orders"] == [{"cmd":"deploy","units":[1]}]
    assert agent.choose(state, ctx) is WAIT


def test_ready_building_and_power():
    state = ra({"buildings":[{"id":2,"type":"fact"}],
                "production":[{"item":"proc","ready":True}],
                "available_production":["powr"],
                "economy":{"cash":500}})
    result = RedAlert().choose(state, NS(game_config={}))
    assert {"cmd":"place","item":"proc"} in result["orders"]
    assert {"cmd":"build","item":"powr"} in result["orders"]


def test_no_model_on_unsupported_game():
    with pytest.raises(ValueError):
        create_agent().choose_action(None, NS(game_type="werewolf"))


def test_out_of_bounds_attack_is_not_sent():
    obs = {"buildings":[{"id":1,"type":"fact"},{"id":2,"type":"powr"},{"id":3,"type":"proc"},{"id":4,"type":"weap"},{"id":5,"type":"barr"}],
           "units":[{"id":i,"type":"e1","idle":True} for i in range(10,13)]}
    state = ra(obs, legal_actions={"enemy_base":[100,100]}, map={"bounds":[0,0,20,20]})
    assert RedAlert().choose(state, NS(game_config={})) is WAIT
