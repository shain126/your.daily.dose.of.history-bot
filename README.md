# @yddoseOfHistory — Daily Indian-Heritage History Bot

Posts a **daily thread with a striking image** about India's civilizational heritage to
[X / @yddoseOfHistory](https://x.com/yddoseOfHistory) — fully automatically, for free, on
GitHub Actions. By default it's an **image-first "showcase"** — one striking image + a short
curator caption ("attribute + teach", with IAST diacritics), styled after accounts that grow
in this niche (@hinduaesthetic, @IndiaArtHistory). Topics are weighted toward the most visual
pillars (art, temples); a longer hook-driven **thread** runs occasionally (~15%). Images are
pulled from Wikimedia Commons and posted via reply-chain when there's more than one tweet.

Inspired by [`spanish-word-bot`](https://github.com/shain126/spanish-word-bot).

---

## How it works

**One post a day**, produced by a generate→publish pair (generate runs ~2h earlier,
leaving a review window):

| Stage | Workflow | Time (IST) | What it does |
|-------|----------|------------|--------------|
| **Generate** | `.github/workflows/generate_draft.yml` | 06:00 | Pick a topic → Claude writes the thread → pick a Wikimedia image → save `drafts/<date>-<slot>.json` (status `pending`) and commit it. |
| **Publish** | `.github/workflows/publish.yml` | 08:00 | Read that draft → post the thread to X → mark it `posted`, record the topic. |

Both jobs run in the morning, so they share the same `morning` draft. One topic is
consumed per day; `used_topics.txt` prevents repeats. (To go back to twice daily, add
a second `cron` to each workflow — the morning/evening slot logic is still built in.)

**Content:** the *India's Sacred Wonders* signature series — five rotating pillars
(temples & architecture, ancient science, forgotten empires, epics & sacred geography,
sacred art), plus an occasional "On This Day in Indian history". Topics live in
[`topics.json`](topics.json).

**Accuracy first:** the Claude prompt hard-bans invented facts and any communal/sectarian
framing — the growth strategy is pride-in-heritage done accurately.

### Optional human review (you're on auto by default)
`AUTO_APPROVE=true` means the draft auto-posts even if you don't touch it. To review before
posting, in the ~2h window before each slot open `drafts/<today>-<slot>.json` in the GitHub
mobile app and:
- edit any tweet text or the `image.url`, then set `"status": "approved"`; or
- set `"status": "skip"` to cancel the day's post.

To require approval every day, set the repo variable `AUTO_APPROVE=false`.

---

## Setup (one time)

### 1. Push this folder to a GitHub repo
```bash
git init && git add . && git commit -m "Initial history bot"
git branch -M main
git remote add origin https://github.com/<you>/your.daily.dose.of.history.git
git push -u origin main
```

### 2. Add secrets — GitHub repo → **Settings → Secrets and variables → Actions → Secrets**
| Secret | Where to get it |
|--------|-----------------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Run `claude setup-token` locally (needs a Claude Pro/Max subscription). |
| `X_API_KEY`, `X_API_SECRET` | [developer.x.com](https://developer.x.com) → your app → Keys and tokens (Consumer Keys). |
| `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` | Same page → Access Token and Secret. **Must have Read *and* Write** permission. |

Optionally add a **Variable** (not secret) `AUTO_APPROVE` = `true` or `false`.

> **X app must be set to "Read and Write"** under User authentication settings, and you must
> regenerate the Access Token *after* enabling write, or posting will 403.

### 3. Enable the schedules
The workflows run on their cron automatically once on the default branch. Trigger a manual
test run any time from the **Actions** tab (**Run workflow** / `workflow_dispatch`).

---

## Local testing (optional)

Requires a **real Python 3.11+** install (the Windows Store `python` alias won't work).

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in the values

# 1) Image search only (no keys needed):
python image_provider.py "Konark Sun Temple"

# 2) Generate a draft and print it without writing/posting (uses Claude if installed,
#    else the local template fallback):
python bot.py --mode generate --dry-run

# 3) Real end-to-end: generate, then publish (this actually posts to X):
python bot.py --mode generate
python bot.py --mode publish
```

---

## ⚠️ Known risk to verify first: X API tier & media upload

Image upload uses the X **v1.1 `media/upload`** endpoint, which historically required
**Elevated/Basic** access. On some **Free**-tier apps it can be blocked, and threads consume
several of the ~500 posts/month write cap.

**Verify with one manual `publish` run before trusting the daily schedule.** If media upload
fails, either (a) post text-only (the bot already falls back to this if no image), or
(b) upgrade to the X API **Basic** tier.

---

## Files

```
bot.py             # entry point: --mode generate | publish  (+ --dry-run)
claude_client.py   # hook-optimized thread generation via the Claude Code CLI
topic_provider.py  # picks pillar / on-this-day topic; local fallback
image_provider.py  # Wikimedia Commons search + quality/licence ranking
twitter_client.py  # Tweepy: media upload + threaded reply chain
draft_store.py     # drafts/*.json queue + used_topics.txt tracker (IST-dated)
topics.json        # signature-series topic pool
drafts/            # <YYYY-MM-DD>-<slot>.json, two per day (committed by CI)
used_topics.txt    # posted-topic slugs, to avoid repeats (committed by CI)
```

## Extending to AI-generated images later
`image_provider.fetch_image(query)` returns a dict or `None`. To add a paid image API as a
fallback, generate an image when `fetch_image` returns `None` and return the same dict shape
— no caller changes needed.
