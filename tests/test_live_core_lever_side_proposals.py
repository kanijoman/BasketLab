"""A lever whose points are lost in OUR DEFENCE asks for defence, in the words and in the substitutions (feedback of the 0.5.2, on the diagnosis of #586).

«¿Las propuestas de cambio en la probabilidad de victoria tienen en cuenta si es defensa o ataque? Si el acierto es en el tiro del rival hay que meter defensa, no ataque.»
They did not: the engine said «Es sobre todo la defensa» and then proposed the attack's action and brought in the best attackers in the factor. In Cultural–Melilla
(2536133, a real recording) the win probability fell with the lever «balón» on the defence (Melilla lost few balls) and the alert said «asegurar el balón» and proposed
players who lose fewer balls. Now the defence side has its own action and the substitution looks for the defender's profile: steals for the turnovers we force,
defensive rebounds for the rival's offensive ones, blocks and steals for the rival's shooting; the free throws of the rival have no individual metric (no substitution).
"""
import gzip
from pathlib import Path

import pytest

from src.live_core.session import LiveSession

RECORDINGS = Path(__file__).parent / "recordings"


def play(code):
    """Every alert and every lever row of the win probability card of a real recording, followed as the app does (a poll every 30 s of the recording)."""
    session = LiveSession((RECORDINGS / f"{code}.package.json").read_text(encoding="utf-8"))
    info = session.load_recording(gzip.open(RECORDINGS / f"{code}.rec.json.gz", "rt", encoding="utf-8").read())
    alerts, cards, t = [], [], 0.0
    while t <= info["duration"]:
        out = session.play(t)["output"]
        if out:
            alerts += out["alerts"]
            cards += [(out["snapshot"]["elapsed"], lv) for lv in out["analysis"].get("win_levers") or []]
        t += 30
    return alerts, cards


@pytest.fixture(scope="module")
def cultural_melilla():
    return play("2536133")


def subs(alert_or_lever):
    return [p["message"] for p in alert_or_lever.get("proposal") or [] if p.get("type") == "sub"]


def test_the_win_probability_falling_with_the_turnovers_on_our_defence_asks_for_pressure_not_ball_security_regression(cultural_melilla):
    alerts, _ = cultural_melilla
    [flip] = [a for a in alerts if a["id"] == "win_flip" and a["evidence"]["lever"] == "tov"]
    assert flip["evidence"]["lever_side"] == "defence"
    assert "asegurar el balón" not in flip["message"] and "forzar pérdidas" in flip["message"]
    assert subs(flip) and all("mejora los robos" in m for m in subs(flip))


def test_the_offensive_rebounds_of_the_rival_ask_for_the_defensive_rebound_regression(cultural_melilla):
    alerts, _ = cultural_melilla
    [lever] = [a for a in alerts if a["id"] == "four_factors_lever" and a["evidence"]["lever"] == "orb" and a["evidence"].get("side") == "defence"]
    assert "Reforzar el rebote ofensivo" not in lever["message"] and "rebote defensivo" in lever["message"]
    assert subs(lever) and all("mejora el rebote defensivo" in m for m in subs(lever))


def test_the_card_of_the_win_probability_proposes_defenders_for_a_defence_lever_and_attackers_for_an_attack_one(cultural_melilla):
    _, cards = cultural_melilla
    defence = [lv for _, lv in cards if lv["id"] in ("tov", "orb") and lv.get("side") == "defence" and subs(lv)]
    assert defence and all(("robos" in m) if lv["id"] == "tov" else ("rebote defensivo" in m) for lv in defence for m in subs(lv))
    rival_free_throws = [lv for _, lv in cards if lv["id"] == "ftr" and lv.get("side") == "defence"]
    assert rival_free_throws and not any(subs(lv) for lv in rival_free_throws)       # no individual metric says who fouls less on defence
    attack = [lv for _, lv in cards if lv["id"] == "tov" and lv.get("side") == "attack" and subs(lv)]
    assert all("mejora las pérdidas" in m for lv in attack for m in subs(lv))         # our own turnovers: who loses fewer balls, as before
