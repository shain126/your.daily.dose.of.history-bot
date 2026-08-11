"""Generate a hook-optimized history thread via the Claude Code CLI.

Same mechanism as spanish-word-bot: shell out to `claude -p "<prompt>"` (auth via the
CLAUDE_CODE_OAUTH_TOKEN env var set by GitHub Actions) and parse the JSON it returns.
The prompt is the product here — it enforces the scroll-stopping hook, the accuracy
guardrail, and a strict JSON schema.
"""
import json
import os
import shutil
import subprocess

MAX_TWEET = 280

PILLAR_GUIDE = {
    "temples": "temples & sacred architecture",
    "science": "ancient Indian science & innovation",
    "empires": "forgotten Indian empires & kings",
    "epics": "epics & sacred geography",
    "art": "sacred art & manuscripts",
}


def _claude_bin():
    for name in ("claude", "claude.cmd", "claude.exe"):
        path = shutil.which(name)
        if path:
            return path
    return "claude"


def _build_prompt(mode, topic, date_str, used_slugs):
    banned = ", ".join(sorted(used_slugs)) or "(none yet)"
    if mode == "on_this_day":
        subject = (
            f"Pick a genuinely notable event from INDIAN history that happened on this "
            f"calendar date ({date_str[5:]} in MM-DD). Favour heritage, culture, science, "
            f"empires, temples, or art over modern-day politics."
        )
    else:
        subject = (
            f"Write about: {topic['title']} — {topic.get('fact', '')} "
            f"Pillar: {PILLAR_GUIDE.get(topic.get('pillar', ''), 'Indian heritage')}."
        )

    return f"""You write viral-but-accurate history threads for an X account about India's civilizational heritage (@yddoseOfHistory).

TASK: {subject}

HARD RULES:
- Every claim must be historically DEFENSIBLE. No invented facts, no fake quotes; real dates only. If unsure, choose a safer, well-documented angle.
- Celebrate the heritage with PRIDE, but NEVER frame it as one community against another. No communal, sectarian, or political-grievance framing. Keep it about wonder, ingenuity, and scale.
- Do NOT reuse any of these already-posted slugs: {banned}

HOOK RULES (most important):
- Tweet 1 is the hook. In the FIRST ~8 words, open a curiosity gap or set the stakes.
- BAN textbook openers like "On this day", "In 1565", or "Did you know".
- Good archetypes: "They carved this whole temple from the TOP down...", "This 1,600-year-old iron pillar still refuses to rust.", "The largest human gathering on Earth is visible from space."

STRUCTURE:
- 3 to 5 tweets. Tweet 1 = the hook (the payoff the image will show). Middle tweets = the story / how / why. Last tweet = a memorable kicker + a soft "Follow @yddoseOfHistory for your daily dose of history".
- Each tweet MUST be <= {MAX_TWEET} characters. At most 1-2 tasteful emojis total. No hashtags except optionally one at the very end.

Return ONLY valid minified JSON, nothing before or after, in exactly this shape:
{{"slug":"kebab-case-topic","pillar":"temples|science|empires|epics|art","image_query":"best Wikimedia Commons search term for a real photo","confidence":"high|medium|low","tweets":["...","...","..."]}}"""


def _extract_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in Claude output")
    return json.loads(text[start:end + 1])


def generate_history_thread(mode, topic, date_str, used_slugs, timeout=180):
    prompt = _build_prompt(mode, topic, date_str, used_slugs)
    cmd = [_claude_bin(), "-p", prompt]
    model = os.getenv("CLAUDE_MODEL")
    if model:
        cmd += ["--model", model]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI failed ({result.returncode}): {result.stderr or result.stdout}"
        )

    data = _extract_json(result.stdout.strip())

    tweets = [t.strip() for t in data.get("tweets", []) if t and t.strip()]
    if not (3 <= len(tweets) <= 5):
        raise ValueError(f"Expected 3-5 tweets, got {len(tweets)}")
    for i, t in enumerate(tweets):
        if len(t) > MAX_TWEET:
            raise ValueError(f"Tweet {i + 1} exceeds {MAX_TWEET} chars ({len(t)})")
    data["tweets"] = tweets

    seed = topic or {}
    data.setdefault("slug", seed.get("slug", "india-heritage"))
    data.setdefault("image_query", seed.get("image_query", data.get("slug")))
    data.setdefault("pillar", seed.get("pillar", "epics"))
    data.setdefault("confidence", "medium")
    return data
