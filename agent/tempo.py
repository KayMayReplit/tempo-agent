"""Local, deterministic strategies. No model provider or inference credentials."""
from itertools import combinations, product
import re

from altruagent import WAIT
from examples.smoke_agent import choose_action as legal_fallback


def norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


# Attack type -> super-effective, resisted, immune defender types.
CHART = {
    "normal": ("", "rock steel", "ghost"),
    "fire": ("grass ice bug steel", "fire water rock dragon", ""),
    "water": ("fire ground rock", "water grass dragon", ""),
    "electric": ("water flying", "electric grass dragon", "ground"),
    "grass": ("water ground rock", "fire grass poison flying bug dragon steel", ""),
    "ice": ("grass ground flying dragon", "fire water ice steel", ""),
    "fighting": ("normal ice rock dark steel", "poison flying psychic bug fairy", "ghost"),
    "poison": ("grass fairy", "poison ground rock ghost", "steel"),
    "ground": ("fire electric poison rock steel", "grass bug", "flying"),
    "flying": ("grass fighting bug", "electric rock steel", ""),
    "psychic": ("fighting poison", "psychic steel", "dark"),
    "bug": ("grass psychic dark", "fire fighting poison flying ghost steel fairy", ""),
    "rock": ("fire ice flying bug", "fighting ground steel", ""),
    "ghost": ("psychic ghost", "dark", "normal"),
    "dragon": ("dragon", "steel", "fairy"),
    "dark": ("psychic ghost", "fighting dark fairy", ""),
    "steel": ("ice rock fairy", "fire water electric steel", ""),
    "fairy": ("fighting dragon dark", "fire poison steel", ""),
}


def effectiveness(kind, target):
    strong, weak, immune = (s.split() for s in CHART.get(norm(kind), ("", "", "")))
    value = 1.
    for t in target.get("types", []):
        t = norm(t)
        value *= 0 if t in immune else 2 if t in strong else .5 if t in weak else 1
    ability = norm(target.get("ability", ""))
    if (norm(kind), ability) in {
        ("ground", "levitate"), ("fire", "flashfire"), ("water", "waterabsorb"),
        ("water", "stormdrain"), ("electric", "voltabsorb"), ("electric", "lightningrod"),
    }:
        return 0.
    return value


def members(value):
    if isinstance(value, dict):
        return list(value.values())
    return value if isinstance(value, list) else []


def quality(p):
    stats = p.get("base_stats") or {}
    score = sum(v for v in stats.values() if isinstance(v, (int, float))) / 30
    moves = {norm(m.get("id", "") if isinstance(m, dict) else m) for m in p.get("moves", [])}
    score += 12 * bool(moves & {"tailwind", "trickroom"})
    score += 7 * bool(moves & {"fakeout", "followme", "ragepowder"})
    score += 5 * ("protect" in moves)
    score += 6 * (norm(p.get("ability", "")) == "intimidate")
    return score


class Pokemon:
    def choose(self, state, context):
        obs = state.raw.get("observation") or {}
        actions = state.legal_actions
        if state.phase == "draft":
            cards = {c["card_id"]: c for c in obs.get("available_cards", [])}
            return max(actions, key=lambda a: quality(cards.get(a.action_id.split(":", 1)[-1], {})))
        template = actions[0].input.get("action", {}) if actions else {}
        if state.phase == "team_preview":
            roster = template.get("roster", [])
            details = {norm(p.get("species")): p for p in obs.get("your_roster", [])}
            def team_score(team):
                types = [norm(t) for s in team for t in details.get(norm(s), {}).get("types", [])]
                return sum(quality(details.get(norm(s), {})) for s in team) + 3 * len(set(types))
            four = max(combinations(roster, 4), key=team_score)
            four = sorted(four, key=lambda s: quality(details.get(norm(s), {})), reverse=True)
            return {"type": "select_lineup", "bring": four, "leads": four[:2]}
        if template.get("type") != "doubles_turn":
            return legal_fallback(state, context)
        enemies = members(obs.get("opponent_active_pokemon"))
        slots = sorted(template["slots"], key=lambda s: s["slot"])
        choices = []
        for slot in slots:
            active = slot.get("active") or {}
            if not isinstance(active, dict):
                active = {}
            board = obs.get("active_pokemon") or []
            if isinstance(board, list) and len(board) > slot["slot"] and isinstance(board[slot["slot"]], dict):
                active = {**active, **board[slot["slot"]]}
            available = obs.get("available_moves") or []
            move_details = {}
            if isinstance(available, list) and len(available) > slot["slot"]:
                move_details = {norm(m.get("id", m.get("move_id"))): m
                                for m in members(available[slot["slot"]]) if isinstance(m, dict)}
            candidates = []
            for opt in slot["options"]:
                opt = {**move_details.get(norm(opt.get("move_id")), {}), **opt}
                kind = opt["type"]
                if kind == "pass":
                    candidates.append((-100., {"type": "pass"}))
                elif kind == "switch":
                    candidates.append((5., {"type": "switch", "species": opt["species"]}))
                elif kind == "move":
                    move = norm(opt["move_id"])
                    targets = opt.get("targets") or [None]
                    for target in targets:
                        action = {"type": "move", "move_id": opt["move_id"]}
                        if target is not None:
                            action["target"] = target
                        defender = enemies[target - 1] if target in (1, 2) and len(enemies) >= target else {}
                        defender = defender or {}
                        category = norm(opt.get("category", ""))
                        bp = opt.get("base_power") or (50 if category in {"physical", "special"} else 0)
                        accuracy = opt.get("accuracy", 1)
                        accuracy = 1 if accuracy is True or accuracy is None else float(accuracy)
                        if accuracy > 1:
                            accuracy /= 100
                        mt = opt.get("move_type", opt.get("type_name", ""))
                        stab = 1.5 if norm(mt) in [norm(t) for t in active.get("types", [])] else 1.
                        score = bp * accuracy * stab * effectiveness(mt, defender)
                        if target in (-1, -2):
                            score = -1000 if bp else 4
                        if target in (None, 0) and bp:
                            score *= .75  # conservative spread estimate, not exact damage
                            if move in {"earthquake", "surf", "discharge", "explosion", "selfdestruct"}:
                                score -= 150  # avoid uncoordinated friendly fire
                        if move in {"protect", "detect"}:
                            score = 2  # no repeated-protect loops
                        if move == "fakeout":
                            score = 1  # entry timing is not reliably exposed here
                        if move == "tailwind":
                            conditions = norm(str(obs.get("side_conditions", {})))
                            score = 1 if "tailwind" in conditions else 75
                        if move in {"spore", "sleeppowder"}:
                            score = 55 if not defender.get("status") and "grass" not in [norm(t) for t in defender.get("types", [])] else 0
                        if move in {"recover", "roost", "slackoff", "softboiled"}:
                            score = 65 if active.get("current_hp_fraction", 1) < .45 else 0
                        # Keep all legal choices; legality wins over a tactical preference.
                        candidates.append((score, action))
            choices.append(candidates)
        best = None
        for left, right in product(*choices):
            a, b = left[1], right[1]
            if a["type"] == b["type"] == "switch" and a["species"] == b["species"]:
                continue
            if a["type"] == b["type"] == "pass":
                continue
            score = left[0] + right[0]
            if best is None or score > best[0]:
                best = (score, a, b)
        if best is None:
            return legal_fallback(state, context)
        return {"type": "doubles_turn", "slot_0": best[1], "slot_1": best[2]}


class RedAlert:
    def __init__(self):
        self.sent = {}

    def choose(self, state, context):
        raw = state.raw
        obs = raw.get("observation") or {}
        if raw.get("phase") not in (None, "playing") or not obs:
            return WAIT
        tick = raw.get("state_version", 0)
        hints = raw.get("legal_actions") or {}
        units = [u for u in obs.get("units", []) if not u.get("wreck")]
        buildings = obs.get("buildings", [])
        types = {b["type"] for b in buildings}
        production = obs.get("production", [])
        queued = {p["item"] for p in production}
        available = {x if isinstance(x, str) else x.get("item") for x in obs.get("available_production", [])}
        econ = obs.get("economy") or {}
        funds = econ.get("cash", 0) + econ.get("ore", 0)
        orders = []
        limits = raw.get("limits") or {}
        max_orders = min(20, limits.get("max_orders_per_batch", 20))
        max_units = min(50, limits.get("max_units_per_order", 50))
        rules = (context.game_config or {}).get("rules", {})
        facts = {**rules.get("buildings", {}), **rules.get("units", {})}
        def add(order, cooldown=125):
            key = repr(order)
            if tick - self.sent.get(key, -100000) < cooldown or len(orders) >= max_orders:
                return
            self.sent[key] = tick
            orders.append(order)
        def buy(cmd, item, fallback_cost):
            nonlocal funds
            cost = facts.get(item, {}).get("cost", fallback_cost)
            if item in available and item not in queued and funds >= cost:
                before = len(orders)
                add({"cmd": cmd, "item": item}, 250)
                if len(orders) > before:
                    funds -= cost
                    queued.add(item)
        for p in production:
            if p.get("ready"):
                add({"cmd": "place", "item": p["item"]}, 50)
        if "fact" not in types:
            mcvs = [u["id"] for u in units if u.get("type") == "mcv"]
            if mcvs:
                add({"cmd": "deploy", "units": mcvs[:1]}, 125)
            return {"type": "orders", "orders": orders} if orders else WAIT
        provided, drained = econ.get("power_provided", 0), econ.get("power_drained", 0)
        if "powr" not in types or provided - drained < 25:
            buy("build", "powr", 300)
        if not types & {"tent", "barr"}:
            buy("build", "tent" if "tent" in available else "barr", 500)
        if "proc" not in types:
            buy("build", "proc", 1400)
        elif "weap" not in types:
            buy("build", "weap", 2000)
        harvesters = [u for u in units if u.get("type") == "harv"]
        if "proc" in types and not harvesters:
            buy("train", "harv", 1100)
        for u in harvesters:
            if u.get("idle"):
                add({"cmd": "harvest", "units": [u["id"]]}, 125)
        # Preserve funds for the opening refinery; avoid infantry spending stalls.
        if "proc" in types:
            for name, cost in (("3tnk", 950), ("2tnk", 800), ("1tnk", 700), ("ftrk", 600), ("apc", 850)):
                if name in available:
                    buy("train", name, cost)
                    break
            if funds > 500:
                buy("train", "e1", 100)
        elif funds > 1800:
            buy("train", "e1", 100)
        for b in buildings:
            if b.get("hp", 100) < 65 and not b.get("repairing") and funds > 300:
                add({"cmd": "repair", "building": b["id"], "on": True}, 250)
                break
        combat = [u for u in units if u.get("type") not in {"mcv", "harv", "medi", "e6", "mech"}]
        base = obs.get("base_center")
        if isinstance(base, dict):
            base = [base.get("x"), base.get("y")]
        enemies = [e for e in obs.get("visible_enemies", []) if not e.get("wreck")]
        threats = [e for e in enemies if isinstance(base, list) and len(base) == 2
                   and all(isinstance(x, (int, float)) for x in base)
                   and abs(e["x"]-base[0])+abs(e["y"]-base[1]) < 16]
        destination = [threats[0]["x"], threats[0]["y"]] if threats else hints.get("enemy_base")
        army = combat if threats else [u for u in combat if u.get("idle")]
        bounds = (raw.get("map") or {}).get("bounds")
        in_bounds = (isinstance(destination, list) and len(destination) == 2 and
                     isinstance(bounds, list) and len(bounds) == 4 and
                     bounds[0] <= destination[0] < bounds[0]+bounds[2] and
                     bounds[1] <= destination[1] < bounds[1]+bounds[3])
        if army and in_bounds and (threats or len(army) >= 3):
            add({"cmd": "attack_move", "units": [u["id"] for u in army[:max_units]], "to": destination}, 250)
        # Bounded memory: commands older than one minute are irrelevant to cooldowns.
        self.sent = {k: t for k, t in self.sent.items() if tick-t < 1500}
        return {"type": "orders", "orders": orders} if orders else WAIT


class TempoAgent:
    def __init__(self):
        self.game_type = None
        self.policy = None

    def choose_action(self, state, context):
        if self.game_type is not None and context.game_type != self.game_type:
            raise ValueError("Do not share agent instances between games")
        if self.policy is None:
            policies = {"pokemon_vgc_doubles_draft": Pokemon, "red_alert": RedAlert}
            if context.game_type not in policies:
                raise ValueError("Unsupported game")
            self.game_type = context.game_type
            self.policy = policies[self.game_type]()
        return self.policy.choose(state, context)


def create_agent():
    return TempoAgent()
