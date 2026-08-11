"""Draft queue + used-topics tracker.

File-based so GitHub Actions can commit the state back to the repo between runs
(same idea as spanish-word-bot's used_words.txt).
"""
import json
import os
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.join(BASE_DIR, "drafts")
USED_TOPICS_FILE = os.path.join(BASE_DIR, "used_topics.txt")

# Account targets an Indian audience -> date the queue in IST.
IST = timezone(timedelta(hours=5, minutes=30))


def today_str():
    return datetime.now(IST).strftime("%Y-%m-%d")


def load_used_topics():
    if not os.path.exists(USED_TOPICS_FILE):
        return set()
    with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def save_used_topic(slug):
    with open(USED_TOPICS_FILE, "a", encoding="utf-8") as f:
        f.write(slug.strip().lower() + "\n")


def draft_path(date_str=None):
    return os.path.join(DRAFTS_DIR, f"{date_str or today_str()}.json")


def write_draft(data, date_str=None):
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = draft_path(date_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def read_draft(date_str=None):
    path = draft_path(date_str)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_draft_status(status, date_str=None, extra=None):
    data = read_draft(date_str)
    if data is None:
        return None
    data["status"] = status
    if extra:
        data.update(extra)
    write_draft(data, date_str)
    return data
