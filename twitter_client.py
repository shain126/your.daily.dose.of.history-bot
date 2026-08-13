"""Post a threaded tweet (with an optional image) to X via Tweepy.

Uses the same 4 OAuth 1.0a credentials as spanish-word-bot, but adds:
  - media upload (Tweepy API v1.1 media_upload), which the reference lacks, and
  - a reply chain (in_reply_to_tweet_id) to turn a list of tweets into a thread.
"""
import os
import time

import tweepy


class PostingBlocked(Exception):
    """X refused to post for a billing/permission/rate reason — not a code bug.

    The caller (bot.py) treats this as a clean skip (log + exit 0) rather than
    crashing the run with a traceback.
    """


def _cred(name):
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    # Log length only (never the value) to help diagnose bad/mismatched keys.
    print(f"[x] {name}: {len(val)} chars")
    return val


def _clients():
    api_key = _cred("X_API_KEY")
    api_secret = _cred("X_API_SECRET")
    access_token = _cred("X_ACCESS_TOKEN")
    access_secret = _cred("X_ACCESS_SECRET")

    # v2 client for creating tweets / threads.
    client = tweepy.Client(
        consumer_key=api_key, consumer_secret=api_secret,
        access_token=access_token, access_token_secret=access_secret,
    )
    # v1.1 API purely for media upload (create_tweet takes the resulting media_ids).
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api = tweepy.API(auth)
    return client, api


def _create_with_retry(client, retries=3, delay=10, **kwargs):
    for attempt in range(1, retries + 1):
        try:
            return client.create_tweet(**kwargs)
        except tweepy.errors.TwitterServerError as e:
            if attempt == retries:
                raise
            print(f"[x] server error (attempt {attempt}/{retries}), retrying in {delay}s: {e}")
            time.sleep(delay)
        except tweepy.errors.TooManyRequests as e:
            raise PostingBlocked("X API rate limit reached (429) — try again later.") from e
        except tweepy.errors.Forbidden as e:
            raise PostingBlocked(
                f"X refused the post (403) — app may be read-only, or this is a duplicate tweet: {e}"
            ) from e
        except tweepy.errors.HTTPException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 402:
                raise PostingBlocked(
                    "X API credits depleted (402 Payment Required) — add credits or upgrade "
                    "the tier in the X developer portal."
                ) from e
            raise


def post_thread(tweets, image_path=None, image_alt=None):
    client, api = _clients()

    try:
        me = client.get_me()
        print(f"[x] authenticated as @{me.data.username}")
    except tweepy.errors.Unauthorized as e:
        raise PostingBlocked(
            "X auth failed (401) — check the four X_* keys and that the app is set to Read+Write."
        ) from e
    except tweepy.errors.HTTPException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status == 402:
            raise PostingBlocked(
                "X API credits depleted (402) — add credits or upgrade the tier in the X portal."
            ) from e
        raise

    media_ids = None
    if image_path and os.path.exists(image_path):
        try:
            media = api.media_upload(filename=image_path)
            media_ids = [media.media_id_string]
            if image_alt:
                try:
                    api.create_media_metadata(media.media_id_string, image_alt[:1000])
                except Exception as e:
                    print(f"[x] alt-text set failed (non-fatal): {e}")
        except tweepy.errors.TweepyException as e:
            # Media upload can be blocked on some API tiers — fall back to text-only
            # rather than failing the whole post.
            print(f"[x] media upload unavailable, posting text-only: {e}")
            media_ids = None

    ids = []
    reply_to = None
    for i, text in enumerate(tweets):
        kwargs = {"text": text}
        if i == 0 and media_ids:
            kwargs["media_ids"] = media_ids
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to
        resp = _create_with_retry(client, **kwargs)
        tid = resp.data["id"]
        ids.append(tid)
        reply_to = tid
        print(f"[x] posted tweet {i + 1}/{len(tweets)}: {tid}")
        if i < len(tweets) - 1:
            time.sleep(2)
    return ids
