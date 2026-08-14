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


def _subject_line(mode, topic, date_str):
    if mode == "on_this_day":
        return (
            f"Pick a genuinely notable event from INDIAN history that happened on this "
            f"calendar date ({date_str[5:]} in MM-DD). Favour heritage, culture, science, "
            f"empires, temples, or art over modern-day politics."
        )
    return (
        f"Subject: {topic['title']} — {topic.get('fact', '')} "
        f"Pillar: {PILLAR_GUIDE.get(topic.get('pillar', ''), 'Indian heritage')}."
    )


def _build_showcase_prompt(mode, topic, date_str, used_slugs):
    """Image-first single-post format, styled after @hinduaesthetic / @IndiaArtHistory."""
    banned = ", ".join(sorted(used_slugs)) or "(none yet)"
    subject = _subject_line(mode, topic, date_str)

    return f"""You run @yddoseOfHistory, an X account in the style of curator accounts like @hinduaesthetic and @IndiaArtHistory: one striking image, one elegant caption. The image is the star; the words are a museum label with soul.

TASK: {subject}

Write an IMAGE-FIRST showcase post — a single beautiful image (found via image_query) with a short, authoritative caption.

HARD RULES:
- Every claim must be historically DEFENSIBLE. No invented facts, no fake quotes, real dates only. If unsure, choose a safer, well-documented angle.
- Celebrate the heritage with quiet pride and wonder. NEVER frame it as one community against another; no communal, sectarian, or political-grievance angle.
- Do NOT reuse any of these already-posted slugs: {banned}

CAPTION STYLE — "attribute + teach":
- Name the subject beautifully, then deliver ONE vivid, specific teaching detail: an iconographic meaning, a feat of engineering, a technique, or an arresting fact. (e.g. "Gaṅgā rides her makara — part crocodile, part fish, part elephant: land, water and sky, all served by the Mother.")
- Curator voice: elegant, confident, unhurried. No hype, no clickbait, no "you won't believe".
- Use IAST diacritics for Sanskrit names where natural (Kṛṣṇa, Viṣṇu, Śiva, Naṭarāja, gopuram).
- Where it fits, fold in a light provenance line like a museum label: title / era / place.
- No hashtags. At most one tasteful emoji, or none.

STRUCTURE:
- ONE tweet is ideal. Add a SECOND tweet only if there's a genuinely rich extra layer (deeper context or why it matters), and end that one with a soft "Follow @yddoseOfHistory for your daily dose of history".
- Every tweet MUST be <= {MAX_TWEET} characters.

Return ONLY valid minified JSON, nothing before or after, in exactly this shape:
{{"slug":"kebab-case-topic","pillar":"temples|science|empires|epics|art","image_query":"best Wikimedia Commons search term for a real, high-quality photo","confidence":"high|medium|low","tweets":["<caption>"]}}"""


def _build_thread_prompt(mode, topic, date_str, used_slugs):
    banned = ", ".join(sorted(used_slugs)) or "(none yet)"
    subject = (
        _subject_line(mode, topic, date_str)
        if mode == "on_this_day"
        else f"Write about: {topic['title']} — {topic.get('fact', '')} "
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


def generate_history_thread(mode, topic, date_str, used_slugs, fmt="showcase", timeout=180):
    if fmt == "thread":
        prompt = _build_thread_prompt(mode, topic, date_str, used_slugs)
    else:
        prompt = _build_showcase_prompt(mode, topic, date_str, used_slugs)

    binary = _claude_bin()
    cmd = [binary, "-p", prompt]
    model = os.getenv("CLAUDE_MODEL")
    if model:
        cmd += ["--model", model]
    print(f"[gen] invoking Claude CLI: {binary} (token set: {bool(os.getenv('CLAUDE_CODE_OAUTH_TOKEN'))})")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI exit {result.returncode}: {(result.stderr or result.stdout or '')[:500]}"
        )

    try:
        data = _extract_json(result.stdout.strip())
    except Exception as e:
        raise RuntimeError(
            f"Claude output not valid JSON ({e}); first 300 chars: {result.stdout.strip()[:300]!r}"
        ) from e

    tweets = [t.strip() for t in data.get("tweets", []) if t and t.strip()]
    if not (1 <= len(tweets) <= 5):
        raise ValueError(f"Expected 1-5 tweets, got {len(tweets)}")
    for i, t in enumerate(tweets):
        if len(t) > MAX_TWEET:
            raise ValueError(f"Tweet {i + 1} exceeds {MAX_TWEET} chars ({len(t)})")
    data["tweets"] = tweets

    seed = topic or {}
    data.setdefault("slug", seed.get("slug", "india-heritage"))
    data.setdefault("image_query", seed.get("image_query", data.get("slug")))
    data.setdefault("pillar", seed.get("pillar", "epics"))
    data.setdefault("confidence", "medium")
    data.setdefault("format", fmt)
    return data
