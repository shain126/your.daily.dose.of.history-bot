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

ON_THIS_DAY_CHANCE = 0.2  # ~1 in 5 days


def _load():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _unused(topics, used):
    return [t for t in topics if t["slug"].lower() not in used]


def pick_topic(used):
    """Return (mode, topic_or_None).

    - mode == "on_this_day": no seed topic; Claude finds an event for today's date.
    - mode == "pillar": returns a seed topic dict from the curated pool.
    """
    if random.random() < ON_THIS_DAY_CHANCE:
        return "on_this_day", None

    data = _load()
    pool = _unused(data["topics"], used)
    if not pool:  # everything used -> allow repeats
        pool = data["topics"]
    return "pillar", random.choice(pool)


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
