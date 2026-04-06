# Design: Instagram Auto-Fetch Gallery

**Date:** 2026-02-20
**Status:** Approved

## Summary

Tự động fetch ảnh từ tài khoản Instagram (Business/Creator) về Hugo static site, hiển thị tại trang `/instagram` riêng biệt. Mỗi lần trigger thủ công qua GitHub Actions sẽ fetch tối đa 24 ảnh theo chiều ngược thời gian (mới → cũ), dần dần lấp đầy toàn bộ lịch sử ảnh.

## Architecture

```
Instagram Graph API
        ↓
  GitHub Actions (manual trigger)
        ↓
  scripts/fetch_instagram.py
  ├── Đọc data/instagram_cursor.json
  ├── Fetch 24 ảnh (IMAGE + CAROUSEL_ALBUM, bỏ qua VIDEO)
  ├── Download ảnh → content/instagram/<post-id>/
  ├── Tạo index.md cho mỗi ảnh
  └── Cập nhật data/instagram_cursor.json
        ↓
  Git commit + push
        ↓
  Cloudflare Pages auto-deploy → /instagram
```

## File Structure

```
content/instagram/
├── _index.md                     # Trang /instagram
└── <post-id>/
    ├── index.md                  # Metadata: date, caption, instagram_url
    └── photo.jpg                 # Ảnh download từ Instagram

data/
└── instagram_cursor.json         # { "next_cursor": "...", "fetched_count": 48 }

.github/workflows/
└── fetch-instagram.yml           # GitHub Actions workflow

scripts/
└── fetch_instagram.py            # Script Python
```

### index.md frontmatter format

```yaml
---
date: 2024-01-15T10:30:00Z
caption: "Caption từ Instagram"
instagram_url: "https://www.instagram.com/p/ABC123/"
---
```

## GitHub Actions

**Trigger:** `workflow_dispatch` (manual)

**Required Secrets:**

| Secret | Mô tả |
|--------|-------|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived token (60 ngày, auto-refresh) |
| `INSTAGRAM_USER_ID` | Numeric ID của tài khoản |
| `GH_PAT` | GitHub PAT để workflow commit & push |

**Script logic:**
1. Đọc `data/instagram_cursor.json` để lấy cursor từ lần trước
2. Gọi `GET /me/media?fields=id,caption,media_url,timestamp&after=<cursor>&limit=24`
3. Bỏ qua VIDEO, chỉ xử lý IMAGE và CAROUSEL_ALBUM
4. Download ảnh, tạo Hugo page bundle
5. Cập nhật cursor vào `data/instagram_cursor.json`
6. Auto-refresh access token và lưu lại vào GitHub Secret
7. Commit: `chore: fetch instagram photos (batch N)`
8. Push → Cloudflare Pages deploy tự động

## Hugo Frontend

- **URL:** `/instagram`
- **Layout:** Tái sử dụng gallery layout hiện có (PhotoSwipe lightbox)
- **Menu:** Thêm mục "Instagram" vào `config.toml`
- **Caption:** Hiển thị trong lightbox
- **Link gốc:** "Xem trên Instagram" trong lightbox
- **Sắp xếp:** Mới nhất lên trên (`date` descending)
