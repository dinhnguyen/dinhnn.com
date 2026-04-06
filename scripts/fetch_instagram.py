#!/usr/bin/env python3
"""
Fetch Instagram photos by crawling a public profile via instaloader.
Supports carousel (multi-image) posts.

Required env vars:
  INSTAGRAM_USERNAME - Instagram username (public profile)

Optional env vars:
  INSTAGRAM_MAX_POSTS - Max posts to fetch per run (default: 24)
  INSTAGRAM_SESSION_FILE - Path to instaloader session file for avoiding rate limits
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import instaloader

CONTENT_DIR = Path("content/instagram")
CURSOR_FILE = Path("data/instagram_cursor.json")
MAX_POSTS = int(os.environ.get("INSTAGRAM_MAX_POSTS", "24"))


def load_state():
    if CURSOR_FILE.exists():
        return json.loads(CURSOR_FILE.read_text())
    return {"fetched_ids": [], "fetched_count": 0, "last_fetch": None}


def save_state(state):
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_FILE.write_text(json.dumps(state, indent=2))


def sanitize_caption(caption):
    if not caption:
        return ""
    return re.sub(r"[\n\r\t]+", " ", caption).replace('"', "'").strip()


def post_exists(shortcode):
    return (CONTENT_DIR / shortcode).exists()


def download_node_image(node_url, dest_path):
    import urllib.request
    urllib.request.urlretrieve(node_url, dest_path)


def create_page_bundle(post):
    shortcode = post.shortcode
    if post_exists(shortcode):
        print(f"  skip {shortcode} (already exists)")
        return False

    if post.is_video and post.typename != "GraphSidecar":
        print(f"  skip {shortcode} (video)")
        return False

    post_dir = CONTENT_DIR / shortcode
    post_dir.mkdir(parents=True, exist_ok=True)

    caption = sanitize_caption(post.caption or "")
    date_str = post.date_utc.replace(tzinfo=timezone.utc).isoformat()
    permalink = f"https://www.instagram.com/p/{shortcode}/"

    # Collect images
    images = []
    if post.typename == "GraphSidecar":
        for i, node in enumerate(post.get_sidecar_nodes()):
            if node.is_video:
                continue
            filename = f"photo_{i+1}.jpg"
            dest = post_dir / filename
            print(f"  downloading {shortcode} [{i+1}]...")
            try:
                L.download_pic(filename=str(post_dir / f"photo_{i+1}"), url=node.display_url, mtime=post.date_utc)
                # rename if instaloader added extension
                for f in post_dir.glob(f"photo_{i+1}.*"):
                    if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.name != filename:
                        f.rename(dest)
                    elif f.name == filename:
                        pass  # already correct
                if dest.exists():
                    images.append(filename)
            except Exception as e:
                print(f"  ✗ failed node {i+1}: {e}")
    else:
        filename = "photo_1.jpg"
        dest = post_dir / filename
        print(f"  downloading {shortcode}...")
        try:
            L.download_pic(filename=str(post_dir / "photo_1"), url=post.url, mtime=post.date_utc)
            for f in post_dir.glob("photo_1.*"):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.name != filename:
                    f.rename(dest)
            if dest.exists():
                images.append(filename)
        except Exception as e:
            print(f"  ✗ failed to download {shortcode}: {e}")

    if not images:
        import shutil
        shutil.rmtree(post_dir, ignore_errors=True)
        return False

    # Write frontmatter with list of images
    images_yaml = "\n".join(f'  - "{img}"' for img in images)
    frontmatter = f"""---
date: {date_str}
caption: "{caption}"
instagram_url: "{permalink}"
images:
{images_yaml}
---
"""
    (post_dir / "index.md").write_text(frontmatter)
    return True


def main():
    username = os.environ.get("INSTAGRAM_USERNAME")
    if not username:
        print("ERROR: INSTAGRAM_USERNAME must be set", file=sys.stderr)
        sys.exit(1)

    session_file = os.environ.get("INSTAGRAM_SESSION_FILE")

    global L
    L = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        sleep=True,
    )

    if session_file and Path(session_file).exists():
        print(f"Loading session from {session_file}...")
        L.load_session_from_file(username, session_file)

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    existing_ids = set(state.get("fetched_ids", []))

    print(f"Fetching up to {MAX_POSTS} posts from @{username}...")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"ERROR: Profile @{username} not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    saved = 0
    checked = 0
    for post in profile.get_posts():
        if saved >= MAX_POSTS:
            break
        checked += 1

        if post.shortcode in existing_ids and post_exists(post.shortcode):
            print(f"  skip {post.shortcode} (already exists)")
            continue

        if create_page_bundle(post):
            saved += 1
            existing_ids.add(post.shortcode)

        if checked > MAX_POSTS * 2 and saved == 0:
            print("  no new posts found, stopping early")
            break

    state = {
        "fetched_ids": list(existing_ids),
        "fetched_count": len(list(CONTENT_DIR.glob("*/index.md"))),
        "last_fetch": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)

    print(f"\n✓ Done: {saved} new posts saved (total: {state['fetched_count']})")


if __name__ == "__main__":
    main()
