"""Daily Indian-heritage history bot for @yddoseOfHistory.

Two stages (each a separate GitHub Actions job):
  --mode generate : pick a topic, write a hook-optimized thread + pick an image,
                    save it to drafts/<date>.json (status "pending").
  --mode publish  : take today's draft and post the thread to X, then record it.

Modeled on spanish-word-bot: Claude is the primary content source, with a local
template fallback, and state is tracked in files committed back by CI.
"""
import argparse
import json
import os
import tempfile

from dotenv import load_dotenv

import claude_client
import draft_store
import image_provider
import topic_provider
import twitter_client

load_dotenv()

ATTRIB_PREFIX = "\U0001F4F7 "  # camera emoji


def _fallback_thread(topic):
    """Template thread used when the Claude CLI is unavailable."""
    tweets = [
        topic.get("fact", topic["title"]),
        f"{topic['title']} — one of the wonders of India's heritage.",
        "Follow @yddoseOfHistory for your daily dose of history \U0001F1EE\U0001F1F3",
    ]
    return {
        "slug": topic["slug"],
        "pillar": topic.get("pillar", "epics"),
        "image_query": topic.get("image_query", topic["title"]),
        "confidence": "fallback",
        "tweets": [t[:280] for t in tweets],
    }


def generate(dry_run=False):
    used = draft_store.load_used_topics()
    mode, topic = topic_provider.pick_topic(used)
    date_str = draft_store.today_str()

    try:
        thread = claude_client.generate_history_thread(mode, topic, date_str, used)
        print(f"[gen] Claude thread ok (mode={mode}, slug={thread['slug']})")
    except Exception as e:
        print(f"[gen] Claude failed ({e}); using local fallback")
        fb_topic = topic or topic_provider.get_next_unused_topic(used)
        thread = _fallback_thread(fb_topic)

    img = image_provider.fetch_image(thread["image_query"])
    if img:
        attrib = ATTRIB_PREFIX + img["attribution"]
        last = thread["tweets"][-1]
        if len(last) + 1 + len(attrib) <= 280:
            thread["tweets"][-1] = last + "\n" + attrib
        thread["image"] = {
            "url": img["url"],
            "attribution": img["attribution"],
            "alt": f"{thread.get('slug', '')} — {img.get('title', '')}"[:1000],
        }
    else:
        thread["image"] = None
        print("[gen] no suitable image found; draft is text-only")

    thread["status"] = "pending"
    thread["mode"] = mode
    thread["date"] = date_str

    if dry_run:
        print(json.dumps(thread, indent=2, ensure_ascii=False))
        return thread

    path = draft_store.write_draft(thread, date_str)
    print(f"[gen] draft written: {path}")
    return thread


def _auto_approve_enabled():
    return os.getenv("AUTO_APPROVE", "true").strip().lower() in ("1", "true", "yes")


def publish(dry_run=False):
    draft = draft_store.read_draft()
    if draft is None:
        print("[pub] no draft for today; nothing to publish")
        return

    status = draft.get("status", "pending")
    if status == "posted":
        print("[pub] already posted today; skipping")
        return
    if status == "skip":
        print("[pub] draft marked 'skip'; not posting")
        return
    if status == "pending" and not _auto_approve_enabled():
        print("[pub] draft still pending and AUTO_APPROVE=false; awaiting approval")
        return

    tweets = draft["tweets"]
    img = draft.get("image")
    image_path = None
    if img and img.get("url"):
        fd, tmp = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            image_provider.download_image(img["url"], tmp)
            image_path = tmp
        except Exception as e:
            print(f"[pub] image download failed (posting text-only): {e}")

    if dry_run:
        print(f"[pub] DRY RUN — would post {len(tweets)} tweets, image={bool(image_path)}")
        return

    try:
        ids = twitter_client.post_thread(
            tweets, image_path=image_path, image_alt=(img or {}).get("alt")
        )
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    draft_store.update_draft_status("posted", extra={"tweet_ids": ids})
    draft_store.save_used_topic(draft["slug"])
    print(f"[pub] posted thread: {ids}")


def main():
    p = argparse.ArgumentParser(description="Daily Indian-heritage history bot")
    p.add_argument("--mode", choices=["generate", "publish"], required=True)
    p.add_argument("--dry-run", action="store_true", help="print, don't write/post")
    args = p.parse_args()
    if args.mode == "generate":
        generate(dry_run=args.dry_run)
    else:
        publish(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
