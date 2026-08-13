"""Pick the day's topic.

Mostly signature-series pillar topics from topics.json, occasionally an
"On This Day in Indian history" slot for freshness. Also provides a deterministic
fallback used when Claude is unavailable (mirrors spanish-word-bot's local provider).
"""
import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOPICS_FILE = os.path.join(BASE_DIR, "topics.json")

ON_THIS_DAY_CHANCE = 0.15  # occasional freshness slot

# Weight selection toward the most *visual* pillars — that's what the top Indian
# heritage accounts (@hinduaesthetic, @IndiaArtHistory) grow on. Art, temples and
# sacred sites photograph beautifully; science/empires lean on portraits with
# weaker imagery, so they appear less often.
PILLAR_WEIGHTS = {"art": 3, "temples": 3, "epics": 2, "empires": 1, "science": 1}


def _load():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _unused(topics, used):
    return [t for t in topics if t["slug"].lower() not in used]


def _weighted_pillar(pool):
    """Pick a pillar present in `pool`, biased by PILLAR_WEIGHTS."""
    pillars = sorted({t["pillar"] for t in pool})
    weights = [PILLAR_WEIGHTS.get(p, 1) for p in pillars]
    return random.choices(pillars, weights=weights, k=1)[0]


def pick_topic(used):
    """Return (mode, topic_or_None).

    - mode == "on_this_day": no seed topic; Claude finds an event for today's date.
    - mode == "pillar": returns a seed topic dict, biased toward visual pillars.
    """
    if random.random() < ON_THIS_DAY_CHANCE:
        return "on_this_day", None

    data = _load()
    pool = _unused(data["topics"], used)
    if not pool:  # everything used -> allow repeats
        pool = data["topics"]
    pillar = _weighted_pillar(pool)
    choices = [t for t in pool if t["pillar"] == pillar]
    return "pillar", random.choice(choices)


def get_next_unused_topic(used):
    """Fallback: first unused curated topic (carries a pre-written fact)."""
    data = _load()
    pool = _unused(data["topics"], used)
    if not pool:
        pool = data["topics"]
    return pool[0]


if __name__ == "__main__":
    mode, topic = pick_topic(set())
    print(mode, "->", (topic or {}).get("title", "on-this-day (Claude picks)"))
