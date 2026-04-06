# Instagram Auto-Fetch Gallery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Tự động fetch ảnh từ Instagram Business/Creator account về Hugo site, hiển thị tại `/instagram` với PhotoSwipe lightbox và caption.

**Architecture:** GitHub Actions (manual trigger) chạy Python script gọi Instagram Graph API, download ảnh vào Hugo page bundles tại `content/instagram/<post-id>/`, lưu cursor phân trang vào `data/instagram_cursor.json` để mỗi lần trigger tiếp tục fetch ảnh cũ hơn. Hugo dùng custom layout `instagram/list.html` iterate qua `.Pages` thay vì `.Resources`.

**Tech Stack:** Python 3, Instagram Graph API v21, Hugo page bundles, GitHub Actions `workflow_dispatch`, PhotoSwipe (đã có sẵn).

---

## Task 1: Tạo Hugo content section `/instagram`

**Files:**
- Create: `content/instagram/_index.md`
- Modify: `config.toml` (thêm menu item)

**Step 1: Tạo `content/instagram/_index.md`**

```markdown
---
title: "Instagram"
type: "instagram"
url: "/instagram"
maxWidth: "800x"
clickablePhotos: true
---

Ảnh từ Instagram của mình.
```

**Step 2: Thêm menu item vào `config.toml`**

Tìm block `[[params.mainMenu]]` cuối cùng (trước `[imaging]`), thêm vào sau block `gallery`:

```toml
[[params.mainMenu]]
    link = "instagram"
    text = "instagram"
```

**Step 3: Kiểm tra Hugo build không lỗi**

```bash
hugo server -D
```

Truy cập `http://localhost:1313/instagram` — trang trống (chưa có layout) là bình thường.

---

## Task 2: Tạo Hugo layout cho Instagram section

**Files:**
- Create: `layouts/instagram/list.html`

**Step 1: Tạo `layouts/instagram/list.html`**

Layout này iterate qua `.Pages` (mỗi post là một page bundle), lấy ảnh từ resource của từng page. Dựa trên `themes/sam/layouts/gallery/list.html` nhưng adapted cho page bundles.

```html
{{ define "section_content" }}
<article role="article" class="flex-container">
    {{ .Content }}
</article>

<div class="grid">
{{ range sort .Pages "Date" "desc" }}
    {{ $page := . }}
    {{ $img := .Resources.GetMatch "photo.*" }}
    {{ if $img }}
        {{ $resized := $img.Resize $.Params.maxWidth }}
        <div>
            <a href="{{ $img.RelPermalink }}"
               data-size="{{ $img.Width }}x{{ $img.Height }}"
               data-caption="{{ $page.Params.caption | htmlEscape }} <a href='{{ $page.Params.instagram_url }}' target='_blank' rel='noopener'>Xem trên Instagram</a>">
                <img src="{{ $resized.RelPermalink }}" alt="{{ $page.Params.caption }}" />
            </a>
        </div>
    {{ end }}
{{ end }}
</div>

<!-- Root element of PhotoSwipe. Must have class pswp. -->
<div class="pswp" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="pswp__bg"></div>
    <div class="pswp__scroll-wrap">
        <div class="pswp__container">
            <div class="pswp__item"></div>
            <div class="pswp__item"></div>
            <div class="pswp__item"></div>
        </div>
        <div class="pswp__ui pswp__ui--hidden">
            <div class="pswp__top-bar">
                <div class="pswp__counter"></div>
                <button class="pswp__button pswp__button--close" title="Close (Esc)"></button>
                <button class="pswp__button pswp__button--share" title="Share"></button>
                <button class="pswp__button pswp__button--fs" title="Toggle fullscreen"></button>
                <button class="pswp__button pswp__button--zoom" title="Zoom in/out"></button>
                <div class="pswp__preloader">
                    <div class="pswp__preloader__icn">
                      <div class="pswp__preloader__cut">
                        <div class="pswp__preloader__donut"></div>
                      </div>
                    </div>
                </div>
            </div>
            <div class="pswp__share-modal pswp__share-modal--hidden pswp__single-tap">
                <div class="pswp__share-tooltip"></div>
            </div>
            <button class="pswp__button pswp__button--arrow--left" title="Previous (arrow left)"></button>
            <button class="pswp__button pswp__button--arrow--right" title="Next (arrow right)"></button>
            <div class="pswp__caption">
                <div class="pswp__caption__center"></div>
            </div>
        </div>
    </div>
</div>

{{ $photoswipe := "js/photoswipe.min.js"}}
<script src="{{ $photoswipe | absURL }}"></script>
{{ $photoswipeUI := "js/photoswipe-ui-default.min.js"}}
<script src="{{ $photoswipeUI | absURL }}"></script>
{{ $script := resources.Get "js/gallery.js" | minify}}
<script src="{{ $script.Permalink }}"></script>

{{ end }}
```

**Step 2: Tạo thư mục và file test để verify layout**

```bash
mkdir -p content/instagram/test-post
```

Tạo `content/instagram/test-post/index.md`:
```markdown
---
date: 2024-01-01T00:00:00Z
caption: "Test caption"
instagram_url: "https://www.instagram.com/p/test/"
---
```

Copy một ảnh bất kỳ từ gallery vào `content/instagram/test-post/photo.jpg` để test.

**Step 3: Verify Hugo render đúng**

```bash
hugo server -D
```

Vào `http://localhost:1313/instagram` — phải thấy ảnh test hiển thị với PhotoSwipe.

**Step 4: Xóa test-post sau khi verify xong**

```bash
rm -rf content/instagram/test-post
```

---

## Task 3: Tạo cursor state file

**Files:**
- Create: `data/instagram_cursor.json`

**Step 1: Tạo `data/instagram_cursor.json`**

```json
{
  "next_cursor": null,
  "fetched_count": 0,
  "last_fetch": null
}
```

- `next_cursor`: cursor của Instagram API để fetch trang tiếp theo (null = bắt đầu từ đầu, tức là ảnh mới nhất)
- `fetched_count`: tổng số ảnh đã fetch
- `last_fetch`: timestamp lần fetch gần nhất

---

## Task 4: Viết Python fetch script

**Files:**
- Create: `scripts/fetch_instagram.py`
- Create: `scripts/requirements.txt`

**Step 1: Tạo `scripts/requirements.txt`**

```
requests==2.31.0
```

**Step 2: Tạo `scripts/fetch_instagram.py`**

```python
#!/usr/bin/env python3
"""
Fetch Instagram photos via Graph API and save as Hugo page bundles.

Required env vars:
  INSTAGRAM_ACCESS_TOKEN - Long-lived Instagram access token
  INSTAGRAM_USER_ID      - Numeric Instagram user ID
  GH_TOKEN               - GitHub token (for updating secret after refresh)
  GITHUB_REPOSITORY      - e.g. "dinhnguyen/dinhnn.com" (set by Actions automatically)
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import requests

CONTENT_DIR = Path("content/instagram")
CURSOR_FILE = Path("data/instagram_cursor.json")
BATCH_SIZE = 24
API_BASE = "https://graph.instagram.com"
GRAPH_BASE = "https://graph.facebook.com/v21.0"


def load_cursor():
    if CURSOR_FILE.exists():
        return json.loads(CURSOR_FILE.read_text())
    return {"next_cursor": None, "fetched_count": 0, "last_fetch": None}


def save_cursor(state):
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_FILE.write_text(json.dumps(state, indent=2))


def refresh_token(token):
    """Refresh long-lived token. Returns new token string."""
    resp = requests.get(
        f"{API_BASE}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def update_github_secret(token, repo, gh_token):
    """Update INSTAGRAM_ACCESS_TOKEN secret in GitHub repo via API."""
    # Get repo public key for encrypting secret
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github+json",
    }
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    )
    key_resp.raise_for_status()
    key_data = key_resp.json()

    # Encrypt secret using libsodium (via PyNaCl if available, else skip)
    try:
        from base64 import b64encode
        from nacl import encoding, public

        pk = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder)
        sealed = public.SealedBox(pk).encrypt(token.encode())
        encrypted = b64encode(sealed).decode()

        requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/INSTAGRAM_ACCESS_TOKEN",
            headers=headers,
            json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
        ).raise_for_status()
        print("✓ GitHub secret updated with refreshed token")
    except ImportError:
        print("⚠ PyNaCl not installed — skipping GitHub secret update. Install with: pip install PyNaCl")


def fetch_media_page(user_id, token, after_cursor=None):
    """Fetch one page of media from Instagram Graph API."""
    params = {
        "fields": "id,caption,media_type,media_url,thumbnail_url,timestamp,permalink",
        "limit": BATCH_SIZE,
        "access_token": token,
    }
    if after_cursor:
        params["after"] = after_cursor

    resp = requests.get(f"{API_BASE}/{user_id}/media", params=params)
    resp.raise_for_status()
    return resp.json()


def sanitize_caption(caption):
    """Strip newlines/tabs for YAML frontmatter safety."""
    if not caption:
        return ""
    return re.sub(r"[\n\r\t]+", " ", caption).replace('"', "'").strip()


def post_exists(post_id):
    return (CONTENT_DIR / post_id).exists()


def download_image(url, dest_path):
    """Download image from URL to dest_path."""
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)


def create_page_bundle(post):
    """Create Hugo page bundle for one Instagram post."""
    post_id = post["id"]
    if post_exists(post_id):
        print(f"  skip {post_id} (already exists)")
        return False

    media_type = post.get("media_type", "")
    if media_type == "VIDEO":
        print(f"  skip {post_id} (VIDEO)")
        return False

    # For CAROUSEL_ALBUM, media_url points to first image
    image_url = post.get("media_url") or post.get("thumbnail_url")
    if not image_url:
        print(f"  skip {post_id} (no image url)")
        return False

    # Determine timestamp
    ts = post.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        date_str = dt.isoformat()
    except Exception:
        date_str = datetime.now(timezone.utc).isoformat()

    caption = sanitize_caption(post.get("caption", ""))
    permalink = post.get("permalink", "")

    # Create directory
    post_dir = CONTENT_DIR / post_id
    post_dir.mkdir(parents=True, exist_ok=True)

    # Write index.md
    frontmatter = f"""---
date: {date_str}
caption: "{caption}"
instagram_url: "{permalink}"
---
"""
    (post_dir / "index.md").write_text(frontmatter)

    # Download image
    print(f"  downloading {post_id}...")
    download_image(image_url, post_dir / "photo.jpg")

    return True


def main():
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.environ.get("INSTAGRAM_USER_ID")
    gh_token = os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")

    if not token or not user_id:
        print("ERROR: INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID must be set", file=sys.stderr)
        sys.exit(1)

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    # Refresh token first
    print("Refreshing access token...")
    try:
        new_token = refresh_token(token)
        token = new_token
        print("✓ Token refreshed")
        if gh_token and repo:
            update_github_secret(token, repo, gh_token)
    except Exception as e:
        print(f"⚠ Token refresh failed: {e} — continuing with existing token")

    # Load state
    state = load_cursor()
    cursor = state.get("next_cursor")
    fetched_count = state.get("fetched_count", 0)

    print(f"Fetching up to {BATCH_SIZE} posts (cursor: {cursor or 'start'})...")

    data = fetch_media_page(user_id, token, after_cursor=cursor)
    posts = data.get("data", [])
    paging = data.get("paging", {})
    next_cursor = paging.get("cursors", {}).get("after")
    has_next = bool(paging.get("next"))

    saved = 0
    for post in posts:
        if create_page_bundle(post):
            saved += 1

    fetched_count += saved
    state = {
        "next_cursor": next_cursor if has_next else None,
        "fetched_count": fetched_count,
        "last_fetch": datetime.now(timezone.utc).isoformat(),
    }
    save_cursor(state)

    print(f"\n✓ Done: {saved} new photos saved (total: {fetched_count})")
    if not has_next:
        print("✓ Reached end of Instagram media — cursor reset to null for next run")


if __name__ == "__main__":
    main()
```

**Step 3: Test script locally (optional, cần có token thật)**

```bash
cd /path/to/dinhnn.com
pip install -r scripts/requirements.txt
INSTAGRAM_ACCESS_TOKEN=xxx INSTAGRAM_USER_ID=yyy python scripts/fetch_instagram.py
```

Expected output:
```
Refreshing access token...
✓ Token refreshed
Fetching up to 24 posts (cursor: start)...
  downloading 123456789...
  ...
✓ Done: 24 new photos saved (total: 24)
```

---

## Task 5: Tạo GitHub Actions workflow

**Files:**
- Create: `.github/workflows/fetch-instagram.yml`

**Step 1: Tạo `.github/workflows/fetch-instagram.yml`**

```yaml
name: Fetch Instagram Photos

on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Dry run (không commit)"
        required: false
        default: "false"
        type: choice
        options:
          - "false"
          - "true"

jobs:
  fetch:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      secrets: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GH_PAT }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r scripts/requirements.txt PyNaCl

      - name: Fetch Instagram photos
        env:
          INSTAGRAM_ACCESS_TOKEN: ${{ secrets.INSTAGRAM_ACCESS_TOKEN }}
          INSTAGRAM_USER_ID: ${{ secrets.INSTAGRAM_USER_ID }}
          GH_TOKEN: ${{ secrets.GH_PAT }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: python scripts/fetch_instagram.py

      - name: Check for new files
        id: check
        run: |
          git status --porcelain
          COUNT=$(git status --porcelain | wc -l | tr -d ' ')
          echo "changed=$COUNT" >> $GITHUB_OUTPUT

      - name: Commit and push
        if: steps.check.outputs.changed != '0' && inputs.dry_run != 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          BATCH=$(cat data/instagram_cursor.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('fetched_count',0))")
          git add content/instagram/ data/instagram_cursor.json
          git commit -m "chore: fetch instagram photos (total: ${BATCH})"
          git push
```

**Step 2: Verify workflow file syntax**

```bash
# Không có tool validate YAML locally, chỉ cần kiểm tra indentation đúng
cat .github/workflows/fetch-instagram.yml
```

---

## Task 6: Cấu hình GitHub Secrets

Đây là bước thủ công, thực hiện trên GitHub web UI:

**Step 1: Lấy Instagram User ID**

Gọi API (thay `YOUR_TOKEN`):
```
https://graph.instagram.com/me?fields=id,username&access_token=YOUR_TOKEN
```

Kết quả trả về `id` — đó là `INSTAGRAM_USER_ID`.

**Step 2: Thêm secrets vào GitHub repo**

Vào `https://github.com/dinhnguyen/dinhnn.com/settings/secrets/actions` và thêm:

| Name | Value |
|------|-------|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived token (60 ngày) |
| `INSTAGRAM_USER_ID` | Numeric ID từ bước trên |
| `GH_PAT` | GitHub Personal Access Token với scope: `repo`, `secrets` |

**Step 3: Tạo GitHub PAT (nếu chưa có)**

Vào `https://github.com/settings/tokens/new`:
- Scopes: `repo` (full), `admin:org > read:org` (không cần)
- Expiration: No expiration hoặc 1 year

---

## Task 7: Test end-to-end

**Step 1: Trigger workflow thủ công**

Vào `https://github.com/dinhnguyen/dinhnn.com/actions/workflows/fetch-instagram.yml` → "Run workflow" → chọn `dry_run: false`.

**Step 2: Verify workflow pass**

Kiểm tra logs — phải thấy:
```
✓ Token refreshed
✓ GitHub secret updated with refreshed token
Fetching up to 24 posts...
  downloading ...
✓ Done: N new photos saved
```

**Step 3: Verify Cloudflare Pages deploy**

Sau khi workflow commit & push, Cloudflare Pages sẽ tự build. Kiểm tra `https://dinhnn.com/instagram` — phải thấy ảnh hiển thị với PhotoSwipe.

---

## Lưu ý quan trọng

### Instagram Access Token
- Token hết hạn sau **60 ngày**. Script tự refresh mỗi lần chạy.
- Nếu token expired trước khi chạy workflow, phải lấy token mới từ [Facebook Developer Console](https://developers.facebook.com/).

### Lấy Long-Lived Token lần đầu
1. Vào [Facebook Developer Console](https://developers.facebook.com/) → tạo app
2. Thêm "Instagram Basic Display" product
3. Lấy short-lived token từ OAuth flow
4. Đổi sang long-lived token:
   ```
   GET https://graph.instagram.com/access_token
     ?grant_type=ig_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &access_token={short-lived-token}
   ```

### Phân trang (cursor)
- Lần 1: fetch 24 ảnh mới nhất, lưu cursor
- Lần 2: fetch 24 ảnh tiếp theo (cũ hơn), lưu cursor mới
- Khi hết ảnh: `next_cursor` = null → lần sau bắt đầu lại từ đầu (fetch ảnh mới nhất)
