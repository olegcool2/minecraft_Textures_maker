# Minecraft Texture Replacer v2.1

Replace Minecraft textures with your photos, or browse packs from minecraft-inside.ru.

---

## Option A — Standalone EXE (no Python needed for end users)

### How to BUILD the .exe (one-time, requires Python on YOUR machine)

1. Double-click **`build.bat`**
2. Wait 1-3 minutes while PyInstaller bundles everything
3. Find **`dist\MCTextureReplacer.exe`**
4. Share that single `.exe` file — recipients need NO Python!

> The EXE contains Python + Pillow + requests + beautifulsoup4 inside.
> File size will be ~30-60 MB (normal for bundled Python apps).

---

## Option B — Run with Python (auto-installs deps)

If you have Python 3.10+:

1. Double-click **`run.bat`** — OR run `python app.py`
2. On first launch: a splash window appears and auto-installs packages
3. App opens automatically when ready

---

## Features

### Tab 1 – My Photos
Replace any texture from your installed Minecraft version with your own photo.

| Step | Action |
|------|--------|
| 1 | Click **Load versions** to detect MC versions |
| 2 | Pick category (Blocks, Items, Entities...) or search |
| 3 | Click a texture — see original preview |
| 4 | Click **Choose photo** — any JPG/PNG/BMP/WEBP |
| 5 | Adjust resize mode and size, preview updates instantly |
| 6 | Click **Add replacement** — repeat for more textures |
| 7 | Export: **Save Folder** / **Save ZIP** / **Install to MC** |

### Tab 2 – Browse Packs (minecraft-inside.ru)
Browse, preview, and download texture packs directly from minecraft-inside.ru.

| Feature | Details |
|---------|---------|
| Thumbnail grid | Auto-loads pack preview images |
| Categories | All / PvP / Realistic / 3D / Modern / Medieval / Cartoon / FPS |
| Search | Searches minecraft-inside.ru |
| Pagination | Prev / Next buttons |
| Screenshot gallery | Scroll horizontally, click to open full-size |
| Download | Click version button → choose folder → progress bar |

---

## Activating a pack in Minecraft
Options → Resource Packs → move pack to right column → Done

## Pack format numbers (for pack.mcmeta)
| Version | Format |
|---------|--------|
| 1.21+   | 34 |
| 1.20.x  | 22 |
| 1.19.x  | 13 |
| 1.18.x  | 8  |
| 1.17.x  | 7  |