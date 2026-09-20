"""
Minecraft Resource & Shader Manager v3.2
=========================================
Tab 1 - Replace textures with your own photos (Totem, Grass, etc.)
Tab 2 - Preview, listen & replace in-game sounds (Totem, Hurt, Anvil, etc.)
Tab 3 - Download texture packs from GitHub with screenshot preview
Tab 4 - Download & install shaders (Shaderpacks) with version warning & Iris/OptiFine guide
"""

import sys, subprocess, importlib

# Auto-install dependencies if running from Python directly
for _mod, _pkg in [
    ("PIL", "pillow"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
    ("pygame", "pygame-ce"),
    ("soundfile", "soundfile")
]:
    try:
        importlib.import_module(_mod)
    except ImportError:
        if not getattr(sys, "frozen", False):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", _pkg])
            except Exception as _err:
                print(f"Failed to auto-install {_pkg}: {_err}")

import html, io, json, os, posixpath, re, shutil, tempfile, threading, time, webbrowser, zipfile
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageOps, ImageTk

# Audio engine imports
try:
    import pygame
except Exception:
    pygame = None

try:
    import soundfile as sf
except Exception:
    sf = None

try:
    import winsound
except Exception:
    winsound = None

# ── Colors & Theme ────────────────────────────────────────────────────────────
BG      = "#1e1e2e"
SURFACE = "#313244"
ACCENT  = "#89b4fa"
TEXT    = "#cdd6f4"
SUBTEXT = "#a6adc8"
SUCCESS = "#a6e3a1"
WARNING = "#f38ba8"

TEXTURE_SIZES = [16, 32, 64, 128, 256]
DEFAULT_MC = Path.home() / "AppData" / "Roaming" / ".minecraft"

TEXTURE_CATEGORIES = {
    "Blocks":      "textures/block",
    "Items":       "textures/item",
    "Entities":    "textures/entity",
    "Environment": "textures/environment",
    "GUI":         "textures/gui",
    "All":         "",
}

# ── Sources ───────────────────────────────────────────────────────────────────
SITE_INSIDE_BASE = "https://minecraft-inside.ru"
INSIDE_CATEGORIES = {
    "Все текстуры":   f"{SITE_INSIDE_BASE}/resource-packs/",
    "PvP":             f"{SITE_INSIDE_BASE}/resource-packs/pvp/",
    "Реалистичные":    f"{SITE_INSIDE_BASE}/resource-packs/realism/",
    "3D":              f"{SITE_INSIDE_BASE}/resource-packs/3d/",
    "Современные":     f"{SITE_INSIDE_BASE}/resource-packs/modern/",
    "Средневековые":   f"{SITE_INSIDE_BASE}/resource-packs/medieval/",
    "Мультяшные":      f"{SITE_INSIDE_BASE}/resource-packs/mult/",
    "FPS":             f"{SITE_INSIDE_BASE}/resource-packs/fps/",
    "Популярные":      f"{SITE_INSIDE_BASE}/resource-packs/?sort=rating",
}

SITE_EXPERT_BASE = "https://minecraftexpert.ru"
EXPERT_CATEGORIES = {
    "Все текстуры":       f"{SITE_EXPERT_BASE}/textures/",
    "Версия 1.21":        f"{SITE_EXPERT_BASE}/textures/1-21/",
    "Версия 1.20":        f"{SITE_EXPERT_BASE}/textures/1-20-1/",
    "Версия 1.19":        f"{SITE_EXPERT_BASE}/textures/1-19-4/",
    "Версия 1.18":        f"{SITE_EXPERT_BASE}/textures/1-18-2/",
    "Версия 1.16.5":      f"{SITE_EXPERT_BASE}/textures/1-16-5/",
    "Версия 1.12.2":      f"{SITE_EXPERT_BASE}/textures/1-12-2/",
    "Разрешение 16x16":   f"{SITE_EXPERT_BASE}/textures/16x16/",
    "Разрешение 32x32":   f"{SITE_EXPERT_BASE}/textures/32x32/",
    "Разрешение 64x64+":  f"{SITE_EXPERT_BASE}/textures/64x64/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ru,en;q=0.9",
}
THUMB_W, THUMB_H = 200, 140

# ── Local Texture Helpers ─────────────────────────────────────────────────────
def find_mc_jars(mc_path):
    jars = []
    vdir = mc_path / "versions"
    if vdir.exists():
        for d in sorted(vdir.iterdir(), reverse=True):
            for j in d.glob("*.jar"):
                if not j.name.endswith("-natives.jar"):
                    jars.append(j)
    return jars

def list_textures(jar, prefix="assets/minecraft/textures"):
    result = []
    try:
        with zipfile.ZipFile(jar) as zf:
            for n in zf.namelist():
                if n.startswith(prefix) and n.endswith(".png"):
                    result.append(n)
    except Exception:
        pass
    return sorted(result)

def extract_texture(jar, path):
    try:
        with zipfile.ZipFile(jar) as zf:
            with zf.open(path) as f:
                return Image.open(f).copy().convert("RGBA")
    except Exception:
        return None

def process_image(src, size, mode="fill", keep_alpha=True):
    img = Image.open(src).convert("RGBA")
    w, h = size
    if mode == "fit":
        img = ImageOps.contain(img, (w, h), Image.LANCZOS)
        c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        c.paste(img, ((w - img.width)//2, (h - img.height)//2), img)
        result = c
    elif mode == "fill":
        result = ImageOps.fit(img, (w, h), Image.LANCZOS)
    elif mode == "stretch":
        result = img.resize((w, h), Image.LANCZOS)
    elif mode == "tile":
        c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for y in range(0, h, max(1, img.height)):
            for x in range(0, w, max(1, img.width)):
                c.paste(img, (x, y))
        result = c
    else:
        result = img.resize((w, h), Image.LANCZOS)
    if not keep_alpha:
        bg = Image.new("RGB", result.size, (255, 255, 255))
        bg.paste(result, mask=result.split()[3])
        result = bg.convert("RGBA")
    return result

def build_pack(pack_dir, replacements, desc="MC Texture Replacer"):
    pack_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "pack": {
            "pack_format": 34,
            "supported_formats": [1, 99],
            "description": desc
        }
    }
    with open(pack_dir / "pack.mcmeta", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    # Generate pack.png icon from replacement image
    if replacements and "image" in replacements[0]:
        try:
            icon = replacements[0]["image"].resize((128, 128), Image.LANCZOS)
            icon.save(pack_dir / "pack.png", "PNG")
        except Exception:
            pass
    for r in replacements:
        dest = pack_dir / Path(r["mc_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        r["image"].save(dest, "PNG")
    return pack_dir

def zip_pack(pack_dir, out_zip=None):
    zp = out_zip if out_zip else pack_dir.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pack_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(pack_dir))
    return zp

def install_pack(pack_dir, mc):
    rp = mc / "resourcepacks"
    rp.mkdir(parents=True, exist_ok=True)
    # 1. Install as ZIP archive with pack.mcmeta at root
    zip_dest = rp / f"{pack_dir.name}.zip"
    zip_pack(pack_dir, zip_dest)
    # 2. Also install as unpacked folder for maximum launcher compatibility
    folder_dest = rp / pack_dir.name
    if folder_dest.exists():
        shutil.rmtree(folder_dest, ignore_errors=True)
    try:
        shutil.copytree(pack_dir, folder_dest)
    except Exception:
        pass
    return zip_dest

# ── Scrapers ──────────────────────────────────────────────────────────────────
def fetch_html(url, retries=2):
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            r.encoding = "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception:
            time.sleep(0.5)
    return None

# 1. Minecraft-Inside
def scrape_inside_listing(url):
    soup = fetch_html(url)
    if not soup: return []
    packs, seen = [], set()
    for tag in soup.find_all(["article", "div", "li"]):
        a = tag.find("a", href=re.compile(r"/resource-packs/\d+-.+\.html"))
        if not a: continue
        href = a["href"]
        if href in seen: continue
        seen.add(href)
        title = a.get_text(strip=True)
        if not title: continue
        img_tag = tag.find("img")
        thumb = ""
        if img_tag:
            thumb = img_tag.get("src") or img_tag.get("data-src") or ""
            if thumb and not thumb.startswith("http"):
                thumb = SITE_INSIDE_BASE + thumb
        pack_url = href if href.startswith("http") else SITE_INSIDE_BASE + href
        packs.append({"source": "inside", "title": html.unescape(title), "url": pack_url, "thumb": thumb})
    return packs

def scrape_inside_detail(url):
    soup = fetch_html(url)
    if not soup: return {}
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    images, seen_imgs = [], set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src in seen_imgs: continue
        try:
            if int(img.get("width", 999)) < 100 or int(img.get("height", 999)) < 100: continue
        except Exception: pass
        if any(x in src for x in ["/avatars/", "/icons/", "/emoji/", "/logo"]): continue
        full = src if src.startswith("http") else SITE_INSIDE_BASE + src
        seen_imgs.add(src)
        images.append(full)
    downloads = []
    for a in soup.find_all("a", href=re.compile(r"/download/\d+/")):
        label = a.get_text(strip=True)
        href  = a["href"]
        dl_url = href if href.startswith("http") else SITE_INSIDE_BASE + href
        entry = {"label": label or "Скачать", "url": dl_url, "is_cloud": False}
        if entry not in downloads:
            downloads.append(entry)
    desc_parts = []
    for p in soup.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 40 and "Скачать" not in txt and "http" not in txt:
            desc_parts.append(txt)
        if len(desc_parts) >= 4: break
    return {"title": html.unescape(title), "images": images, "downloads": downloads, "description": "\n\n".join(desc_parts[:3])}

# 2. MinecraftExpert
def scrape_expert_listing(url):
    soup = fetch_html(url)
    if not soup: return []
    packs, seen = [], set()
    for tag in soup.find_all(["article", "div"]):
        classes = " ".join(tag.get("class", []))
        if "post" in classes and not any(x in classes for x in ["related", "meta", "widget"]):
            a = tag.find("a", href=re.compile(r"minecraftexpert\.ru/[^/]+-texture/"))
            if not a:
                for link in tag.find_all("a", href=True):
                    if "-texture" in link["href"] and "minecraftexpert.ru" in link["href"]:
                        a = link
                        break
            if not a: continue
            href = a["href"]
            if href in seen: continue
            seen.add(href)
            title = a.get_text(strip=True) or a.get("title", "")
            if not title:
                h = tag.find(["h2", "h3"])
                if h: title = h.get_text(strip=True)
            if not title: continue
            img_tag = tag.find("img")
            thumb = ""
            if img_tag:
                thumb = img_tag.get("src") or img_tag.get("data-src") or ""
                if not thumb and img_tag.get("srcset"):
                    thumb = img_tag["srcset"].split(",")[0].split()[0]
            packs.append({"source": "expert", "title": html.unescape(title), "url": href, "thumb": thumb})
    return packs

def scrape_expert_detail(url):
    soup = fetch_html(url)
    if not soup: return {}
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    images, seen_imgs = [], set()
    for a in soup.find_all("a", href=re.compile(r"\.(png|jpg|jpeg|webp)$", re.I)):
        href = a["href"]
        if href not in seen_imgs and not any(x in href for x in ["avatar", "icon", "logo"]):
            seen_imgs.add(href)
            images.append(href)
    downloads = []
    for div in soup.find_all("div", class_=re.compile(r"download-button")):
        if "tg-button" in div.get("class", []): continue
        a = div.find("a", href=True)
        if not a: continue
        raw_t = a.get_text(strip=True)
        href = a["href"]
        is_cloud = any(x in href for x in ["cloud.mail.ru", "yadi.sk", "drive.google", "mediafire"])
        pfx = "☁️ [Облако] " if is_cloud else "⬇ "
        label = pfx + (raw_t or "Скачать")
        entry = {"label": html.unescape(label), "url": href, "is_cloud": is_cloud}
        if entry not in downloads:
            downloads.append(entry)
    desc_parts = []
    content_div = soup.find("div", class_=re.compile(r"post-content|entry-content"))
    if content_div:
        for p in content_div.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 35 and not any(x in txt for x in ["Скачать", "http", "Версия", "Установка"]):
                desc_parts.append(txt)
            if len(desc_parts) >= 4: break
    return {"title": html.unescape(title), "images": images, "downloads": downloads, "description": "\n\n".join(desc_parts[:3])}

def fetch_image_pil(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        return None

def extract_gdrive_id(url_or_id):
    s = url_or_id.strip()
    m = re.search(r"(?:/file/d/|id=)([a-zA-Z0-9_-]{25,})", s)
    if m: return m.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{25,}$", s): return s
    return None

def download_from_gdrive(file_id, dest_target, progress_cb=None):
    session = requests.Session()
    session.headers.update(HEADERS)
    base_url = "https://drive.google.com/uc?export=download"
    resp = session.get(base_url, params={"id": file_id}, stream=True, timeout=30)
    
    token = None
    for k, v in session.cookies.items():
        if k.startswith("download_warning"):
            token = v
            break
            
    content_type = resp.headers.get("content-type", "").lower()
    if token:
        resp = session.get(base_url, params={"id": file_id, "confirm": token}, stream=True, timeout=60)
    elif "text/html" in content_type:
        text = resp.text
        m_conf = re.search(r'confirm=([0-9A-Za-z_]+)', text)
        if m_conf:
            resp = session.get(base_url, params={"id": file_id, "confirm": m_conf.group(1)}, stream=True, timeout=60)
        else:
            soup = BeautifulSoup(text, "html.parser")
            form = soup.find("form", id="download-form") or soup.find("a", id="uc-download-link")
            if form:
                action = form.get("action") or form.get("href")
                if action:
                    if not action.startswith("http"):
                        action = "https://drive.google.com" + action
                    resp = session.get(action, stream=True, timeout=60)
            else:
                if "access denied" in text.lower() or "доступ" in text.lower():
                    raise Exception("Нет доступа к Google Диску! Включите «Доступ всем, у кого есть ссылка».")
                raise Exception("Google Диск не отдал файл. Проверьте права доступа к файлу.")

    resp.raise_for_status()

    cd = resp.headers.get("content-disposition", "")
    filename = None
    if "filename=" in cd:
        m_fn = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd)
        if m_fn:
            filename = urllib.parse.unquote(m_fn.group(1))

    if not filename:
        if isinstance(dest_target, Path) and not dest_target.is_dir() and dest_target.name.endswith(".zip"):
            filename = dest_target.name
        else:
            filename = "ResourcePack_GDrive.zip"

    actual_dest = (dest_target / filename) if (isinstance(dest_target, Path) and dest_target.is_dir()) else Path(dest_target)
    
    total = int(resp.headers.get("content-length", 0))
    done = 0
    with open(actual_dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    return actual_dest

def is_yandex_disk(url):
    return any(domain in url for domain in ["disk.yandex.ru", "disk.yandex.com", "yadi.sk"])

def download_from_yandex(yandex_url, dest_target, progress_cb=None):
    api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
    resp = requests.get(api_url, params={"public_key": yandex_url}, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Ошибка Яндекс.Диска ({resp.status_code}). Проверьте, что ссылка публичная.")
    data = resp.json()
    direct_url = data.get("href")
    if not direct_url:
        raise Exception("Не удалось получить прямую ссылку с Яндекс.Диска.")
    
    filename = data.get("name")
    if not filename:
        parsed = urllib.parse.urlparse(direct_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "filename" in qs:
            filename = qs["filename"][0]
    if not filename:
        filename = "ResourcePack_Yandex.zip"
        
    actual_dest = (dest_target / filename) if (isinstance(dest_target, Path) and dest_target.is_dir()) else Path(dest_target)
    return download_file(direct_url, actual_dest, progress_cb)

def download_file(url, dest_path, progress_cb=None, referer=None):
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    elif "minecraft-inside" in url:
        headers["Referer"] = "https://minecraft-inside.ru/"
    elif "minecraftexpert" in url:
        headers["Referer"] = "https://minecraftexpert.ru/"

    if "dropbox.com" in url:
        url = url.replace("?dl=0", "?dl=1")
        if "?dl=1" not in url:
            url += "?dl=1"

    resp = requests.get(url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()

    cd = resp.headers.get("content-disposition", "")
    filename = None
    if "filename=" in cd:
        m_fn = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd)
        if m_fn:
            filename = urllib.parse.unquote(m_fn.group(1))

    if not filename:
        p_name = Path(urllib.parse.urlparse(url).path).name
        filename = p_name if p_name else "resourcepack.zip"
        if not (filename.endswith(".zip") or filename.endswith(".jar")):
            filename += ".zip"

    actual_dest = (dest_path / filename) if (isinstance(dest_path, Path) and dest_path.is_dir()) else Path(dest_path)
    
    total = int(resp.headers.get("content-length", 0))
    done = 0
    with open(actual_dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    return actual_dest

def resolve_download(dl_url):
    try:
        resp = requests.get(dl_url, headers=HEADERS, timeout=12, allow_redirects=True)
        if "text/html" in resp.headers.get("content-type", ""):
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(href.endswith(ext) for ext in [".zip", ".jar"]):
                    return href if href.startswith("http") else SITE_INSIDE_BASE + href
        return resp.url
    except Exception:
        return dl_url

def download_universal_pack(link, dest_target, progress_cb=None, referer=None):
    link = link.strip()
    gid = extract_gdrive_id(link)
    if gid and ("drive.google" in link or "docs.google" in link or len(link) < 50):
        return download_from_gdrive(gid, dest_target, progress_cb)
    elif is_yandex_disk(link):
        return download_from_yandex(link, dest_target, progress_cb)
    else:
        return download_file(link, dest_target, progress_cb, referer=referer)

# ── Style ─────────────────────────────────────────────────────────────────────
def apply_style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE, font=("Segoe UI", 10))
    s.configure("TButton", background=ACCENT, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), relief="flat", padding=(10, 5))
    s.map("TButton", background=[("active", "#74c7ec"), ("pressed", "#89dceb")])
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, insertcolor=TEXT)
    s.configure("TCombobox", fieldbackground=SURFACE, foreground=TEXT, selectbackground=ACCENT)
    s.map("TCombobox",
          fieldbackground=[("readonly", SURFACE), ("!disabled", SURFACE)],
          selectbackground=[("readonly", ACCENT), ("!disabled", ACCENT)],
          selectforeground=[("readonly", "#1e1e2e"), ("!disabled", "#1e1e2e")],
          foreground=[("readonly", TEXT), ("!disabled", TEXT)],
          background=[("readonly", SURFACE), ("!disabled", SURFACE)])
    s.configure("Treeview", background=SURFACE, foreground=TEXT, rowheight=26, fieldbackground=SURFACE, borderwidth=0)
    s.configure("Treeview.Heading", background=BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
    s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#1e1e2e")])
    s.configure("TNotebook", background=BG, borderwidth=0)
    s.configure("TNotebook.Tab", background=SURFACE, foreground=SUBTEXT, padding=(14, 7), font=("Segoe UI", 11, "bold"))
    s.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "#1e1e2e")])
    s.configure("TFrame", background=BG)
    s.configure("TScrollbar", background=SURFACE, troughcolor=BG, arrowcolor=SUBTEXT, borderwidth=0)
    s.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT, borderwidth=0)
    s.configure("TLabelframe", background=BG, foreground=ACCENT)
    s.configure("TLabelframe.Label", background=BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))

# ── Tab 1: My Photos ──────────────────────────────────────────────────────────
class TextureTab(tk.Frame):
    def __init__(self, parent, mc_path_var, status_fn):
        super().__init__(parent, bg=BG)
        self.mc_path_var = mc_path_var
        self.set_status = status_fn
        self._jars = []
        self.selected_jar = None
        self.all_textures = []
        self.filtered_textures = []
        self.selected_texture = None
        self.user_image_path = None
        self.replacements = []
        self.fit_mode   = tk.StringVar(value="fill")
        self.keep_alpha = tk.BooleanVar(value=True)
        self.size_var   = tk.IntVar(value=16)
        self.pack_name  = tk.StringVar(value="MyTexturePack")
        self._orig_ph = None
        self._res_ph  = None
        self._empty_ph = None
        self._build()
        self.after(300, self._load_jars)

    def _build(self):
        # 1. Anchored bottom bar - packed FIRST so it is NEVER hidden on small screens
        bot = tk.Frame(self, bg=SURFACE, pady=10)
        bot.pack(fill="x", side="bottom")
        tk.Label(bot, text="📦 Имя пака:", bg=SURFACE, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(14, 4))
        tk.Entry(bot, textvariable=self.pack_name, width=18, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))
        
        btn_inst = tk.Button(bot, text="🚀 Шаг 3: Установить в Minecraft", bg=SUCCESS, fg="#1e1e2e",
                             activebackground="#94e2d5", font=("Segoe UI", 9, "bold"), relief="flat",
                             padx=14, pady=4, cursor="hand2", command=self._install)
        btn_inst.pack(side="left", padx=4)
        
        ttk.Button(bot, text="🗜 Экспорт в ZIP", command=self._save_zip).pack(side="left", padx=4)
        ttk.Button(bot, text="📁 В папку", command=self._save_folder).pack(side="left", padx=4)

        # 2. Top bar: Minecraft version jar selection
        ctrl = tk.Frame(self, bg=BG, pady=6)
        ctrl.pack(fill="x", padx=14)
        tk.Label(ctrl, text="Версия:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.jar_combo = ttk.Combobox(ctrl, state="readonly", width=28)
        self.jar_combo.pack(side="left", padx=6)
        self.jar_combo.bind("<<ComboboxSelected>>", self._on_jar)
        ttk.Button(ctrl, text="Загрузить версии", command=self._load_jars).pack(side="left", padx=2)

        # 3. Split workspace
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=260)
        self._build_left(left)
        
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=440)
        self._build_right(right)

    def _build_left(self, p):
        r = tk.Frame(p, bg=BG, pady=2)
        r.pack(fill="x")
        tk.Label(r, text="Категория:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.cat_combo = ttk.Combobox(r, state="readonly", values=list(TEXTURE_CATEGORIES.keys()), width=20)
        self.cat_combo.current(0)
        self.cat_combo.pack(side="left", padx=6)
        self.cat_combo.bind("<<ComboboxSelected>>", self._filter)

        r2 = tk.Frame(p, bg=BG, pady=2)
        r2.pack(fill="x")
        tk.Label(r2, text="Поиск:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        tk.Entry(r2, textvariable=self.search_var, width=22, bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat").pack(side="left", padx=6)

        # Quick preset chips
        chips = tk.Frame(p, bg=BG, pady=3)
        chips.pack(fill="x")
        tk.Label(chips, text="Быстро:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side="left")
        def _quick(q, cat="All"):
            if cat in TEXTURE_CATEGORIES:
                self.cat_combo.set(cat)
            self.search_var.set(q)
        for name, query, cname in [("🗿 Тотем", "totem", "Items"), ("🟩 Трава", "grass_block", "Blocks"), ("💎 Алмаз", "diamond", "Items"), ("💣 TNT", "tnt", "Blocks")]:
            btn = tk.Button(chips, text=name, bg=SURFACE, fg=TEXT, font=("Segoe UI", 8),
                            relief="flat", padx=4, pady=1, cursor="hand2",
                            activebackground=ACCENT, activeforeground="#1e1e2e",
                            command=lambda _q=query, _c=cname: _quick(_q, _c))
            btn.pack(side="left", padx=2)

        lf = tk.Frame(p, bg=BG)
        lf.pack(fill="both", expand=True, pady=4)
        self.tex_list = tk.Listbox(lf, bg=SURFACE, fg=TEXT, selectbackground=ACCENT, selectforeground="#1e1e2e", relief="flat", font=("Consolas", 9), activestyle="none")
        sb = ttk.Scrollbar(lf, command=self.tex_list.yview)
        self.tex_list.configure(yscrollcommand=sb.set)
        self.tex_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tex_list.bind("<<ListboxSelect>>", self._on_tex)
        self.tex_list.bind("<ButtonRelease-1>", self._on_tex)
        self.cnt = tk.Label(p, text="", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        self.cnt.pack()

    def _build_right(self, p):
        # Image preview cards
        prev = tk.Frame(p, bg=BG)
        prev.pack(fill="x", pady=(0, 6))

        # Blank 128x128 image so labels never expand to text character units
        self._empty_ph = ImageTk.PhotoImage(Image.new("RGBA", (128, 128), (45, 47, 65, 255)))

        def card(parent, title, hint, click_fn=None):
            c = tk.Frame(parent, bg=SURFACE, padx=10, pady=8, highlightthickness=1, highlightbackground="#45475a")
            c.pack(side="left", padx=(0, 10))
            tk.Label(c, text=title, bg=SURFACE, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(pady=(0, 4))
            
            box = tk.Frame(c, width=128, height=128, bg="#242638")
            box.pack_propagate(False)
            box.pack()
            
            il = tk.Label(box, bg="#242638", image=self._empty_ph, cursor="hand2" if click_fn else "")
            il.pack(fill="both", expand=True)
            if click_fn:
                il.bind("<Button-1>", lambda e: click_fn())
                box.bind("<Button-1>", lambda e: click_fn())
            
            sl = tk.Label(c, text=hint, bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 8))
            sl.pack(pady=(4, 0))
            return il, sl

        self.orig_lbl, self.orig_sz = card(prev, "1. Оригинал из игры", "Выберите в списке слева")
        
        arrow = tk.Label(prev, text="➡️", bg=BG, fg=ACCENT, font=("Segoe UI", 18))
        arrow.pack(side="left", padx=6)
        
        self.res_lbl, self.res_sz = card(prev, "2. Ваша картинка", "Нажмите для выбора фото", click_fn=self._browse_img)

        # Prominent Action Bar (Steps 1 & 2)
        act = tk.Frame(p, bg=SURFACE, padx=10, pady=8, highlightthickness=1, highlightbackground="#45475a")
        act.pack(fill="x", pady=(0, 6))

        btn_browse = tk.Button(
            act, text="📷 Шаг 1: Выбрать фото (миньона / любое)...",
            bg=ACCENT, fg="#1e1e2e", activebackground="#b4befe",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=12, pady=6, cursor="hand2",
            command=self._browse_img
        )
        btn_browse.pack(side="left")

        self.photo_lbl = tk.Label(act, text="Файл не выбран", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9))
        self.photo_lbl.pack(side="left", padx=10)

        btn_add = tk.Button(
            act, text="➕ Шаг 2: Добавить замену",
            bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6, cursor="hand2",
            command=self._add
        )
        btn_add.pack(side="right")

        # Settings row (compact)
        sf = tk.Frame(p, bg=BG)
        sf.pack(fill="x", pady=(0, 6))
        tk.Label(sf, text="Масштаб:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        for txt, val in [("Fill (заполнить)", "fill"), ("Fit (вписать)", "fit"), ("Stretch (растянуть)", "stretch")]:
            tk.Radiobutton(sf, text=txt, variable=self.fit_mode, value=val, bg=BG, fg=TEXT,
                           selectcolor=SURFACE, activebackground=BG, command=self._update_preview).pack(side="left", padx=4)
        
        tk.Label(sf, text="Размер:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        self.size_combo = ttk.Combobox(sf, values=[str(s) for s in TEXTURE_SIZES], width=5, state="readonly")
        self.size_combo.set("16")
        self.size_combo.pack(side="left", padx=(0, 10))
        self.size_combo.bind("<<ComboboxSelected>>", lambda e: (self.size_var.set(int(self.size_combo.get())), self._update_preview()))
        
        tk.Checkbutton(sf, text="Прозрачность (альфа)", variable=self.keep_alpha, bg=BG, fg=TEXT,
                       selectcolor=SURFACE, activebackground=BG, command=self._update_preview).pack(side="left")

        # Planned Replacements Table
        rf = ttk.LabelFrame(p, text=" Запланированные замены ")
        rf.pack(fill="both", expand=True, pady=(0, 4))
        cols = ("texture", "photo", "mode", "size")
        self.rep_tree = ttk.Treeview(rf, columns=cols, show="headings", height=4)
        for col, hd, w in zip(cols, ["Текстура в игре", "Ваше фото", "Режим", "Размер"], [200, 140, 70, 60]):
            self.rep_tree.heading(col, text=hd)
            self.rep_tree.column(col, width=w, anchor="w")
        rsb = ttk.Scrollbar(rf, command=self.rep_tree.yview)
        self.rep_tree.configure(yscrollcommand=rsb.set)
        self.rep_tree.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")
        
        tk.Button(p, text="🗑 Удалить выбранную замену из списка", bg=SURFACE, fg=TEXT,
                  activebackground="#f38ba8", activeforeground="#1e1e2e",
                  font=("Segoe UI", 8), relief="flat", pady=2, cursor="hand2",
                  command=self._remove).pack(fill="x")

    def _load_jars(self):
        jars = find_mc_jars(Path(self.mc_path_var.get()))
        if not jars:
            messagebox.showwarning("Не найдено", "Файлы версий .jar не найдены.")
            return
        self._jars = jars
        self.jar_combo["values"] = [j.stem for j in jars]
        self.jar_combo.current(0)
        self._on_jar()

    def _on_jar(self, *_):
        idx = self.jar_combo.current()
        if idx < 0: return
        self.selected_jar = self._jars[idx]
        self.set_status("Загрузка текстур...")
        threading.Thread(target=self._bg_load, daemon=True).start()

    def _bg_load(self):
        tx = list_textures(self.selected_jar)
        self.all_textures = tx
        self.after(0, self._filter)
        self.after(0, lambda: self.set_status(f"Загружено {len(tx)} текстур"))

    def _filter(self, *_):
        cat = TEXTURE_CATEGORIES.get(self.cat_combo.get(), "")
        pfx = f"assets/minecraft/{cat}" if cat else "assets/minecraft/textures"
        q   = self.search_var.get().lower()
        self.filtered_textures = [t for t in self.all_textures if t.startswith(pfx) and q in t.lower()]
        self.tex_list.delete(0, "end")
        for t in self.filtered_textures:
            self.tex_list.insert("end", Path(t).name)
        self.cnt.config(text=f"{len(self.filtered_textures)} текстур")

    def _on_tex(self, *_):
        sel = self.tex_list.curselection()
        if not sel or not self.selected_jar: return
        self.selected_texture = self.filtered_textures[sel[0]]
        orig = extract_texture(self.selected_jar, self.selected_texture)
        if orig:
            ph = ImageTk.PhotoImage(orig.resize((128, 128), Image.NEAREST))
            self.orig_lbl.configure(image=ph)
            self._orig_ph = ph
            self.orig_sz.config(text=f"{orig.width}x{orig.height}")
            if orig.width in TEXTURE_SIZES:
                self.size_var.set(orig.width)
                self.size_combo.set(str(orig.width))
        self._update_preview()

    def _browse_img(self):
        p = filedialog.askopenfilename(
            title="Выберите фото (например, миньона)",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"), ("Все файлы", "*.*")]
        )
        if p:
            self.user_image_path = p
            short = Path(p).name
            self.photo_lbl.config(text=(short[:32]+"...") if len(short)>34 else short, fg=SUCCESS)
            self._update_preview()

    def _update_preview(self, *_):
        if not self.user_image_path: return
        try:
            sz = self.size_var.get()
            r  = process_image(self.user_image_path, (sz, sz), self.fit_mode.get(), self.keep_alpha.get())
            ph = ImageTk.PhotoImage(r.resize((128, 128), Image.NEAREST))
            self.res_lbl.configure(image=ph)
            self._res_ph = ph
            self.res_sz.config(text=f"{sz}x{sz} (нажмите для смены)")
        except Exception as e:
            self.set_status(f"Ошибка превью: {e}", err=True)

    def _add(self):
        if not self.selected_texture:
            messagebox.showwarning("Нет текстуры", "1. Сначала выберите текстуру в списке слева (например, totem_of_undying.png).")
            return
        if not self.user_image_path:
            messagebox.showwarning("Нет фото", "2. Нажмите кнопку «📷 Шаг 1: Выбрать фото» и укажите картинку (миньона).")
            return
        sz   = self.size_var.get()
        mode = self.fit_mode.get()
        img  = process_image(self.user_image_path, (sz, sz), mode, self.keep_alpha.get())
        
        # If this texture was already added, update it
        for i, existing in enumerate(self.replacements):
            if existing["mc_path"] == self.selected_texture:
                self.replacements[i] = {"mc_path": self.selected_texture, "image": img}
                for item in self.rep_tree.get_children():
                    if self.rep_tree.item(item, "values")[0] == Path(self.selected_texture).name:
                        self.rep_tree.item(item, values=(Path(self.selected_texture).name, Path(self.user_image_path).name, mode, f"{sz}px"))
                        break
                self.set_status(f"Обновлено: {Path(self.selected_texture).name}")
                return

        self.replacements.append({"mc_path": self.selected_texture, "image": img})
        self.rep_tree.insert("", "end", values=(Path(self.selected_texture).name, Path(self.user_image_path).name, mode, f"{sz}px"))
        self.set_status(f"Добавлено в список: {Path(self.selected_texture).name}")

    def _remove(self):
        sel = self.rep_tree.selection()
        if not sel: return
        idx = self.rep_tree.index(sel[0])
        self.rep_tree.delete(sel[0])
        if 0 <= idx < len(self.replacements):
            self.replacements.pop(idx)

    def _check(self):
        if not self.replacements:
            # Auto-add if user already selected texture and photo
            if self.selected_texture and self.user_image_path:
                self._add()
                return True
            messagebox.showwarning(
                "Нет замен",
                "Инструкция:\n1. Выберите текстуру слева (например, totem_of_undying.png)\n"
                "2. Нажмите «Шаг 1: Выбрать фото» (укажите картинку миньона)\n"
                "3. Нажмите «Шаг 2: Добавить замену»"
            )
            return False
        return True

    def _save_folder(self):
        if not self._check(): return
        d = filedialog.askdirectory(title="Папка для сохранения")
        if not d: return
        pd = build_pack(Path(d) / self.pack_name.get(), self.replacements)
        self.set_status(f"Сохранено: {pd}")
        messagebox.showinfo("Готово!", f"Ресурспак сохранен в:\n{pd}")

    def _save_zip(self):
        if not self._check(): return
        d = filedialog.askdirectory(title="Папка для сохранения")
        if not d: return
        pd = Path(d) / self.pack_name.get()
        build_pack(pd, self.replacements)
        zp = zip_pack(pd)
        shutil.rmtree(pd, ignore_errors=True)
        self.set_status(f"Сохранено: {zp}")
        messagebox.showinfo("Готово!", f"ZIP сохранен в:\n{zp}")

    def _install(self):
        if not self._check(): return
        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Ошибка", f"Папка .minecraft не найдена:\n{mc}")
            return
        with tempfile.TemporaryDirectory() as tmp:
            pd   = build_pack(Path(tmp) / self.pack_name.get(), self.replacements)
            dest = install_pack(pd, mc)
        self.set_status(f"Установлено в Minecraft: {dest.name}")
        messagebox.showinfo(
            "Готово! Текстуры установлены",
            f"Ресурспак «{self.pack_name.get()}» успешно добавлен в Minecraft!\n\n"
            f"Как включить в игре:\n"
            f"1. Откройте Minecraft\n"
            f"2. Настройки -> Наборы ресурсов (Resource Packs)\n"
            f"3. Нажмите стрелочку на «{self.pack_name.get()}», чтобы переместить его вправо\n"
            f"4. Нажмите «Готово»!\n\n"
            f"(Если игра уже запущена, нажмите сочетание F3 + T для мгновенной перезагрузки текстур)"
        )

# ── Curated Favorites & GitHub Integration ────────────────────────────────────

DEFAULT_GITHUB_REPO = "olegcool2/minecraft_Textures_maker"

def fetch_github_packs(repo=DEFAULT_GITHUB_REPO):
    repo = repo.strip().strip("/")
    if not repo:
        repo = DEFAULT_GITHUB_REPO
    packs = []
    seen_urls = set()
    headers = dict(HEADERS)
    headers["Accept"] = "application/vnd.github.v3+json"

    # Determine default branch
    default_branch = "main"
    try:
        r_repo = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=6)
        if r_repo.status_code == 200:
            default_branch = r_repo.json().get("default_branch", "main")
    except Exception:
        pass

    # 1. Fetch assets from GitHub Releases (Best for packs & large files)
    try:
        url = f"https://api.github.com/repos/{repo}/releases"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            for rel in resp.json():
                rel_name = rel.get("name") or rel.get("tag_name") or "Релиз"
                rel_body = (rel.get("body") or "").strip()
                assets = rel.get("assets", [])

                zip_assets = []
                img_assets = []
                for asset in assets:
                    aname = asset.get("name", "")
                    aname_low = aname.lower()
                    if (aname_low.endswith(".zip") or aname_low.endswith(".jar")) and not aname_low.endswith(".exe"):
                        zip_assets.append(asset)
                    elif any(aname_low.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                        img_assets.append(asset)

                for z_asset in zip_assets:
                    z_name = z_asset.get("name", "")
                    dl_url = z_asset.get("browser_download_url", "")
                    if dl_url in seen_urls:
                        continue
                    seen_urls.add(dl_url)

                    z_stem = posixpath.splitext(z_name)[0].lower()
                    selected_img = None

                    # Priority 1: Exact 1.png, 1.jpg, 1.jpeg
                    for img in img_assets:
                        if img.get("name", "").lower() in ["1.png", "1.jpg", "1.jpeg", "1.webp"]:
                            selected_img = img
                            break
                    # Priority 2: Starts with 1.
                    if not selected_img:
                        for img in img_assets:
                            if img.get("name", "").lower().startswith("1."):
                                selected_img = img
                                break
                    # Priority 3: Matching pack name
                    if not selected_img:
                        for img in img_assets:
                            if posixpath.splitext(img.get("name", ""))[0].lower() == z_stem:
                                selected_img = img
                                break
                    # Priority 4: Any other image
                    if not selected_img and img_assets:
                        selected_img = img_assets[0]

                    img_url = selected_img.get("browser_download_url", "") if selected_img else ""
                    size_b = z_asset.get("size", 0)
                    size_mb = f"{size_b / (1024*1024):.1f} MB" if size_b else ""
                    desc_text = rel_body if rel_body else f"Ресурс-пак из релиза «{rel_name}» на GitHub"

                    cands = [
                        f"https://raw.githubusercontent.com/{repo}/{default_branch}/packs/{z_stem}/1.png",
                        f"https://raw.githubusercontent.com/{repo}/{default_branch}/packs/{z_stem}/1.jpg",
                        f"https://raw.githubusercontent.com/{repo}/{default_branch}/1.png",
                        f"https://raw.githubusercontent.com/{repo}/{default_branch}/1.jpg"
                    ]

                    packs.append({
                        "name": z_name,
                        "size": size_mb,
                        "source": f"🏷️ Релиз: {rel_name}",
                        "url": dl_url,
                        "image_url": img_url,
                        "candidate_img_urls": cands,
                        "desc": desc_text
                    })
    except Exception as e:
        print(f"[github releases] {e}")

    # 2. Fetch via Git Trees API (Scans repository folders and pairs pack with 1.png / 1.jpg)
    try:
        branches_to_try = [default_branch]
        if "main" not in branches_to_try: branches_to_try.append("main")
        if "master" not in branches_to_try: branches_to_try.append("master")

        for br in branches_to_try:
            tree_url = f"https://api.github.com/repos/{repo}/git/trees/{br}?recursive=1"
            resp = requests.get(tree_url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue

            tree_data = resp.json()
            items = tree_data.get("tree", [])

            folder_files = {}
            for it in items:
                if it.get("type") != "blob":
                    continue
                p = it.get("path", "")
                folder = posixpath.dirname(p)
                fname = posixpath.basename(p)
                folder_files.setdefault(folder, []).append({
                    "path": p,
                    "name": fname,
                    "size": it.get("size", 0)
                })

            for folder, files in folder_files.items():
                zips = [f for f in files if (f["name"].lower().endswith(".zip") or f["name"].lower().endswith(".jar")) and not f["name"].lower().endswith(".exe")]
                if not zips:
                    continue

                img_candidates = [f for f in files if any(f["name"].lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])]

                for z in zips:
                    raw_zip_url = f"https://raw.githubusercontent.com/{repo}/{br}/{z['path']}"
                    if raw_zip_url in seen_urls:
                        continue
                    seen_urls.add(raw_zip_url)

                    z_stem = posixpath.splitext(z["name"])[0].lower()
                    selected_img = None

                    for cand in img_candidates:
                        if cand["name"].lower() in ["1.png", "1.jpg", "1.jpeg", "1.webp"]:
                            selected_img = cand
                            break
                    if not selected_img:
                        for cand in img_candidates:
                            if cand["name"].lower().startswith("1."):
                                selected_img = cand
                                break
                    if not selected_img:
                        for cand in img_candidates:
                            if posixpath.splitext(cand["name"])[0].lower() == z_stem:
                                selected_img = cand
                                break
                    if not selected_img and img_candidates:
                        selected_img = img_candidates[0]

                    raw_img_url = f"https://raw.githubusercontent.com/{repo}/{br}/{selected_img['path']}" if selected_img else ""

                    if not raw_img_url:
                        root_cands = [f for f in folder_files.get("", []) if f["name"].lower() in ["1.png", "1.jpg", "1.jpeg"]]
                        if root_cands:
                            raw_img_url = f"https://raw.githubusercontent.com/{repo}/{br}/{root_cands[0]['path']}"

                    size_b = z.get("size", 0)
                    size_mb = f"{size_b / (1024*1024):.1f} MB" if size_b else ""
                    folder_display = folder if folder else "корень"

                    packs.append({
                        "name": z["name"],
                        "size": size_mb,
                        "source": f"📁 Папка: {folder_display}",
                        "url": raw_zip_url,
                        "image_url": raw_img_url,
                        "candidate_img_urls": [],
                        "desc": f"Файл из папки «{folder_display}» в репозитории GitHub"
                    })
            break
    except Exception as e:
        print(f"[github trees] {e}")

    # 3. Fetch from packs.json in repository (if present)
    try:
        for br in [default_branch, "main", "master"]:
            raw_json_url = f"https://raw.githubusercontent.com/{repo}/{br}/packs.json"
            resp = requests.get(raw_json_url, headers=HEADERS, timeout=5)
            if resp.status_code == 200:
                for p in resp.json():
                    u = p.get("url", "")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        img = p.get("image", "") or p.get("preview", "") or p.get("thumb", "")
                        if img and not img.startswith("http"):
                            img = f"https://raw.githubusercontent.com/{repo}/{br}/{img.lstrip('/')}"
                        if not img:
                            img = f"https://raw.githubusercontent.com/{repo}/{br}/1.png"
                        packs.append({
                            "name": p.get("name", "Ресурспак"),
                            "size": p.get("size", ""),
                            "source": "📋 packs.json",
                            "url": u,
                            "image_url": img,
                            "candidate_img_urls": [],
                            "desc": p.get("desc", "")
                        })
                break
    except Exception:
        pass

    return packs

# ── Curated Favorites Collection ─────────────────────────────────────────────
CURATED_FAVORITE_CATEGORIES = [
    "Все категории",
    "🎨 HD Ванилла",
    "🌙 Тёмный интерфейс",
    "⏳ Ностальгия / Ретро",
    "✨ HD Интерфейс",
    "⚔️ PvP Битвы",
    "💎 Современный стиль",
    "💎 Ultra HD 64x",
    "🔊 Звуки и эффекты"
]

CURATED_FAVORITE_PACKS = [
    {
        "name": "Faithful 32x (HD Ванилла)",
        "category": "🎨 HD Ванилла",
        "size": "12.5 MB",
        "source": "GitHub: Faithful-32x-Java",
        "url": "https://github.com/Faithful-Resource-Pack/Faithful-32x-Java/releases/download/september-2026-release/Faithful.32x.-.26.3.zip",
        "image_url": "https://database.faithfulpack.net/images/branding/logos/transparent/hd/f32_logo.png?w=256",
        "desc": "Самый знаменитый и популярный ресурс-пак в истории Minecraft! Увеличивает разрешение всех текстур в 2 раза (32x32) с сохранением ванильной эстетики и духа классической игры."
    },
    {
        "name": "Default Dark Mode (Тёмная тема)",
        "category": "🌙 Тёмный интерфейс",
        "size": "0.7 MB",
        "source": "GitHub: Default-Dark-Mode",
        "url": "https://github.com/nebuIr/Default-Dark-Mode/releases/download/2026.6.0/Default-Dark-Mode-26.2-2026.6.0.zip",
        "image_url": "https://raw.githubusercontent.com/nebuIr/Default-Dark-Mode/main/pack.png",
        "desc": "Элегантный тёмный интерфейс для всех меню, инвентарей, сундуков, печек, наковален и верстаков. Значительно снижает нагрузку на глаза при игре ночью!"
    },
    {
        "name": "Golden Days (Ретро Альфа / Бета)",
        "category": "⏳ Ностальгия / Ретро",
        "size": "0.4 MB",
        "source": "GitHub: golden-days",
        "url": "https://github.com/PoeticRainbow/golden-days/releases/download/16.3/golden-days-alpha-16.3-.1.20-to-26.3.zip",
        "image_url": "https://raw.githubusercontent.com/PoeticRainbow/golden-days/master/cover.png",
        "desc": "Возвращает яркие ностальгические текстуры травы, сочную листву, блоки, старый интерфейс и классические звуки золотой эры Minecraft Alpha и Beta!"
    },
    {
        "name": "CozyUI+ (Уютный HD интерфейс)",
        "category": "✨ HD Интерфейс",
        "size": "39.1 MB",
        "source": "GitHub: CozyUI-Plus",
        "url": "https://github.com/Fogg05/CozyUI-Plus/releases/download/v1.10/CozyUI%2B_v1.10.zip",
        "image_url": "https://raw.githubusercontent.com/Fogg05/CozyUI-Plus/main/description_image/banner.jpg",
        "desc": "Красивый, современный и аккуратный редизайн панелей инвентаря, кнопок, сердечек здоровья и иконок Minecraft в высоком разрешении."
    },
    {
        "name": "Plast-Pack (PvP Битвы и дуэли)",
        "category": "⚔️ PvP Битвы",
        "size": "6.4 MB",
        "source": "GitHub: Plast-Pack",
        "url": "https://github.com/Plastix/Plast-Pack/releases/download/v1.23/Plast-Pack.zip",
        "image_url": "https://raw.githubusercontent.com/Plastix/Plast-Pack/master/pack.png",
        "desc": "Оптимизированный ресурс-пак для PvP и битв: укороченные мечи, прозрачные меню инвентаря и улучшенный обзор в бою."
    },
    {
        "name": "Modernity GTNH (Текстуры Jappa)",
        "category": "💎 Современный стиль",
        "size": "52.9 MB",
        "source": "GitHub: Modernity-GTNH",
        "url": "https://github.com/ModernityGTNH/Modernity-GTNH/releases/download/weekly-2026-09-14/Modernity-GTNH-2026-09-14.zip",
        "image_url": "https://raw.githubusercontent.com/ModernityGTNH/Modernity-GTNH/master/pack.png",
        "desc": "Глобальное обновление текстур мира, руд, инструментов и блоков в детализированном современном стиле Jappa."
    },
    {
        "name": "Compliance 64x (Ultra HD 64x)",
        "category": "💎 Ultra HD 64x",
        "size": "5.5 MB",
        "source": "GitHub: Faithful-64x-Java",
        "url": "https://github.com/Faithful-Resource-Pack/Faithful-64x-Java/releases/download/alpha-6/Compliance_64x_-_Parity_Update.zip",
        "image_url": "https://database.faithfulpack.net/images/branding/logos/transparent/hd/f64_logo.png?w=256",
        "desc": "Максимальная детализация ванильного Minecraft в супер-высоком разрешении 64x64 пикселя для четкой и резкой картинки."
    },
    {
        "name": "Merged Damage Sounds (Звуки урона)",
        "category": "🔊 Звуки и эффекты",
        "size": "0.3 MB",
        "source": "GitHub: Merged-Damage-Sounds",
        "url": "https://github.com/Brottweiler/Merged-Damage-Sounds/releases/download/v1.8/Merged-Damage-Sounds.zip",
        "image_url": "https://raw.githubusercontent.com/Brottweiler/Merged-Damage-Sounds/master/pack.png",
        "desc": "Возвращает классический смачный звук получения урона («Oof!») при падении игрока и ударах мобов."
    }
]

# ── Tab 2: GitHub Repository & Curated Favorites ─────────────────────────────
class GitHubTab(tk.Frame):
    def __init__(self, parent, mc_path_var, status_fn):
        super().__init__(parent, bg=BG)
        self.mc_path_var = mc_path_var
        self.set_status = status_fn

        # Load saved repo from config file
        repo_file = Path.home() / ".mctexturereplacer_repo.txt"
        saved_repo = DEFAULT_GITHUB_REPO
        if repo_file.exists():
            try:
                saved_repo = repo_file.read_text(encoding="utf-8").strip() or DEFAULT_GITHUB_REPO
            except Exception:
                pass
        self.repo_var = tk.StringVar(value=saved_repo)

        self.mode = "favorites"  # "favorites" or "my_repo"
        self._displayed_packs = []
        self._repo_packs = []
        self._repo_loaded = False
        self._is_downloading = False
        self._selected_pack = None
        self._preview_id = 0
        self._current_screenshot_ph = None
        self._full_screenshot_pil = None

        self._build()
        self.after(100, lambda: self._set_mode("favorites"))

    def _build(self):
        # 1. Mode Switcher (Top segmented buttons)
        mode_bar = tk.Frame(self, bg=BG)
        mode_bar.pack(fill="x", padx=14, pady=(10, 6))

        self.btn_mode_fav = tk.Button(
            mode_bar, text="⭐ Избранные паки GitHub (Топ)",
            bg=ACCENT, fg="#1e1e2e", activebackground="#b4befe",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=6, cursor="hand2",
            command=lambda: self._set_mode("favorites")
        )
        self.btn_mode_fav.pack(side="left", padx=(0, 6))

        self.btn_mode_repo = tk.Button(
            mode_bar, text="👤 Мой личный репозиторий GitHub",
            bg="#313244", fg=TEXT, activebackground="#45475a",
            font=("Segoe UI", 10), relief="flat", padx=16, pady=6, cursor="hand2",
            command=lambda: self._set_mode("my_repo")
        )
        self.btn_mode_repo.pack(side="left")

        # 2. Dynamic Header Banner
        self.hdr = tk.Frame(self, bg=SURFACE, padx=16, pady=8)
        self.hdr.pack(fill="x", padx=14, pady=(0, 8))

        self.hdr_title = tk.Label(
            self.hdr, text="", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 12, "bold")
        )
        self.hdr_title.pack(anchor="w")

        self.hdr_sub = tk.Label(
            self.hdr, text="", bg=SURFACE, fg=TEXT, font=("Segoe UI", 9), justify="left"
        )
        self.hdr_sub.pack(anchor="w", pady=(2, 0))

        # 3. Dynamic Toolbars Container
        self.toolbar_box = tk.Frame(self, bg=BG)
        self.toolbar_box.pack(fill="x", padx=14, pady=(0, 8))

        # Toolbar A: Favorites Filter
        self.fav_toolbar = tk.Frame(self.toolbar_box, bg=SURFACE, padx=12, pady=7, highlightthickness=1, highlightbackground="#45475a")

        tk.Label(self.fav_toolbar, text="Категория:", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.cat_var = tk.StringVar(value="Все категории")
        self.cat_cb = ttk.Combobox(self.fav_toolbar, textvariable=self.cat_var, values=CURATED_FAVORITE_CATEGORIES, state="readonly", width=22)
        self.cat_cb.pack(side="left", padx=(6, 12))
        self.cat_cb.bind("<<ComboboxSelected>>", self._filter_favorites)

        tk.Label(self.fav_toolbar, text="Поиск:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.search_fav = tk.StringVar()
        s_ent = tk.Entry(self.fav_toolbar, textvariable=self.search_fav, width=20, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        s_ent.pack(side="left", padx=(6, 6))
        s_ent.bind("<KeyRelease>", self._filter_favorites)

        btn_fav_clear = tk.Button(
            self.fav_toolbar, text="✕", bg="#313244", fg=SUBTEXT, activebackground="#45475a",
            font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2, cursor="hand2",
            command=self._clear_fav_search
        )
        btn_fav_clear.pack(side="left", padx=(0, 10))

        btn_fav_local = tk.Button(
            self.fav_toolbar, text="📥 Установить свой .ZIP с ПК", bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, cursor="hand2", command=self._install_local_zip
        )
        btn_fav_local.pack(side="right")

        # Toolbar B: My Repo Controls
        self.repo_toolbar = tk.Frame(self.toolbar_box, bg=SURFACE, padx=12, pady=7, highlightthickness=1, highlightbackground="#45475a")

        tk.Label(self.repo_toolbar, text="Репозиторий:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.entry_repo = tk.Entry(self.repo_toolbar, textvariable=self.repo_var, width=30, bg=BG, fg=TEXT, insertbackground=TEXT, font=("Consolas", 9), relief="flat")
        self.entry_repo.pack(side="left", padx=(6, 10))

        btn_refresh = tk.Button(
            self.repo_toolbar, text="🔄 Обновить список с GitHub", bg=ACCENT, fg="#1e1e2e", activebackground="#b4befe",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, cursor="hand2", command=self._load_repo_packs
        )
        btn_refresh.pack(side="left", padx=(0, 6))

        btn_open_gh = tk.Button(
            self.repo_toolbar, text="🌐 Открыть", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=8, pady=4, cursor="hand2", command=self._open_github_repo
        )
        btn_open_gh.pack(side="left", padx=(0, 6))

        btn_rel_gh = tk.Button(
            self.repo_toolbar, text="🏷️ Создать релиз", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=8, pady=4, cursor="hand2", command=self._open_github_new_release
        )
        btn_rel_gh.pack(side="left", padx=(0, 6))

        btn_repo_local = tk.Button(
            self.repo_toolbar, text="📥 Установить свой .ZIP с ПК", bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, cursor="hand2", command=self._install_local_zip
        )
        btn_repo_local.pack(side="right")

        # 4. Main Workspace Split (Table on Left, Preview Card on Right)
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        # Left Frame: Table
        self.left_frame = ttk.LabelFrame(paned, text=" Каталог ресурс-паков ")
        paned.add(self.left_frame, minsize=380, width=540)

        cols = ("col1", "col2", "col3")
        self.pack_tree = ttk.Treeview(self.left_frame, columns=cols, show="headings", height=10)
        sb = ttk.Scrollbar(self.left_frame, command=self.pack_tree.yview)
        self.pack_tree.configure(yscrollcommand=sb.set)
        self.pack_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.pack_tree.bind("<<TreeviewSelect>>", self._on_pack_select)
        self.pack_tree.bind("<ButtonRelease-1>", self._on_pack_select)
        self.pack_tree.bind("<Double-1>", lambda e: self._download_selected())

        # Right Frame: Preview Card
        self.right_frame = ttk.LabelFrame(paned, text=" Предпросмотр и скриншот ")
        paned.add(self.right_frame, minsize=420)

        card_inner = tk.Frame(self.right_frame, bg=SURFACE, padx=14, pady=10)
        card_inner.pack(fill="both", expand=True)

        self.card_title = tk.Label(
            card_inner, text="Выберите текстур-пак слева", bg=SURFACE, fg=ACCENT,
            font=("Segoe UI", 12, "bold"), wraplength=400, justify="left"
        )
        self.card_title.pack(anchor="w")

        self.card_meta = tk.Label(
            card_inner, text="Размер: --  •  Категория: --", bg=SURFACE, fg=SUBTEXT,
            font=("Segoe UI", 9)
        )
        self.card_meta.pack(anchor="w", pady=(2, 8))

        # Screenshot display box (360x200)
        img_box = tk.Frame(card_inner, width=360, height=200, bg="#242638", highlightthickness=1, highlightbackground="#45475a")
        img_box.pack_propagate(False)
        img_box.pack(pady=(0, 4))

        self.card_img_lbl = tk.Label(
            img_box, bg="#242638", fg=SUBTEXT, font=("Segoe UI", 10), justify="center", wraplength=320, cursor="hand2",
            text="📁 Выберите текстур-пак слева\n\nЗдесь появится скриншот или иконка"
        )
        self.card_img_lbl.pack(fill="both", expand=True)
        self.card_img_lbl.bind("<Button-1>", lambda e: self._on_screenshot_click())
        img_box.bind("<Button-1>", lambda e: self._on_screenshot_click())

        self.card_hint_lbl = tk.Label(
            card_inner, text="Кликните на скриншот, чтобы увеличить его", bg=SURFACE, fg=SUBTEXT,
            font=("Segoe UI", 8)
        )
        self.card_hint_lbl.pack(pady=(0, 6))

        # Description text
        desc_box = tk.Frame(card_inner, bg=SURFACE)
        desc_box.pack(fill="x", pady=(0, 8))
        self.card_desc = tk.Text(
            desc_box, height=3, bg=BG, fg=TEXT, font=("Segoe UI", 9),
            relief="flat", wrap="word", state="disabled", padx=8, pady=6
        )
        self.card_desc.pack(fill="x")

        # Action buttons
        btn_row = tk.Frame(card_inner, bg=SURFACE)
        btn_row.pack(fill="x", pady=(4, 0))

        self.btn_download = tk.Button(
            btn_row, text="⚡ Скачать и установить в Minecraft",
            bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6, cursor="hand2",
            state="disabled", command=self._download_selected
        )
        self.btn_download.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_download_other = tk.Button(
            btn_row, text="📁 В другую папку...", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=10, pady=6, cursor="hand2",
            state="disabled", command=self._download_selected_other
        )
        self.btn_download_other.pack(side="left")

        # 5. Progress Card
        self.prog_card = tk.Frame(self, bg=SURFACE, padx=16, pady=6)
        self.prog_card.pack(fill="x", padx=14, pady=(0, 6))

        self.prog_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(self.prog_card, variable=self.prog_var, maximum=100)
        self.prog_bar.pack(fill="x", pady=(0, 2))

        self.prog_lbl = tk.Label(self.prog_card, text="Выберите пак в таблице и нажмите кнопку установки.", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9))
        self.prog_lbl.pack(anchor="w")

        # 6. Bottom Instruction / Tip Card
        self.tip_frame = tk.Frame(self, bg="#242638", padx=14, pady=8, highlightthickness=1, highlightbackground="#45475a")
        self.tip_frame.pack(fill="x", padx=14, pady=(0, 8))
        self.tip_lbl = tk.Label(
            self.tip_frame, text="", bg="#242638", fg=TEXT, font=("Segoe UI", 9), justify="left"
        )
        self.tip_lbl.pack(anchor="w")

    def _set_mode(self, mode):
        self.mode = mode
        if mode == "favorites":
            self.btn_mode_fav.configure(bg=ACCENT, fg="#1e1e2e", font=("Segoe UI", 10, "bold"))
            self.btn_mode_repo.configure(bg="#313244", fg=TEXT, font=("Segoe UI", 10))

            self.hdr_title.config(text="⭐ Избранные проверенные текстур-паки с GitHub")
            self.hdr_sub.config(text="Коллекция лучших проверенных наборов текстур. Выберите любой пак, оцените скриншот и установите в игру в 1 клик!")

            self.repo_toolbar.pack_forget()
            self.fav_toolbar.pack(fill="x")

            self.left_frame.config(text=" Избранная коллекция ресурс-паков ")
            self.pack_tree.heading("col1", text="Название пака")
            self.pack_tree.heading("col2", text="Категория")
            self.pack_tree.heading("col3", text="Размер")
            self.pack_tree.column("col1", width=240, anchor="w")
            self.pack_tree.column("col2", width=150, anchor="w")
            self.pack_tree.column("col3", width=80, anchor="center")

            self.tip_lbl.config(
                text="💡 Выберите любой пак из списка выше — справа сразу отобразится его скриншот, описание и кнопка быстрой установки в Minecraft!"
            )
            self._filter_favorites()
        else:
            self.btn_mode_repo.configure(bg=ACCENT, fg="#1e1e2e", font=("Segoe UI", 10, "bold"))
            self.btn_mode_fav.configure(bg="#313244", fg=TEXT, font=("Segoe UI", 10))

            self.hdr_title.config(text="📦 Текстур-паки из вашего GitHub репозитория")
            self.hdr_sub.config(text="Приложение автоматически ищет .zip архивы и скриншоты 1.png / 1.jpg рядом с ними в вашем личном репозитории.")

            self.fav_toolbar.pack_forget()
            self.repo_toolbar.pack(fill="x")

            self.left_frame.config(text=" Список файлов в вашем репозитории ")
            self.pack_tree.heading("col1", text="Название архива")
            self.pack_tree.heading("col2", text="Размер")
            self.pack_tree.heading("col3", text="Раздел / Папка")
            self.pack_tree.column("col1", width=240, anchor="w")
            self.pack_tree.column("col2", width=85, anchor="center")
            self.pack_tree.column("col3", width=160, anchor="w")

            self.tip_lbl.config(
                text="💡 Как закинуть паки и скриншоты в свой репозиторий:\n"
                     "• Нажмите «🏷️ Создать релиз», прикрепите .zip архив и рядом скриншот 1.png (или 1.jpg).\n"
                     "• Либо создайте папку packs/ИмяПака/ и загрузите .zip и 1.png туда. Затем нажмите «🔄 Обновить список»!"
            )
            if not self._repo_loaded:
                self._load_repo_packs()
            else:
                self._displayed_packs = list(self._repo_packs)
                self._render_table()

    def _clear_fav_search(self):
        self.search_fav.set("")
        self._filter_favorites()

    def _filter_favorites(self, *_):
        cat = self.cat_var.get()
        q = self.search_fav.get().strip().lower()
        res = []
        for p in CURATED_FAVORITE_PACKS:
            if cat != "Все категории" and p.get("category") != cat:
                continue
            if q and (q not in p.get("name", "").lower() and q not in p.get("desc", "").lower() and q not in p.get("category", "").lower()):
                continue
            res.append(p)
        self._displayed_packs = res
        self._render_table()
        self.set_status(f"Показано {len(res)} избранных текстур-паков")

    def _open_github_repo(self):
        repo = self.repo_var.get().strip() or DEFAULT_GITHUB_REPO
        webbrowser.open(f"https://github.com/{repo}")

    def _open_github_new_release(self):
        repo = self.repo_var.get().strip() or DEFAULT_GITHUB_REPO
        webbrowser.open(f"https://github.com/{repo}/releases/new")

    def _load_repo_packs(self):
        repo = self.repo_var.get().strip() or DEFAULT_GITHUB_REPO
        try:
            (Path.home() / ".mctexturereplacer_repo.txt").write_text(repo, encoding="utf-8")
        except Exception:
            pass
        self.set_status("Загрузка списка паков с GitHub...")
        self.prog_lbl.config(text=f"Поиск архивов и скриншотов в репозитории {repo}...")
        threading.Thread(target=self._bg_load_repo, daemon=True).start()

    def _bg_load_repo(self):
        repo = self.repo_var.get().strip() or DEFAULT_GITHUB_REPO
        packs = fetch_github_packs(repo)
        self._repo_packs = packs
        self._repo_loaded = True
        self.after(0, self._on_repo_loaded)

    def _on_repo_loaded(self):
        if self.mode == "my_repo":
            self._displayed_packs = list(self._repo_packs)
            self._render_table()

    def _render_table(self):
        self.pack_tree.delete(*self.pack_tree.get_children())
        if not self._displayed_packs:
            if self.mode == "favorites":
                self.card_title.config(text="Ничего не найдено")
                self.card_meta.config(text="Попробуйте изменить запрос")
                self.card_img_lbl.config(image="", text="🔍 По вашему запросу ничего не найдено")
                self.card_hint_lbl.config(text="")
                self.card_desc.configure(state="normal")
                self.card_desc.delete("1.0", "end")
                self.card_desc.insert("1.0", "Выберите другую категорию или очистите строку поиска.")
                self.card_desc.configure(state="disabled")
                self.btn_download.config(state="disabled")
                self.btn_download_other.config(state="disabled")
            else:
                self.set_status("Репозиторий пока пуст")
                self.prog_lbl.config(text="В вашем репозитории пока нет паков. Загрузите файлы на GitHub и нажмите «Обновить список».")
                self.card_title.config(text="Репозиторий пока пуст")
                self.card_meta.config(text="Архивы не найдены")
                self.card_img_lbl.config(image="", text="📁 В вашем репозитории пока нет текстур-паков\n\nНажмите кнопку «Создать релиз» выше\nи загрузите ваш .zip пак и скриншот 1.png!\n\n(Или переключитесь на «⭐ Избранные паки»)")
                self.card_hint_lbl.config(text="")
                self.card_desc.configure(state="normal")
                self.card_desc.delete("1.0", "end")
                self.card_desc.insert("1.0", "Чтобы паки появились здесь, создайте новый релиз в репозитории на GitHub и прикрепите туда .zip архив и скриншот 1.png (или 1.jpg).")
                self.card_desc.configure(state="disabled")
                self.btn_download.config(state="disabled", text="⚡ Скачать и установить в Minecraft")
                self.btn_download_other.config(state="disabled")
            return

        for i, p in enumerate(self._displayed_packs):
            if self.mode == "favorites":
                self.pack_tree.insert(
                    "", "end", iid=str(i),
                    values=(p.get("name", ""), p.get("category", ""), p.get("size", "--"))
                )
            else:
                self.pack_tree.insert(
                    "", "end", iid=str(i),
                    values=(p.get("name", ""), p.get("size", "--"), p.get("source", "GitHub"))
                )

        if self.mode == "favorites":
            self.prog_lbl.config(text=f"Доступно {len(self._displayed_packs)} избранных паков. Выберите пак для просмотра и установки.")
        else:
            self.set_status(f"Загружено {len(self._displayed_packs)} паков из репозитория")
            self.prog_lbl.config(text=f"Найдено {len(self._displayed_packs)} текстур-паков в вашем репозитории.")

        # Auto-select first item
        self.pack_tree.selection_set("0")
        self.pack_tree.focus("0")
        self._on_pack_select()

    def _on_pack_select(self, event=None):
        sel = self.pack_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._displayed_packs):
            return
        pack = self._displayed_packs[idx]
        self._selected_pack = pack

        self._preview_id += 1
        req_id = self._preview_id

        # Update card UI
        self.card_title.config(text=pack.get("name", "Ресурспак"))
        cat_or_src = pack.get("category") or pack.get("source", "")
        self.card_meta.config(text=f"📦 Размер: {pack.get('size', '--')}  •  {cat_or_src}")

        self.card_desc.configure(state="normal")
        self.card_desc.delete("1.0", "end")
        self.card_desc.insert("1.0", pack.get("desc", ""))
        self.card_desc.configure(state="disabled")

        self.btn_download.config(state="normal", text="⚡ Скачать и установить в Minecraft")
        self.btn_download_other.config(state="normal")

        # Show loading placeholder
        self.card_img_lbl.config(image="", text="⏳ Загрузка превью...")
        self.card_hint_lbl.config(text="Пожалуйста, подождите...")
        self._full_screenshot_pil = None

        threading.Thread(target=self._bg_load_screenshot, args=(pack, req_id), daemon=True).start()

    def _bg_load_screenshot(self, pack, req_id):
        img = None
        img_url = pack.get("image_url", "")
        if img_url:
            img = fetch_image_pil(img_url)

        # Try candidate URLs if not found
        if not img and pack.get("candidate_img_urls"):
            for cand_url in pack.get("candidate_img_urls", []):
                img = fetch_image_pil(cand_url)
                if img:
                    pack["image_url"] = cand_url
                    break

        if req_id != self._preview_id:
            return

        self.after(0, lambda: self._apply_screenshot(img, pack, req_id))

    def _apply_screenshot(self, img, pack, req_id):
        if req_id != self._preview_id:
            return

        if img:
            max_w, max_h = 360, 200
            img_ratio = img.width / max(1, img.height)
            box_ratio = max_w / max_h
            if img_ratio > box_ratio:
                new_w = max_w
                new_h = max(1, int(max_w / img_ratio))
            else:
                new_h = max_h
                new_w = max(1, int(max_h * img_ratio))
            resized = img.resize((new_w, new_h), Image.LANCZOS)

            bg_card = Image.new("RGBA", (max_w, max_h), (36, 38, 56, 255))
            offset_x = (max_w - new_w) // 2
            offset_y = (max_h - new_h) // 2
            bg_card.paste(resized, (offset_x, offset_y), resized if resized.mode == "RGBA" else None)

            ph = ImageTk.PhotoImage(bg_card)
            self._current_screenshot_ph = ph
            self.card_img_lbl.config(image=ph, text="")
            self.card_hint_lbl.config(text="🔍 Кликните по скриншоту, чтобы открыть в полном размере")
            self._full_screenshot_pil = img
        else:
            msg = ("📷 Скриншот 1.png / 1.jpg не найден\n\nПоложите 1.png или 1.jpg рядом с файлом на GitHub"
                   if self.mode == "my_repo" else "📷 Превью временно недоступно")
            self.card_img_lbl.config(image="", text=msg)
            self.card_hint_lbl.config(text="")
            self._full_screenshot_pil = None

    def _on_screenshot_click(self):
        if not self._full_screenshot_pil:
            return
        def save_and_open():
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                self._full_screenshot_pil.save(tmp, "PNG")
                os.startfile(tmp)
            except Exception:
                pass
        threading.Thread(target=save_and_open, daemon=True).start()

    def _download_selected(self):
        sel = self.pack_tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите текстур-пак в таблице!")
            return
        idx = int(sel[0])
        pack = self._displayed_packs[idx]
        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Ошибка", f"Папка .minecraft не найдена:\n{mc}")
            return
        rp = mc / "resourcepacks"
        rp.mkdir(parents=True, exist_ok=True)
        self._start_download(pack, rp, is_mc=True)

    def _download_selected_other(self):
        sel = self.pack_tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите текстур-пак в таблице!")
            return
        idx = int(sel[0])
        pack = self._displayed_packs[idx]
        d = filedialog.askdirectory(title="Выберите папку для сохранения")
        if not d: return
        self._start_download(pack, Path(d), is_mc=False)

    def _start_download(self, pack, dest_dir, is_mc=True):
        if self._is_downloading:
            messagebox.showinfo("Загрузка", "Уже идет скачивание файла. Дождитесь завершения.")
            return
        self._is_downloading = True
        self.prog_var.set(0)
        pname = pack.get("name", "пака")
        self.prog_lbl.config(text=f"Скачивание {pname}...")
        self.set_status(f"Скачивание: {pname}...")

        def worker():
            def prog_cb(done, total):
                if total > 0:
                    pct = done / total * 100
                    mb_done = done / (1024 * 1024)
                    mb_tot  = total / (1024 * 1024)
                    self.after(0, lambda: (
                        self.prog_var.set(pct),
                        self.prog_lbl.config(text=f"Скачивание: {mb_done:.1f} MB / {mb_tot:.1f} MB ({pct:.0f}%) — {pname}")
                    ))
                else:
                    mb_done = done / (1024 * 1024)
                    self.after(0, lambda: (
                        self.prog_var.set(50),
                        self.prog_lbl.config(text=f"Скачано: {mb_done:.1f} MB...")
                    ))
            try:
                url = pack.get("url", "")
                saved = download_universal_pack(url, dest_dir, prog_cb)
                self.after(0, lambda: self._on_download_success(saved, is_mc))
            except Exception as e:
                self.after(0, lambda: self._on_download_error(str(e), pack.get("url", "")))
            finally:
                self._is_downloading = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_success(self, saved_path, is_mc):
        self.prog_var.set(100)
        self.prog_lbl.config(text=f"✅ Успешно скачано и установлено: {saved_path.name}")
        self.set_status(f"Установлено: {saved_path.name}")
        if is_mc:
            messagebox.showinfo(
                "Готово! Текстурпак установлен",
                f"Ресурспак «{saved_path.name}» успешно скачан и добавлен в Minecraft!\n\n"
                f"Как включить в игре:\n"
                f"1. Откройте Minecraft ➔ Настройки ➔ Наборы ресурсов (Resource Packs)\n"
                f"2. Переместите «{saved_path.name}» стрелочкой вправо ➔ «Готово»!\n\n"
                f"(Если игра уже запущена, нажмите F3 + T для мгновенной перезагрузки текстур)"
            )
        else:
            messagebox.showinfo("Готово!", f"Файл сохранен в:\n{saved_path}")

    def _on_download_error(self, err_msg, url):
        self.prog_var.set(0)
        self.prog_lbl.config(text=f"❌ Ошибка скачивания: {err_msg}")
        self.set_status("Ошибка скачивания", err=True)
        ans = messagebox.askyesno(
            "Ошибка скачивания",
            f"Не удалось скачать файл автоматически с GitHub:\n{err_msg}\n\n"
            f"Открыть ссылку в браузере, чтобы скачать вручную?\n"
            f"(После скачивания нажмите кнопку «Установить свой .ZIP с ПК»)"
        )
        if ans:
            webbrowser.open(url)

    def _install_local_zip(self):
        path = filedialog.askopenfilename(
            title="Выберите архив с текстурпаком (.zip)",
            filetypes=[("ZIP архивы", "*.zip *.jar"), ("Все файлы", "*.*")]
        )
        if not path: return
        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Ошибка", f"Папка .minecraft не найдена:\n{mc}")
            return
        rp = mc / "resourcepacks"
        rp.mkdir(parents=True, exist_ok=True)
        dest = rp / Path(path).name
        try:
            shutil.copy2(path, dest)
            self.set_status(f"Установлено: {dest.name}")
            messagebox.showinfo(
                "Готово! Текстурпак установлен",
                f"Файл «{dest.name}» успешно скопирован в папку resourcepacks!\n\n"
                f"Как включить в игре:\n"
                f"1. Откройте Minecraft ➔ Настройки ➔ Наборы ресурсов (Resource Packs)\n"
                f"2. Переместите «{dest.name}» стрелочкой вправо ➔ «Готово»!\n\n"
                f"(Если игра уже запущена, нажмите F3 + T для мгновенной перезагрузки)"
            )
        except Exception as e:
            messagebox.showerror("Ошибка копирования", str(e))

# ── Curated Shaders Collection ────────────────────────────────────────────────
CURATED_SHADER_CATEGORIES = [
    "Все шейдеры",
    "⚡ Для слабых ПК (Высокий FPS)",
    "💎 Ванильный стиль",
    "🌊 Реализм и вода",
    "🎨 Яркие и сочные",
    "🎬 Кинематографичные",
    "✨ Фэнтези и магия",
    "🌌 Космос и эффекты",
    "⏳ Ретро-шейдеры"
]

CURATED_SHADERS = [
    {
        "name": "Complementary Reimagined",
        "category": "💎 Ванильный стиль",
        "size": "0.5 MB",
        "versions": "MC 1.7.2 - 1.21+ (Iris / OptiFine)",
        "performance": "🟡 Средняя нагрузка (Оптимальный баланс)",
        "url": "https://cdn.modrinth.com/data/HVnmMxH1/versions/Bqen1mJX/ComplementaryReimagined_r5.9.3.zip",
        "image_url": "https://cdn.modrinth.com/data/HVnmMxH1/79cb7c8123bbc54945305b2ebad6b8881efdf5f8_96.webp",
        "desc": "Самый знаменитый и популярный шейдер в мире! Идеально сохраняет ванильный дух Minecraft, добавляя превосходное мягкое освещение, чистую воду, тени и красивый солнечный свет."
    },
    {
        "name": "MakeUp - Ultra Fast",
        "category": "⚡ Для слабых ПК (Высокий FPS)",
        "size": "0.4 MB",
        "versions": "MC 1.12 - 1.21+ (Iris / OptiFine)",
        "performance": "🟢 Минимальная нагрузка (Максимальный FPS)",
        "url": "https://cdn.modrinth.com/data/izsIPI7a/versions/T3EhqZo1/MakeUp-UltraFast-9.5e.zip",
        "image_url": "https://cdn.modrinth.com/data/izsIPI7a/a08432baa86b8ffd58c08f4b3a001ef976ff764d_96.webp",
        "desc": "Специальный ультра-быстрый шейдер для слабых компьютеров и ноутбуков! Позволяет получить реалистичные тени, покачивание травы и красивую воду без просадки FPS."
    },
    {
        "name": "BSL Shaders",
        "category": "🎨 Яркие и сочные",
        "size": "1.1 MB",
        "versions": "MC 1.7.2 - 1.21+ (Iris / OptiFine)",
        "performance": "🟡 Средняя нагрузка (Отличная оптимизация)",
        "url": "https://cdn.modrinth.com/data/Q1vvjJYV/versions/yFTiE1Nc/BSL_v10.1.5.zip",
        "image_url": "https://cdn.modrinth.com/data/Q1vvjJYV/2a611a3cb434fb52fb81fa5dace13c5d8b67e55d_96.webp",
        "desc": "Легендарный шейдер-пак с сочными тёплыми красками, реалистичной прозрачной водой, динамическим туманом и мягким солнечным светом."
    },
    {
        "name": "Complementary Unbound",
        "category": "🌊 Реализм и вода",
        "size": "0.5 MB",
        "versions": "MC 1.7.2 - 1.21+ (Iris / OptiFine)",
        "performance": "🔴 Высокая нагрузка (Ультра-реализм)",
        "url": "https://cdn.modrinth.com/data/R6NEzAwj/versions/B1kyfoUZ/ComplementaryUnbound_r5.9.3.zip",
        "image_url": "https://cdn.modrinth.com/data/R6NEzAwj/c85ce4049aac76360d2cd24fd9a7003de01ef312_96.webp",
        "desc": "Версия Complementary для любителей максимального реализма: физически корректное освещение, зеркальные отражения на воде и блоках, реалистичные волны."
    },
    {
        "name": "Photon Shaders",
        "category": "🎬 Кинематографичные",
        "size": "3.6 MB",
        "versions": "MC 1.16.5 - 1.21+ (Iris / OptiFine)",
        "performance": "🟡 Средне-высокая нагрузка",
        "url": "https://cdn.modrinth.com/data/lLqFfGNs/versions/gUv7fBPN/photon_v1.3b.zip",
        "image_url": "https://cdn.modrinth.com/data/lLqFfGNs/39cb5f12e7dcc68d6cb666f225fcb2b801dd70fb_96.webp",
        "desc": "Современный полуреалистичный шейдер, созданный специально для комфортного выживания. Объёмные 3D-облака, мягкие тени и кинематографичная цветокоррекция."
    },
    {
        "name": "Solas Shader",
        "category": "✨ Фэнтези и магия",
        "size": "1.2 MB",
        "versions": "MC 1.16.5 - 1.21+ (Iris / OptiFine)",
        "performance": "🟡 Средняя нагрузка",
        "url": "https://cdn.modrinth.com/data/EpQFjzrQ/versions/KcfQaN5J/Solas%20Shader%20V3.7b.zip",
        "image_url": "https://cdn.modrinth.com/data/EpQFjzrQ/e3efc6ba7a63f9e1cf473a794d0224a6daf243c7_96.webp",
        "desc": "Фэнтезийный шейдер с потрясающим цветным освещением! Факелы, лава, светящиеся ягоды и зелья озаряют пещеры и постройки волшебными оттенками."
    },
    {
        "name": "Bliss Shaders",
        "category": "🎬 Кинематографичные",
        "size": "1.7 MB",
        "versions": "MC 1.16.5 - 1.21+ (Iris / Oculus)",
        "performance": "🟡 Средняя нагрузка",
        "url": "https://cdn.modrinth.com/data/ZvMtQlho/versions/kC2Y8q1P/Bliss_v2.1.2_%28Chocapic13_Shaders_edit%29.zip",
        "image_url": "https://cdn.modrinth.com/data/ZvMtQlho/90145c971ea24387775108fc86c89bed9bd2c8f1_96.webp",
        "desc": "Невероятно атмосферный шейдер с динамической погодой: густые утренние туманы в низинах, реалистичные грозы и живые закаты."
    },
    {
        "name": "AstraLex Shaders",
        "category": "🌌 Космос и эффекты",
        "size": "3.0 MB",
        "versions": "MC 1.14 - 1.21+ (Iris / OptiFine)",
        "performance": "🔴 Высокая нагрузка (Множество эффектов)",
        "url": "https://cdn.modrinth.com/data/RphJSnEs/versions/qSbtQS2o/%C2%A7r%C2%A7lAstra%C2%A74%C2%A7lLex%C2%A7r%C2%A7l_By_LexBoosT_%C2%A74%C2%A7lV93.0%C2%A7r%C2%A7l.zip",
        "image_url": "https://cdn.modrinth.com/data/RphJSnEs/3e25ea407447bf2ff8ffa8926cd2db295307cf68_96.webp",
        "desc": "Шейдер с потрясающим ночным небом: северное полярное сияние, яркие созвездия, галактики, падающие звёзды и кинематографичные лучи солнца."
    },
    {
        "name": "Nostalgia Shader",
        "category": "⏳ Ретро-шейдеры",
        "size": "1.8 MB",
        "versions": "MC 1.14 - 1.21+ (Iris / OptiFine)",
        "performance": "🟡 Средняя нагрузка",
        "url": "https://cdn.modrinth.com/data/xEItlMn3/versions/fzxeGgx7/Nostalgia_v5.1.zip",
        "image_url": "https://cdn.modrinth.com/data/xEItlMn3/49ba53348dd4902ad2a3ae49cc643550ead201bc.png",
        "desc": "Воссоздаёт тёплую и уютную визуальную атмосферу первых классических шейдеров 2012-2015 годов на современном движке."
    },
    {
        "name": "Miniature Shader",
        "category": "⚡ Для слабых ПК (Высокий FPS)",
        "size": "0.1 MB",
        "versions": "MC 1.12 - 1.21+ (Iris / OptiFine)",
        "performance": "🟢 Ультра-легкий (Работает везде)",
        "url": "https://cdn.modrinth.com/data/UaS8ROxa/versions/LWmZ94RG/miniature-shader-2.19.zip",
        "image_url": "https://cdn.modrinth.com/data/UaS8ROxa/85f373314addaf840d9c8667c797da6e0f7e7034_96.webp",
        "desc": "Минималистичный микро-шейдер. Добавляет аккуратные тени и отражения на воде практически без потери кадров в секунду."
    }
]

# ── Tab 3: Shaderpacks ────────────────────────────────────────────────────────
class ShaderTab(tk.Frame):
    def __init__(self, parent, mc_path_var, status_fn):
        super().__init__(parent, bg=BG)
        self.mc_path_var = mc_path_var
        self.set_status = status_fn

        self._displayed_shaders = []
        self._is_downloading = False
        self._selected_shader = None
        self._preview_id = 0
        self._current_screenshot_ph = None
        self._full_screenshot_pil = None

        self._build()
        self.after(150, self._filter_shaders)

    def _build(self):
        # 1. Header Banner
        hdr = tk.Frame(self, bg=SURFACE, padx=16, pady=9)
        hdr.pack(fill="x", padx=14, pady=(10, 8))

        tk.Label(
            hdr, text="☀️ Шейдеры для Minecraft (Shaderpacks)",
            bg=SURFACE, fg=ACCENT, font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Коллекция лучших мировых шейдеров. Добавляют реалистичное освещение, тени, живую воду и солнце.\n"
                 "Скачиваются и устанавливаются в папку «.minecraft/shaderpacks» в 1 клик!",
            bg=SURFACE, fg=TEXT, font=("Segoe UI", 9), justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Filter & Actions Toolbar
        bar = tk.Frame(self, bg=SURFACE, padx=12, pady=7, highlightthickness=1, highlightbackground="#45475a")
        bar.pack(fill="x", padx=14, pady=(0, 8))

        tk.Label(bar, text="Категория:", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.cat_var = tk.StringVar(value="Все шейдеры")
        self.cat_cb = ttk.Combobox(bar, textvariable=self.cat_var, values=CURATED_SHADER_CATEGORIES, state="readonly", width=25)
        self.cat_cb.pack(side="left", padx=(6, 12))
        self.cat_cb.bind("<<ComboboxSelected>>", self._filter_shaders)

        tk.Label(bar, text="Поиск:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.search_var = tk.StringVar()
        s_ent = tk.Entry(bar, textvariable=self.search_var, width=20, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        s_ent.pack(side="left", padx=(6, 6))
        s_ent.bind("<KeyRelease>", self._filter_shaders)

        btn_clear = tk.Button(
            bar, text="✕", bg="#313244", fg=SUBTEXT, activebackground="#45475a",
            font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2, cursor="hand2",
            command=self._clear_search
        )
        btn_clear.pack(side="left", padx=(0, 10))

        btn_local = tk.Button(
            bar, text="📥 Установить свой шейдер (.ZIP) с ПК", bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, cursor="hand2", command=self._install_local_zip
        )
        btn_local.pack(side="right")

        # 3. Main Workspace Split (Table on Left, Preview Card on Right)
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        # Left Frame: Table
        self.left_frame = ttk.LabelFrame(paned, text=" Каталог шейдеров ")
        paned.add(self.left_frame, minsize=380, width=530)

        cols = ("col1", "col2", "col3")
        self.pack_tree = ttk.Treeview(self.left_frame, columns=cols, show="headings", height=10)
        self.pack_tree.heading("col1", text="Название шейдера")
        self.pack_tree.heading("col2", text="Категория")
        self.pack_tree.heading("col3", text="Размер")
        self.pack_tree.column("col1", width=230, anchor="w")
        self.pack_tree.column("col2", width=160, anchor="w")
        self.pack_tree.column("col3", width=80, anchor="center")

        sb = ttk.Scrollbar(self.left_frame, command=self.pack_tree.yview)
        self.pack_tree.configure(yscrollcommand=sb.set)
        self.pack_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.pack_tree.bind("<<TreeviewSelect>>", self._on_shader_select)
        self.pack_tree.bind("<ButtonRelease-1>", self._on_shader_select)
        self.pack_tree.bind("<Double-1>", lambda e: self._download_selected())

        # Right Frame: Preview Card
        self.right_frame = ttk.LabelFrame(paned, text=" Предпросмотр и параметры шейдера ")
        paned.add(self.right_frame, minsize=430)

        card_inner = tk.Frame(self.right_frame, bg=SURFACE, padx=14, pady=10)
        card_inner.pack(fill="both", expand=True)

        self.card_title = tk.Label(
            card_inner, text="Выберите шейдер слева", bg=SURFACE, fg=ACCENT,
            font=("Segoe UI", 12, "bold"), wraplength=410, justify="left"
        )
        self.card_title.pack(anchor="w")

        self.card_meta = tk.Label(
            card_inner, text="Размер: --  •  Категория: --", bg=SURFACE, fg=SUBTEXT,
            font=("Segoe UI", 9)
        )
        self.card_meta.pack(anchor="w", pady=(2, 8))

        # Screenshot display box (360x190)
        img_box = tk.Frame(card_inner, width=360, height=190, bg="#242638", highlightthickness=1, highlightbackground="#45475a")
        img_box.pack_propagate(False)
        img_box.pack(pady=(0, 4))

        self.card_img_lbl = tk.Label(
            img_box, bg="#242638", fg=SUBTEXT, font=("Segoe UI", 10), justify="center", wraplength=320, cursor="hand2",
            text="☀️ Выберите шейдер слева\n\nЗдесь появится обложка"
        )
        self.card_img_lbl.pack(fill="both", expand=True)
        self.card_img_lbl.bind("<Button-1>", lambda e: self._on_screenshot_click())
        img_box.bind("<Button-1>", lambda e: self._on_screenshot_click())

        self.card_hint_lbl = tk.Label(
            card_inner, text="Кликните на обложку, чтобы увеличить", bg=SURFACE, fg=SUBTEXT,
            font=("Segoe UI", 8)
        )
        self.card_hint_lbl.pack(pady=(0, 6))

        # Description text
        desc_box = tk.Frame(card_inner, bg=SURFACE)
        desc_box.pack(fill="x", pady=(0, 6))
        self.card_desc = tk.Text(
            desc_box, height=3, bg=BG, fg=TEXT, font=("Segoe UI", 9),
            relief="flat", wrap="word", state="disabled", padx=8, pady=6
        )
        self.card_desc.pack(fill="x")

        # ── COMPACT COMPATIBILITY & VERSION WARNING BADGE (Right by the install button) ──
        self.compat_box = tk.Frame(card_inner, bg="#2d2a1d", padx=10, pady=6, highlightthickness=1, highlightbackground="#fab387")
        self.compat_box.pack(fill="x", pady=(0, 6))

        self.compat_lbl = tk.Label(
            self.compat_box,
            text="⚠️ Требуется версия: Minecraft 1.16 - 1.21+ (Iris / OptiFine)\n⚡ Для работы шейдеров необходим графический мод",
            bg="#2d2a1d", fg="#fab387", font=("Segoe UI", 9, "bold"), justify="left"
        )
        self.compat_lbl.pack(side="left", fill="x", expand=True)

        self.btn_help = tk.Button(
            self.compat_box, text="❓ Инструкция", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=3, cursor="hand2",
            command=self._show_iris_guide
        )
        self.btn_help.pack(side="right")

        # Action buttons
        btn_row = tk.Frame(card_inner, bg=SURFACE)
        btn_row.pack(fill="x", pady=(2, 0))

        self.btn_download = tk.Button(
            btn_row, text="⚡ Скачать и установить в shaderpacks",
            bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6, cursor="hand2",
            state="disabled", command=self._download_selected
        )
        self.btn_download.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_download_other = tk.Button(
            btn_row, text="📁 В другую папку...", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=10, pady=6, cursor="hand2",
            state="disabled", command=self._download_selected_other
        )
        self.btn_download_other.pack(side="left")

        # 4. Progress Card
        self.prog_card = tk.Frame(self, bg=SURFACE, padx=16, pady=6)
        self.prog_card.pack(fill="x", padx=14, pady=(0, 6))

        self.prog_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(self.prog_card, variable=self.prog_var, maximum=100)
        self.prog_bar.pack(fill="x", pady=(0, 2))

        self.prog_lbl = tk.Label(self.prog_card, text="Выберите шейдер в таблице и нажмите кнопку установки.", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9))
        self.prog_lbl.pack(anchor="w")

        # 5. Bottom Instruction / Tip Card
        self.tip_frame = tk.Frame(self, bg="#242638", padx=14, pady=8, highlightthickness=1, highlightbackground="#45475a")
        self.tip_frame.pack(fill="x", padx=14, pady=(0, 8))
        self.tip_lbl = tk.Label(
            self.tip_frame,
            text="💡 Куда устанавливаются шейдеры: файлы .zip помещаются в папку «.minecraft/shaderpacks».\n"
                 "Для включения в игре: Настройки ➔ Настройки графики ➔ Наборы шейдеров (Shader Packs) ➔ Выберите шейдер и нажмите «Применить».",
            bg="#242638", fg=TEXT, font=("Segoe UI", 9), justify="left"
        )
        self.tip_lbl.pack(anchor="w")

    def _clear_search(self):
        self.search_var.set("")
        self._filter_shaders()

    def _filter_shaders(self, *_):
        cat = self.cat_var.get()
        q = self.search_var.get().strip().lower()
        res = []
        for s in CURATED_SHADERS:
            if cat != "Все шейдеры" and s.get("category") != cat:
                continue
            if q and (q not in s.get("name", "").lower() and q not in s.get("desc", "").lower() and q not in s.get("category", "").lower()):
                continue
            res.append(s)
        self._displayed_shaders = res
        self._render_table()
        self.set_status(f"Показано {len(res)} шейдеров")

    def _render_table(self):
        self.pack_tree.delete(*self.pack_tree.get_children())
        if not self._displayed_shaders:
            self.card_title.config(text="Ничего не найдено")
            self.card_meta.config(text="Попробуйте изменить запрос")
            self.card_img_lbl.config(image="", text="🔍 По вашему запросу ничего не найдено")
            self.card_hint_lbl.config(text="")
            self.card_desc.configure(state="normal")
            self.card_desc.delete("1.0", "end")
            self.card_desc.insert("1.0", "Выберите другую категорию или очистите строку поиска.")
            self.card_desc.configure(state="disabled")
            self.compat_lbl.config(text="Шейдеры не выбраны")
            self.btn_download.config(state="disabled")
            self.btn_download_other.config(state="disabled")
            return

        for i, s in enumerate(self._displayed_shaders):
            self.pack_tree.insert(
                "", "end", iid=str(i),
                values=(s.get("name", ""), s.get("category", ""), s.get("size", "--"))
            )

        self.prog_lbl.config(text=f"Доступно {len(self._displayed_shaders)} шейдеров. Выберите шейдер для просмотра и установки.")

        # Auto-select first item
        self.pack_tree.selection_set("0")
        self.pack_tree.focus("0")
        self._on_shader_select()

    def _on_shader_select(self, event=None):
        sel = self.pack_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._displayed_shaders):
            return
        shader = self._displayed_shaders[idx]
        self._selected_shader = shader

        self._preview_id += 1
        req_id = self._preview_id

        # Update card UI
        self.card_title.config(text=shader.get("name", "Шейдер"))
        self.card_meta.config(text=f"📦 Размер: {shader.get('size', '--')}  •  {shader.get('category', '')}")

        self.card_desc.configure(state="normal")
        self.card_desc.delete("1.0", "end")
        self.card_desc.insert("1.0", shader.get("desc", ""))
        self.card_desc.configure(state="disabled")

        # Update compact compatibility warning badge (right above install button)
        vers = shader.get("versions", "Minecraft 1.16 - 1.21+")
        perf = shader.get("performance", "")
        self.compat_lbl.config(text=f"⚠️ Требуется версия: {vers}\n⚡ Нагрузка на ПК: {perf}")

        self.btn_download.config(state="normal", text="⚡ Скачать и установить в shaderpacks")
        self.btn_download_other.config(state="normal")

        # Show loading placeholder
        self.card_img_lbl.config(image="", text="⏳ Загрузка обложки...")
        self.card_hint_lbl.config(text="Пожалуйста, подождите...")
        self._full_screenshot_pil = None

        threading.Thread(target=self._bg_load_screenshot, args=(shader, req_id), daemon=True).start()

    def _bg_load_screenshot(self, shader, req_id):
        img = None
        img_url = shader.get("image_url", "")
        if img_url:
            img = fetch_image_pil(img_url)

        if req_id != self._preview_id:
            return

        self.after(0, lambda: self._apply_screenshot(img, shader, req_id))

    def _apply_screenshot(self, img, shader, req_id):
        if req_id != self._preview_id:
            return

        if img:
            max_w, max_h = 360, 190
            img_ratio = img.width / max(1, img.height)
            box_ratio = max_w / max_h
            if img_ratio > box_ratio:
                new_w = max_w
                new_h = max(1, int(max_w / img_ratio))
            else:
                new_h = max_h
                new_w = max(1, int(max_h * img_ratio))
            resized = img.resize((new_w, new_h), Image.LANCZOS)

            bg_card = Image.new("RGBA", (max_w, max_h), (36, 38, 56, 255))
            offset_x = (max_w - new_w) // 2
            offset_y = (max_h - new_h) // 2
            bg_card.paste(resized, (offset_x, offset_y), resized if resized.mode == "RGBA" else None)

            ph = ImageTk.PhotoImage(bg_card)
            self._current_screenshot_ph = ph
            self.card_img_lbl.config(image=ph, text="")
            self.card_hint_lbl.config(text="🔍 Кликните по обложке, чтобы открыть в полном размере")
            self._full_screenshot_pil = img
        else:
            self.card_img_lbl.config(image="", text="📷 Обложка временно недоступна")
            self.card_hint_lbl.config(text="")
            self._full_screenshot_pil = None

    def _on_screenshot_click(self):
        if not self._full_screenshot_pil:
            return
        def save_and_open():
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                self._full_screenshot_pil.save(tmp, "PNG")
                os.startfile(tmp)
            except Exception:
                pass
        threading.Thread(target=save_and_open, daemon=True).start()

    def _download_selected(self):
        sel = self.pack_tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите шейдер в таблице!")
            return
        idx = int(sel[0])
        shader = self._displayed_shaders[idx]
        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Ошибка", f"Папка .minecraft не найдена:\n{mc}")
            return
        sp = mc / "shaderpacks"
        sp.mkdir(parents=True, exist_ok=True)
        self._start_download(shader, sp, is_mc=True)

    def _download_selected_other(self):
        sel = self.pack_tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите шейдер в таблице!")
            return
        idx = int(sel[0])
        shader = self._displayed_shaders[idx]
        d = filedialog.askdirectory(title="Выберите папку для сохранения")
        if not d: return
        self._start_download(shader, Path(d), is_mc=False)

    def _start_download(self, shader, dest_dir, is_mc=True):
        if self._is_downloading:
            messagebox.showinfo("Загрузка", "Уже идет скачивание файла. Дождитесь завершения.")
            return
        self._is_downloading = True
        self.prog_var.set(0)
        sname = shader.get("name", "шейдера")
        self.prog_lbl.config(text=f"Скачивание {sname}...")
        self.set_status(f"Скачивание шейдера: {sname}...")

        def worker():
            def prog_cb(done, total):
                if total > 0:
                    pct = done / total * 100
                    mb_done = done / (1024 * 1024)
                    mb_tot  = total / (1024 * 1024)
                    self.after(0, lambda: (
                        self.prog_var.set(pct),
                        self.prog_lbl.config(text=f"Скачивание: {mb_done:.1f} MB / {mb_tot:.1f} MB ({pct:.0f}%) — {sname}")
                    ))
                else:
                    mb_done = done / (1024 * 1024)
                    self.after(0, lambda: (
                        self.prog_var.set(50),
                        self.prog_lbl.config(text=f"Скачано: {mb_done:.1f} MB...")
                    ))
            try:
                url = shader.get("url", "")
                saved = download_universal_pack(url, dest_dir, prog_cb)
                self.after(0, lambda: self._on_download_success(saved, is_mc))
            except Exception as e:
                self.after(0, lambda: self._on_download_error(str(e), shader.get("url", "")))
            finally:
                self._is_downloading = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_success(self, saved_path, is_mc):
        self.prog_var.set(100)
        self.prog_lbl.config(text=f"✅ Успешно скачано и установлено: {saved_path.name}")
        self.set_status(f"Установлен шейдер: {saved_path.name}")
        if is_mc:
            messagebox.showinfo(
                "Готово! Шейдер установлен",
                f"Шейдер-пак «{saved_path.name}» успешно скачан в папку shaderpacks!\n\n"
                f"Как включить в игре:\n"
                f"1. Запустите Minecraft с модом Iris Shaders (рекомендуется) или OptiFine\n"
                f"2. Настройки ➔ Настройки графики ➔ Наборы шейдеров (Shader Packs)\n"
                f"3. Выберите «{saved_path.name}» и нажмите «Применить»!\n\n"
                f"(Если игра уже запущена, шейдер сразу появится в списке)"
            )
        else:
            messagebox.showinfo("Готово!", f"Файл сохранен в:\n{saved_path}")

    def _on_download_error(self, err_msg, url):
        self.prog_var.set(0)
        self.prog_lbl.config(text=f"❌ Ошибка скачивания: {err_msg}")
        self.set_status("Ошибка скачивания шейдера", err=True)
        ans = messagebox.askyesno(
            "Ошибка скачивания",
            f"Не удалось скачать шейдер автоматически:\n{err_msg}\n\n"
            f"Открыть ссылку в браузере, чтобы скачать вручную?\n"
            f"(После скачивания нажмите кнопку «Установить свой шейдер (.ZIP) с ПК»)"
        )
        if ans:
            webbrowser.open(url)

    def _install_local_zip(self):
        path = filedialog.askopenfilename(
            title="Выберите архив с шейдером (.zip)",
            filetypes=[("ZIP архивы", "*.zip"), ("Все файлы", "*.*")]
        )
        if not path: return
        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Ошибка", f"Папка .minecraft не найдена:\n{mc}")
            return
        sp = mc / "shaderpacks"
        sp.mkdir(parents=True, exist_ok=True)
        dest = sp / Path(path).name
        try:
            shutil.copy2(path, dest)
            self.set_status(f"Установлен шейдер: {dest.name}")
            messagebox.showinfo(
                "Готово! Шейдер установлен",
                f"Шейдер-пак «{dest.name}» успешно скопирован в папку shaderpacks!\n\n"
                f"Как включить в игре:\n"
                f"1. Откройте Minecraft (с Iris или OptiFine)\n"
                f"2. Настройки графики ➔ Наборы шейдеров (Shader Packs)\n"
                f"3. Выберите «{dest.name}» и нажмите «Применить»!"
            )
        except Exception as e:
            messagebox.showerror("Ошибка копирования", str(e))

    def _show_iris_guide(self):
        messagebox.showinfo(
            "Инструкция: Как запустить шейдеры в игре",
            "Для работы шейдеров в Minecraft нужен мод на шейдеры:\n\n"
            "1. Рекомендуемый мод: «Iris Shaders» (для Fabric / NeoForge)\n"
            "   • Скачивается в любом лаунчере (TLauncher, Prism, Modrinth) в 1 клик\n"
            "   • Даёт самый высокий FPS и поддерживает 99% шейдеров\n\n"
            "2. Альтернатива: «OptiFine» (для Forge / Ванилла)\n"
            "   • Классический мод со встроенной поддержкой шейдеров\n\n"
            "3. Активация в игре:\n"
            "   • Настройки ➔ Настройки графики ➔ Наборы шейдеров (Shader Packs)\n"
            "   • Выберите скачанный шейдер и нажмите «Применить»!"
        )

# ── Sound Infrastructure & Tab ────────────────────────────────────────────────
def load_minecraft_sound_index(mc_path):
    mc_path = Path(mc_path)
    idx_dir = mc_path / "assets" / "indexes"
    obj_dir = mc_path / "assets" / "objects"
    if not idx_dir.exists():
        return None, {}

    json_files = list(idx_dir.glob("*.json"))
    if not json_files:
        return None, {}

    def sort_key(p):
        stem = p.stem
        try:
            return (int(stem), p.stat().st_mtime)
        except ValueError:
            return (0, p.stat().st_mtime)

    # Sort so oldest are first, then newest overwrite with most up-to-date mappings
    json_files.sort(key=sort_key)

    sounds = {}
    last_idx_name = json_files[-1].name
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            objects = data.get("objects", {})
            for k, v in objects.items():
                if k.startswith("minecraft/sounds/") and k.endswith(".ogg"):
                    rel_path = k[len("minecraft/sounds/"):]
                    h = v.get("hash", "")
                    size = v.get("size", 0)
                    disk_file = None
                    if h:
                        cand = obj_dir / h[:2] / h
                        if cand.exists():
                            disk_file = cand
                    # If already seen but current has existing disk file, prefer one with disk file
                    if rel_path not in sounds or disk_file is not None:
                        sounds[rel_path] = {
                            "id": rel_path,
                            "hash": h,
                            "size": size,
                            "disk_path": disk_file
                        }
        except Exception as e:
            print(f"Error loading sound index {jf}: {e}")

    return last_idx_name, sounds

def convert_audio_to_ogg(input_path, output_ogg_path):
    input_path = Path(input_path)
    output_ogg_path = Path(output_ogg_path)
    output_ogg_path.parent.mkdir(parents=True, exist_ok=True)

    if input_path.suffix.lower() == ".ogg":
        shutil.copy2(input_path, output_ogg_path)
        return True

    if sf is not None:
        try:
            data, samplerate = sf.read(str(input_path))
            sf.write(str(output_ogg_path), data, samplerate, format="OGG", subtype="VORBIS")
            return True
        except Exception as e:
            print(f"soundfile conversion error: {e}")

    shutil.copy2(input_path, output_ogg_path)
    return True

def make_sound_pack_png(dest_path):
    try:
        img = Image.new("RGBA", (128, 128), (30, 30, 46, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([4, 4, 123, 123], outline=(137, 180, 250), width=3)
        draw.polygon([(36, 50), (52, 50), (74, 34), (74, 94), (52, 78), (36, 78)], fill=(166, 227, 161))
        draw.arc([68, 44, 96, 84], -60, 60, fill=(137, 180, 250), width=4)
        draw.arc([62, 32, 112, 96], -60, 60, fill=(245, 194, 231), width=4)
        img.save(dest_path, "PNG")
    except Exception:
        pass

SOUND_ALIASES = {
    "item/totem/use_totem.ogg": [
        "assets/minecraft/sounds/item/totem/use_totem.ogg",
        "assets/minecraft/sounds/item/totem/use.ogg"
    ],
    "damage/hit1.ogg": [
        "assets/minecraft/sounds/damage/hit1.ogg",
        "assets/minecraft/sounds/entity/player/hurt1.ogg"
    ],
    "damage/hit2.ogg": [
        "assets/minecraft/sounds/damage/hit2.ogg",
        "assets/minecraft/sounds/entity/player/hurt2.ogg"
    ],
    "damage/hit3.ogg": [
        "assets/minecraft/sounds/damage/hit3.ogg",
        "assets/minecraft/sounds/entity/player/hurt3.ogg"
    ],
    "entity/creeper/primed.ogg": [
        "assets/minecraft/sounds/entity/creeper/primed.ogg",
        "assets/minecraft/sounds/mob/creeper/say1.ogg",
        "assets/minecraft/sounds/mob/creeper/say2.ogg",
        "assets/minecraft/sounds/mob/creeper/say3.ogg",
        "assets/minecraft/sounds/mob/creeper/say4.ogg"
    ],
    "random/explode1.ogg": [
        "assets/minecraft/sounds/random/explode1.ogg",
        "assets/minecraft/sounds/entity/generic/explode1.ogg"
    ],
    "random/explode2.ogg": [
        "assets/minecraft/sounds/random/explode2.ogg",
        "assets/minecraft/sounds/entity/generic/explode2.ogg"
    ],
    "random/explode3.ogg": [
        "assets/minecraft/sounds/random/explode3.ogg",
        "assets/minecraft/sounds/entity/generic/explode3.ogg"
    ],
    "random/explode4.ogg": [
        "assets/minecraft/sounds/random/explode4.ogg",
        "assets/minecraft/sounds/entity/generic/explode4.ogg"
    ],
    "random/levelup.ogg": [
        "assets/minecraft/sounds/random/levelup.ogg",
        "assets/minecraft/sounds/entity/player/levelup.ogg"
    ],
    "random/orb.ogg": [
        "assets/minecraft/sounds/random/orb.ogg",
        "assets/minecraft/sounds/entity/experience_orb/touch.ogg"
    ],
    "random/anvil_land.ogg": [
        "assets/minecraft/sounds/random/anvil_land.ogg",
        "assets/minecraft/sounds/block/anvil/land.ogg"
    ],
    "random/anvil_use.ogg": [
        "assets/minecraft/sounds/random/anvil_use.ogg",
        "assets/minecraft/sounds/block/anvil/use.ogg"
    ],
    "random/anvil_break.ogg": [
        "assets/minecraft/sounds/random/anvil_break.ogg",
        "assets/minecraft/sounds/block/anvil/destroy.ogg"
    ],
    "random/chestopen.ogg": [
        "assets/minecraft/sounds/random/chestopen.ogg",
        "assets/minecraft/sounds/block/chest/open.ogg"
    ],
    "random/chestclosed.ogg": [
        "assets/minecraft/sounds/random/chestclosed.ogg",
        "assets/minecraft/sounds/block/chest/close.ogg"
    ],
    "random/bow.ogg": [
        "assets/minecraft/sounds/random/bow.ogg",
        "assets/minecraft/sounds/entity/arrow/shoot.ogg"
    ],
    "random/eat1.ogg": [
        "assets/minecraft/sounds/random/eat1.ogg",
        "assets/minecraft/sounds/entity/generic/eat1.ogg"
    ],
    "random/drink.ogg": [
        "assets/minecraft/sounds/random/drink.ogg",
        "assets/minecraft/sounds/entity/generic/drink.ogg"
    ],
    "random/burp.ogg": [
        "assets/minecraft/sounds/random/burp.ogg",
        "assets/minecraft/sounds/entity/player/burp.ogg"
    ]
}

CURATED_POPULAR_SOUNDS = [
    {
        "id": "item/totem/use_totem.ogg",
        "name": "🌟 Тотем бессмертия (Активация)",
        "category": "🌟 Популярные",
        "desc": "Звук срабатывания тотема бессмертия при спасении жизни игрока (самый популярный звук для замены)."
    },
    {
        "id": "damage/hit1.ogg",
        "name": "🩸 Урон игрока #1 («Oof!» / Хит)",
        "category": "🌟 Популярные",
        "desc": "Основной звук получения любого урона персонажем (тот самый легендарный «Oof!»)."
    },
    {
        "id": "damage/hit2.ogg",
        "name": "🩸 Урон игрока #2",
        "category": "🌟 Популярные",
        "desc": "Второй вариант звука получения урона персонажем."
    },
    {
        "id": "damage/hit3.ogg",
        "name": "🩸 Урон игрока #3",
        "category": "🌟 Популярные",
        "desc": "Третий вариант звука получения урона персонажем."
    },
    {
        "id": "random/explode1.ogg",
        "name": "💥 Взрыв ТНТ / Крипера #1",
        "category": "🌟 Популярные",
        "desc": "Громкий звук детонации динамита или взрыва крипера."
    },
    {
        "id": "random/explode2.ogg",
        "name": "💥 Взрыв ТНТ / Крипера #2",
        "category": "🌟 Популярные",
        "desc": "Вариант звука взрыва ТНТ или крипера."
    },
    {
        "id": "entity/creeper/primed.ogg",
        "name": "💣 Шипение крипера перед взрывом",
        "category": "🌟 Популярные",
        "desc": "Тревожное шипение фитиля крипера при приближении к игроку."
    },
    {
        "id": "random/levelup.ogg",
        "name": "⭐ Получение уровня (Level Up)",
        "category": "🌟 Популярные",
        "desc": "Торжественный звук повышения уровня опыта игрока."
    },
    {
        "id": "random/orb.ogg",
        "name": "✨ Сбор сфер опыта (Exp Ding)",
        "category": "🌟 Популярные",
        "desc": "Звонкий колокольчик при подборе сфер опыта."
    },
    {
        "id": "random/chestopen.ogg",
        "name": "📦 Открытие сундука",
        "category": "🌟 Популярные",
        "desc": "Скрип открывающейся крышки сундука."
    },
    {
        "id": "random/chestclosed.ogg",
        "name": "📦 Закрытие сундука",
        "category": "🌟 Популярные",
        "desc": "Хлопок закрывающейся крышки сундука."
    },
    {
        "id": "random/anvil_land.ogg",
        "name": "🔨 Падение наковальни",
        "category": "🌟 Популярные",
        "desc": "Тяжёлый металлический звон при падении наковальни."
    },
    {
        "id": "random/anvil_use.ogg",
        "name": "🔨 Использование наковальни",
        "category": "🌟 Популярные",
        "desc": "Удар молота по наковальне при починке или переименовании предмета."
    },
    {
        "id": "random/bow.ogg",
        "name": "🏹 Выстрел из лука",
        "category": "🌟 Популярные",
        "desc": "Свист тетивы и вылет стрелы из лука."
    },
    {
        "id": "entity/player/attack/sweep1.ogg",
        "name": "⚔️ Взмах меча (Sweep Attack)",
        "category": "🌟 Популярные",
        "desc": "Рассекающий взмах меча при круговой атаке по мобам."
    },
    {
        "id": "random/eat1.ogg",
        "name": "🍖 Поедание еды (Хруст)",
        "category": "🌟 Популярные",
        "desc": "Звук пережевывания яблока, стейка или хлеба."
    },
    {
        "id": "random/drink.ogg",
        "name": "🧪 Питьё зелья / молока",
        "category": "🌟 Популярные",
        "desc": "Звук выпивания зелья из стеклянной бутылочки."
    },
    {
        "id": "random/burp.ogg",
        "name": "😋 Отрыжка после еды",
        "category": "🌟 Популярные",
        "desc": "Классический забавный звук насыщения персонажа после приёма пищи."
    },
    {
        "id": "block/bell/bell_use01.ogg",
        "name": "🔔 Звон деревенского колокола",
        "category": "🌟 Популярные",
        "desc": "Громкий набат колокола в деревне жителей."
    },
    {
        "id": "mob/villager/idle1.ogg",
        "name": "🗣️ Житель (Хммм)",
        "category": "🌟 Популярные",
        "desc": "Классическое бормотание деревенского жителя."
    },
    {
        "id": "mob/villager/yes1.ogg",
        "name": "🗣️ Житель (Согласие / Торговля)",
        "category": "🌟 Популярные",
        "desc": "Довольный возглас жителя при успешной сделке."
    },
    {
        "id": "mob/villager/no1.ogg",
        "name": "🗣️ Житель (Отказ)",
        "category": "🌟 Популярные",
        "desc": "Недовольное мычание жителя при невозможности торговли."
    },
    {
        "id": "mob/zombie/say1.ogg",
        "name": "🧟 Рычание зомби",
        "category": "🌟 Популярные",
        "desc": "Глухое урчание приближающегося зомби."
    },
    {
        "id": "mob/endermen/scream1.ogg",
        "name": "👁️ Эндермен (Крик при взгляде)",
        "category": "🌟 Популярные",
        "desc": "Жуткий пронзительный вопль разозлившегося странника Края."
    },
    {
        "id": "mob/warden/roar1.ogg",
        "name": "👾 Варден (Грозный рёв)",
        "category": "🌟 Популярные",
        "desc": "Устрашающий рык Хранителя тёмных глубин."
    },
    {
        "id": "mob/enderdragon/growl1.ogg",
        "name": "🐉 Дракон Края (Рык)",
        "category": "🌟 Популярные",
        "desc": "Могучий устрашающий рёв Эндер-дракона."
    },
    {
        "id": "records/pigstep.ogg",
        "name": "🎵 Пластинка: Pigstep (Lena Raine)",
        "category": "🌟 Популярные",
        "desc": "Зажигательный и энергичный электронный трек из Незера."
    },
    {
        "id": "records/cat.ogg",
        "name": "🎵 Пластинка: Cat (C418)",
        "category": "🌟 Популярные",
        "desc": "Легендарный зелёный виниловый диск с доброй мелодией."
    },
    {
        "id": "records/otherside.ogg",
        "name": "🎵 Пластинка: Otherside (Lena Raine)",
        "category": "🌟 Популярные",
        "desc": "Красивая и мелодичная пластинка из древних глубин."
    }
]

class SoundPlayer:
    def __init__(self):
        self._current_sound = None
        self._channel = None
        self._lock = threading.Lock()
        self._volume = 1.0
        self._engine = None  # "pygame" or "winsound"
        self._stop_event = threading.Event()
        self._temp_wav = None

    def _init_mixer(self):
        if pygame:
            try:
                if not pygame.mixer.get_init():
                    try:
                        pygame.mixer.init()
                    except Exception:
                        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                return bool(pygame.mixer.get_init())
            except Exception as e:
                print(f"pygame mixer init failed: {e}")
        return False

    def set_volume(self, vol):
        self._volume = max(0.0, min(1.0, float(vol)))
        if self._channel:
            try:
                self._channel.set_volume(self._volume)
            except Exception:
                pass

    def play(self, file_path, on_finish_callback=None):
        if not file_path or not Path(file_path).exists():
            raise FileNotFoundError("Файл звука не найден на диске")
        self.stop()

        # Engine 1: Pygame mixer (primary, high-performance)
        if self._init_mixer() and pygame and pygame.mixer.get_init():
            try:
                with self._lock:
                    snd = pygame.mixer.Sound(str(file_path))
                    snd.set_volume(self._volume)
                    ch = snd.play()
                    self._current_sound = snd
                    self._channel = ch
                    self._engine = "pygame"

                    if on_finish_callback and ch:
                        def _monitor():
                            while ch.get_busy():
                                time.sleep(0.05)
                            on_finish_callback()
                        threading.Thread(target=_monitor, daemon=True).start()

                    return snd.get_length()
            except Exception as e:
                print(f"Pygame playback error, trying Windows native fallback: {e}")

        # Engine 2: Windows native audio (winsound + soundfile)
        # Decodes .ogg, .mp3, .wav into memory/temp WAV and plays natively without external DLLs!
        if winsound:
            try:
                p = Path(file_path)
                dur = 1.0
                target_wav = None

                if p.suffix.lower() == ".wav":
                    target_wav = str(p)
                elif sf is not None:
                    data, sr = sf.read(str(p))
                    dur = len(data) / float(sr)
                    tmp_wav_path = os.path.join(tempfile.gettempdir(), f"mc_preview_{os.getpid()}.wav")
                    sf.write(tmp_wav_path, data, sr, format="WAV")
                    self._temp_wav = tmp_wav_path
                    target_wav = tmp_wav_path

                if target_wav and os.path.exists(target_wav):
                    with self._lock:
                        winsound.PlaySound(target_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
                        self._engine = "winsound"
                        self._stop_event.clear()

                        if on_finish_callback:
                            def _timer(evt):
                                slept = 0.0
                                while slept < dur and not evt.is_set():
                                    time.sleep(0.05)
                                    slept += 0.05
                                if not evt.is_set():
                                    with self._lock:
                                        if self._engine == "winsound":
                                            self._engine = None
                                    on_finish_callback()
                            threading.Thread(target=_timer, args=(self._stop_event,), daemon=True).start()

                        return dur
            except Exception as e:
                print(f"winsound fallback error: {e}")

        raise RuntimeError(
            "Не удалось воспроизвести аудио.\n"
            "Убедитесь, что к компьютеру подключены наушники или колонки,\n"
            "и служба звука Windows включена."
        )

    def stop(self):
        with self._lock:
            self._stop_event.set()
            if pygame and pygame.mixer.get_init():
                try:
                    pygame.mixer.stop()
                except Exception:
                    pass
            if winsound:
                try:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except Exception:
                    pass
            self._channel = None
            self._current_sound = None
            self._engine = None

    def is_playing(self):
        if self._engine == "pygame" and self._channel:
            return self._channel.get_busy()
        return self._engine is not None

# ── Tab 2: Sound Manager ──────────────────────────────────────────────────────
class SoundTab(tk.Frame):
    def __init__(self, parent, mc_path_var, status_fn):
        super().__init__(parent, bg=BG)
        self.mc_path_var = mc_path_var
        self.set_status = status_fn

        self.player = SoundPlayer()
        self._indexed_sounds = {}     # rel_path -> info dict
        self._all_sounds = []         # Unified list of sound dicts
        self._displayed_sounds = []   # Current filtered list
        self._replacements = []       # Queued replacements: {'sound': dict, 'user_path': Path, 'duration': float}

        self._selected_sound = None
        self._selected_user_file = None
        self._user_file_duration = 0.0

        self._is_playing_orig = False
        self._is_playing_user = False
        self._is_working = False

        self._build_ui()
        self.after(200, self._reload_sounds)

    def _build_ui(self):
        # 1. Header Banner
        hdr = tk.Frame(self, bg=SURFACE, padx=16, pady=9)
        hdr.pack(fill="x", padx=14, pady=(10, 8))

        tk.Label(
            hdr, text="🔊 Звуки Minecraft (Прослушать и заменить)",
            bg=SURFACE, fg=ACCENT, font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Встроенный аудиоплеер для звуков игры, удобная замена на любые свои файлы (.mp3, .wav, .ogg, .flac)\n"
                 "и быстрая сборка звукового ресурс-пака с автоконвертацией в 1 клик!",
            bg=SURFACE, fg=TEXT, font=("Segoe UI", 9), justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Filter & Toolbar
        bar = tk.Frame(self, bg=SURFACE, padx=12, pady=7, highlightthickness=1, highlightbackground="#45475a")
        bar.pack(fill="x", padx=14, pady=(0, 8))

        tk.Label(bar, text="Категория:", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.cat_var = tk.StringVar(value="🌟 Самые популярные")
        self.cat_cb = ttk.Combobox(
            bar, textvariable=self.cat_var, state="readonly", width=24,
            values=[
                "🌟 Самые популярные",
                "Все звуки игры",
                "Предметы (item)",
                "Блоки (block)",
                "Мобы и сущности (mob/entity)",
                "Урон (damage)",
                "Взрывы и случайные (random)",
                "Музыкальные диски (records)",
                "Окружение (ambient)",
                "Интерфейс (ui)"
            ]
        )
        self.cat_cb.pack(side="left", padx=(6, 12))
        self.cat_cb.bind("<<ComboboxSelected>>", self._filter_sounds)

        tk.Label(bar, text="Поиск звука:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.search_var = tk.StringVar()
        s_ent = tk.Entry(bar, textvariable=self.search_var, width=18, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        s_ent.pack(side="left", padx=(6, 6))
        s_ent.bind("<KeyRelease>", self._filter_sounds)

        btn_clear = tk.Button(
            bar, text="✕", bg="#313244", fg=SUBTEXT, activebackground="#45475a",
            font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2, cursor="hand2",
            command=self._clear_search
        )
        btn_clear.pack(side="left", padx=(0, 12))

        # Volume slider
        tk.Label(bar, text="🔊 Громкость:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.vol_scale = tk.Scale(
            bar, from_=0, to=100, orient="horizontal", length=90,
            showvalue=0, bg=SURFACE, fg=ACCENT, highlightthickness=0,
            troughcolor=BG, activebackground=ACCENT, command=self._on_volume_change
        )
        self.vol_scale.set(100)
        self.vol_scale.pack(side="left", padx=(4, 12))

        btn_refresh = tk.Button(
            bar, text="🔄 Обновить звуки игры", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._reload_sounds
        )
        btn_refresh.pack(side="right")

        # 3. Main Paned Layout
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashrelief="flat", sashwidth=8)
        paned.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        # ── LEFT: Sound Catalog Table ─────────────────────────────────────────
        left_box = tk.Frame(paned, bg=SURFACE, padx=8, pady=8)
        paned.add(left_box, width=540)

        left_hdr = tk.Frame(left_box, bg=SURFACE)
        left_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(left_hdr, text="Каталог звуков игры", font=("Segoe UI", 10, "bold"), bg=SURFACE, fg=ACCENT).pack(side="left")
        self.count_lbl = tk.Label(left_hdr, text="Загрузка...", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 8))
        self.count_lbl.pack(side="right")

        tree_frame = tk.Frame(left_box, bg=SURFACE)
        tree_frame.pack(fill="both", expand=True)

        cols = ("name", "cat", "path", "orig")
        self.sound_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.sound_tree.heading("name", text="Звук", anchor="w")
        self.sound_tree.heading("cat", text="Категория", anchor="w")
        self.sound_tree.heading("path", text="Путь в игре", anchor="w")
        self.sound_tree.heading("orig", text="Оригинал", anchor="center")

        self.sound_tree.column("name", width=190, minwidth=140)
        self.sound_tree.column("cat", width=100, minwidth=80)
        self.sound_tree.column("path", width=170, minwidth=120)
        self.sound_tree.column("orig", width=70, minwidth=60, anchor="center")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sound_tree.yview)
        self.sound_tree.configure(yscrollcommand=sb.set)
        self.sound_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.sound_tree.bind("<<TreeviewSelect>>", self._on_sound_selected)

        # ── RIGHT: Details, Player, Replacements, Actions ─────────────────────
        right_box = tk.Frame(paned, bg=SURFACE, padx=12, pady=8)
        paned.add(right_box, width=640)

        # Card 1: Original Minecraft Sound Player
        card_orig = tk.LabelFrame(right_box, text="  🎵 1. Оригинальный звук из Minecraft  ", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 10, "bold"), padx=10, pady=8)
        card_orig.pack(fill="x", pady=(0, 8))

        self.orig_title_lbl = tk.Label(card_orig, text="Выберите звук в таблице слева", font=("Segoe UI", 11, "bold"), bg=SURFACE, fg=TEXT, anchor="w")
        self.orig_title_lbl.pack(fill="x")

        self.orig_path_lbl = tk.Label(card_orig, text="", font=("Segoe UI", 8), bg=SURFACE, fg=SUBTEXT, anchor="w")
        self.orig_path_lbl.pack(fill="x", pady=(1, 4))

        self.orig_desc_lbl = tk.Label(card_orig, text="", font=("Segoe UI", 9), bg=SURFACE, fg=TEXT, justify="left", wraplength=580, anchor="w")
        self.orig_desc_lbl.pack(fill="x", pady=(0, 6))

        orig_row = tk.Frame(card_orig, bg=SURFACE)
        orig_row.pack(fill="x")

        self.btn_play_orig = tk.Button(
            orig_row, text="▶️ Прослушать оригинал", bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=5, cursor="hand2",
            state="disabled", command=self._play_original
        )
        self.btn_play_orig.pack(side="left", padx=(0, 6))

        self.btn_stop_orig = tk.Button(
            orig_row, text="⏹️ Стоп", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=10, pady=5, cursor="hand2",
            state="disabled", command=self._stop_playback
        )
        self.btn_stop_orig.pack(side="left", padx=(0, 10))

        self.orig_info_lbl = tk.Label(orig_row, text="", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9))
        self.orig_info_lbl.pack(side="left", fill="x", expand=True)

        # Card 2: User Replacement Audio
        card_user = tk.LabelFrame(right_box, text="  🎧 2. Заменить на свой звук  ", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 10, "bold"), padx=10, pady=8)
        card_user.pack(fill="x", pady=(0, 8))

        user_top = tk.Frame(card_user, bg=SURFACE)
        user_top.pack(fill="x", pady=(0, 6))

        self.btn_choose_user = tk.Button(
            user_top, text="📂 Выбрать свой звук (.mp3, .wav, .ogg, .flac)",
            bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=5, cursor="hand2",
            command=self._choose_user_sound
        )
        self.btn_choose_user.pack(side="left", padx=(0, 10))

        self.user_file_lbl = tk.Label(user_top, text="Файл не выбран (нажмите кнопку слева)", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9), anchor="w")
        self.user_file_lbl.pack(side="left", fill="x", expand=True)

        user_ctrl_row = tk.Frame(card_user, bg=SURFACE)
        user_ctrl_row.pack(fill="x")

        self.btn_play_user = tk.Button(
            user_ctrl_row, text="▶️ Прослушать свою запись", bg="#89b4fa", fg="#1e1e2e", activebackground="#b4befe",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=5, cursor="hand2",
            state="disabled", command=self._play_user_sound
        )
        self.btn_play_user.pack(side="left", padx=(0, 6))

        self.btn_stop_user = tk.Button(
            user_ctrl_row, text="⏹️ Стоп", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=10, pady=5, cursor="hand2",
            state="disabled", command=self._stop_playback
        )
        self.btn_stop_user.pack(side="left", padx=(0, 12))

        self.btn_add_replacement = tk.Button(
            user_ctrl_row, text="➕ Добавить замену в набор", bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=5, cursor="hand2",
            state="disabled", command=self._add_replacement
        )
        self.btn_add_replacement.pack(side="right")

        # Card 3: Queued Replacements Table
        card_reps = tk.LabelFrame(right_box, text="  📋 3. Запланированные замены в ресурс-паке  ", bg=SURFACE, fg=ACCENT, font=("Segoe UI", 10, "bold"), padx=10, pady=6)
        card_reps.pack(fill="both", expand=True, pady=(0, 8))

        reps_table_frame = tk.Frame(card_reps, bg=SURFACE)
        reps_table_frame.pack(fill="both", expand=True, pady=(0, 6))

        rep_cols = ("orig_name", "user_audio")
        self.rep_tree = ttk.Treeview(reps_table_frame, columns=rep_cols, show="headings", selectmode="browse", height=4)
        self.rep_tree.heading("orig_name", text="Оригинальный звук в игре", anchor="w")
        self.rep_tree.heading("user_audio", text="Ваш аудиофайл", anchor="w")
        self.rep_tree.column("orig_name", width=250, minwidth=180)
        self.rep_tree.column("user_audio", width=320, minwidth=200)

        rep_sb = ttk.Scrollbar(reps_table_frame, orient="vertical", command=self.rep_tree.yview)
        self.rep_tree.configure(yscrollcommand=rep_sb.set)
        self.rep_tree.pack(side="left", fill="both", expand=True)
        rep_sb.pack(side="right", fill="y")

        reps_btn_row = tk.Frame(card_reps, bg=SURFACE)
        reps_btn_row.pack(fill="x")

        self.rep_count_lbl = tk.Label(reps_btn_row, text="Замен в наборе: 0", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9))
        self.rep_count_lbl.pack(side="left")

        self.btn_clear_reps = tk.Button(
            reps_btn_row, text="🧹 Очистить список", bg="#313244", fg=SUBTEXT, activebackground="#45475a",
            font=("Segoe UI", 8), relief="flat", padx=8, pady=3, cursor="hand2", command=self._clear_replacements
        )
        self.btn_clear_reps.pack(side="right")

        self.btn_del_rep = tk.Button(
            reps_btn_row, text="🗑️ Удалить выбранную", bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 8), relief="flat", padx=8, pady=3, cursor="hand2", command=self._delete_replacement
        )
        self.btn_del_rep.pack(side="right", padx=(0, 6))

        # Card 4: Installation & Export
        card_install = tk.Frame(right_box, bg="#242638", padx=12, pady=10, highlightthickness=1, highlightbackground="#45475a")
        card_install.pack(fill="x")

        pname_row = tk.Frame(card_install, bg="#242638")
        pname_row.pack(fill="x", pady=(0, 8))

        tk.Label(pname_row, text="Название ресурс-пака:", bg="#242638", fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        self.pack_name_var = tk.StringVar(value="My Custom Sounds")
        pname_ent = tk.Entry(pname_row, textvariable=self.pack_name_var, width=28, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        pname_ent.pack(side="left", fill="x", expand=True)

        action_row = tk.Frame(card_install, bg="#242638")
        action_row.pack(fill="x")

        self.btn_install_mc = tk.Button(
            action_row, text="⚡ Установить звуковой пак в Minecraft",
            bg=SUCCESS, fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=7, cursor="hand2",
            command=self._install_to_mc
        )
        self.btn_install_mc.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_export_zip = tk.Button(
            action_row, text="📁 Экспорт в ZIP-архив...",
            bg="#45475a", fg=TEXT, activebackground="#585b70",
            font=("Segoe UI", 9), relief="flat", padx=12, pady=7, cursor="hand2",
            command=self._export_to_zip
        )
        self.btn_export_zip.pack(side="left")

        # 4. Bottom Tip Card
        tip_frame = tk.Frame(self, bg="#242638", padx=14, pady=6, highlightthickness=1, highlightbackground="#45475a")
        tip_frame.pack(fill="x", padx=14, pady=(6, 8))
        tk.Label(
            tip_frame,
            text="💡 Как включить в игре: Настройки ➔ Наборы ресурсов (Resource Packs) ➔ Переместите ваш созданный звуковой пак вправо ➔ «Готово»!\n"
                 "Если игра уже запущена во время установки — нажмите сочетание клавиш F3 + T для мгновенной перезагрузки всех ресурсов.",
            bg="#242638", fg=TEXT, font=("Segoe UI", 8), justify="left"
        ).pack(anchor="w")

    def _on_volume_change(self, val):
        try:
            self.player.set_volume(float(val) / 100.0)
        except Exception:
            pass

    def _clear_search(self):
        self.search_var.set("")
        self._filter_sounds()

    def _reload_sounds(self):
        self.count_lbl.config(text="Чтение ресурсов Minecraft...")
        self.set_status("Поиск звуков в .minecraft...")
        mc_path_val = self.mc_path_var.get()

        def worker():
            mc = Path(mc_path_val)
            idx_name, indexed = load_minecraft_sound_index(mc)
            self._indexed_sounds = indexed

            all_list = []

            # 1. Curated popular sounds
            for cur in CURATED_POPULAR_SOUNDS:
                sid = cur["id"]
                match_info = indexed.get(sid)
                # check aliases if exact key not in index
                if not match_info:
                    for alias in SOUND_ALIASES.get(sid, []):
                        rel = alias.replace("assets/minecraft/sounds/", "")
                        if rel in indexed:
                            match_info = indexed[rel]
                            break

                disk_p = match_info.get("disk_path") if match_info else None
                all_list.append({
                    "id": sid,
                    "name": cur["name"],
                    "category": cur["category"],
                    "desc": cur["desc"],
                    "path": f"assets/minecraft/sounds/{sid}",
                    "disk_path": disk_p,
                    "is_curated": True
                })

            # 2. All other indexed sounds
            for rel, info in indexed.items():
                # Avoid exact duplicates of curated
                if any(c["id"] == rel for c in CURATED_POPULAR_SOUNDS):
                    continue
                parts = rel.split("/")
                cat_tag = parts[0] if parts else "other"
                clean_name = parts[-1].replace(".ogg", "").replace("_", " ").title()
                all_list.append({
                    "id": rel,
                    "name": f"🎵 {clean_name}",
                    "category": cat_tag,
                    "desc": f"Игровой звук Minecraft: {rel}",
                    "path": f"assets/minecraft/sounds/{rel}",
                    "disk_path": info.get("disk_path"),
                    "is_curated": False
                })

            self._all_sounds = all_list
            self.after(0, self._filter_sounds)

        threading.Thread(target=worker, daemon=True).start()

    def _filter_sounds(self, *_):
        cat = self.cat_var.get()
        q = self.search_var.get().strip().lower()

        filtered = []
        for s in self._all_sounds:
            # Category match
            if cat == "🌟 Самые популярные":
                if not s.get("is_curated"):
                    continue
            elif cat == "Предметы (item)":
                if not s["id"].startswith("item/"):
                    continue
            elif cat == "Блоки (block)":
                if not s["id"].startswith("block/"):
                    continue
            elif cat == "Мобы и сущности (mob/entity)":
                if not (s["id"].startswith("mob/") or s["id"].startswith("entity/")):
                    continue
            elif cat == "Урон (damage)":
                if not (s["id"].startswith("damage/") or "hurt" in s["id"] or "hit" in s["id"]):
                    continue
            elif cat == "Взрывы и случайные (random)":
                if not s["id"].startswith("random/"):
                    continue
            elif cat == "Музыкальные диски (records)":
                if not (s["id"].startswith("records/") or s["id"].startswith("music/")):
                    continue
            elif cat == "Окружение (ambient)":
                if not s["id"].startswith("ambient/"):
                    continue
            elif cat == "Интерфейс (ui)":
                if not s["id"].startswith("ui/"):
                    continue
            # "Все звуки игры" passes all

            # Search text match
            if q:
                text_corpus = f"{s.get('name', '')} {s.get('id', '')} {s.get('category', '')} {s.get('desc', '')}".lower()
                if q not in text_corpus:
                    continue

            filtered.append(s)

        self._displayed_sounds = filtered
        self._render_table()

    def _render_table(self):
        self.sound_tree.delete(*self.sound_tree.get_children())
        total = len(self._displayed_sounds)
        self.count_lbl.config(text=f"Найдено: {total}")
        self.set_status(f"Показано {total} звуков")

        for i, s in enumerate(self._displayed_sounds):
            has_disk = "✅ Есть" if s.get("disk_path") else "В игре"
            self.sound_tree.insert(
                "", "end", iid=str(i),
                values=(s.get("name", ""), s.get("category", ""), s.get("id", ""), has_disk)
            )

        if total > 0:
            self.sound_tree.selection_set("0")
            self.sound_tree.focus("0")
            self._on_sound_selected()
        else:
            self.orig_title_lbl.config(text="Ничего не найдено")
            self.orig_path_lbl.config(text="")
            self.orig_desc_lbl.config(text="Попробуйте изменить категорию или поисковый запрос.")
            self.orig_info_lbl.config(text="")
            self.btn_play_orig.config(state="disabled")
            self.btn_stop_orig.config(state="disabled")
            self.btn_add_replacement.config(state="disabled")

    def _on_sound_selected(self, event=None):
        self._stop_playback()
        sel = self.sound_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._displayed_sounds):
            return
        sound = self._displayed_sounds[idx]
        self._selected_sound = sound

        self.orig_title_lbl.config(text=sound.get("name", "Звук игры"))
        self.orig_path_lbl.config(text=f"Путь в ресурс-паке: {sound.get('path', '')}")
        self.orig_desc_lbl.config(text=sound.get("desc", ""))

        disk_p = sound.get("disk_path")
        if disk_p and disk_p.exists():
            self.btn_play_orig.config(state="normal", text="▶️ Прослушать оригинал")
            self.orig_info_lbl.config(text="✅ Оригинальный звук игры доступен на диске", fg=SUCCESS)
        else:
            self.btn_play_orig.config(state="disabled", text="▶️ Прослушать оригинал")
            self.orig_info_lbl.config(text="⚠️ Файл отсутствует на диске (запустите Minecraft)", fg="#fab387")

        self._update_add_btn_state()

    def _play_original(self):
        if not self._selected_sound:
            return
        disk_p = self._selected_sound.get("disk_path")
        if not disk_p or not disk_p.exists():
            messagebox.showinfo("Оригинал не найден", "Оригинальный аудиофайл не найден на компьютере.\nЗапустите Minecraft хотя бы раз для скачивания ассетов.")
            return

        try:
            self._stop_playback()
            self._is_playing_orig = True
            self.btn_play_orig.config(text="🔊 Играет...", bg="#f9e2af")
            self.btn_stop_orig.config(state="normal")

            def on_done():
                self.after(0, self._on_orig_finished)

            dur = self.player.play(disk_p, on_finish_callback=on_done)
            self.orig_info_lbl.config(text=f"▶️ Воспроизведение... ({dur:.1f} сек)", fg=ACCENT)
        except Exception as e:
            self._on_orig_finished()
            messagebox.showerror("Ошибка воспроизведения", f"Не удалось воспроизвести звук:\n{e}")

    def _on_orig_finished(self):
        self._is_playing_orig = False
        self.btn_play_orig.config(text="▶️ Прослушать оригинал", bg=SUCCESS)
        self.btn_stop_orig.config(state="disabled")
        if self._selected_sound and self._selected_sound.get("disk_path"):
            self.orig_info_lbl.config(text="✅ Оригинальный звук игры доступен на диске", fg=SUCCESS)

    def _choose_user_sound(self):
        path = filedialog.askopenfilename(
            title="Выберите свой аудиофайл для замены",
            filetypes=[
                ("Аудиофайлы", "*.mp3 *.wav *.ogg *.flac *.aac *.m4a"),
                ("MP3 файлы", "*.mp3"),
                ("WAV файлы", "*.wav"),
                ("OGG Vorbis", "*.ogg"),
                ("Все файлы", "*.*")
            ]
        )
        if not path:
            return
        p = Path(path)
        self._selected_user_file = p

        dur = 0.0
        try:
            if pygame and pygame.mixer.get_init():
                s = pygame.mixer.Sound(str(p))
                dur = s.get_length()
            elif sf is not None:
                info = sf.info(str(p))
                dur = info.duration
        except Exception:
            pass
        self._user_file_duration = dur

        sz_mb = p.stat().st_size / (1024 * 1024)
        dur_txt = f"{dur:.1f} сек" if dur > 0 else "аудио"
        self.user_file_lbl.config(
            text=f"🎵 {p.name} ({sz_mb:.1f} MB, {dur_txt})",
            fg=TEXT
        )
        self.btn_play_user.config(state="normal")
        self._update_add_btn_state()
        self.set_status(f"Выбран свой звук: {p.name}")

    def _play_user_sound(self):
        if not self._selected_user_file or not self._selected_user_file.exists():
            return
        try:
            self._stop_playback()
            self._is_playing_user = True
            self.btn_play_user.config(text="🔊 Играет...", bg="#f9e2af")
            self.btn_stop_user.config(state="normal")

            def on_done():
                self.after(0, self._on_user_finished)

            dur = self.player.play(self._selected_user_file, on_finish_callback=on_done)
            self.set_status(f"Воспроизведение: {self._selected_user_file.name} ({dur:.1f} сек)")
        except Exception as e:
            self._on_user_finished()
            messagebox.showerror("Ошибка воспроизведения", f"Не удалось воспроизвести выбранный файл:\n{e}")

    def _on_user_finished(self):
        self._is_playing_user = False
        self.btn_play_user.config(text="▶️ Прослушать свою запись", bg="#89b4fa")
        self.btn_stop_user.config(state="disabled")

    def _stop_playback(self):
        self.player.stop()
        if self._is_playing_orig:
            self._on_orig_finished()
        if self._is_playing_user:
            self._on_user_finished()

    def _update_add_btn_state(self):
        if self._selected_sound and self._selected_user_file:
            self.btn_add_replacement.config(state="normal")
        else:
            self.btn_add_replacement.config(state="disabled")

    def _add_replacement(self):
        if not self._selected_sound or not self._selected_user_file:
            return

        sid = self._selected_sound["id"]
        # Remove existing if already in list for same sound
        self._replacements = [r for r in self._replacements if r["sound_id"] != sid]

        # Compute target paths (primary + aliases)
        targets = [f"assets/minecraft/sounds/{sid}"]
        if sid in SOUND_ALIASES:
            for al in SOUND_ALIASES[sid]:
                if al not in targets:
                    targets.append(al)

        self._replacements.append({
            "sound_id": sid,
            "name": self._selected_sound["name"],
            "user_file": self._selected_user_file,
            "target_paths": targets
        })

        self._render_replacements()
        self.set_status(f"Добавлена замена для «{self._selected_sound['name']}»")
        messagebox.showinfo(
            "Замена добавлена!",
            f"Замена для «{self._selected_sound['name']}» добавлена в список!\n\n"
            f"Файл: {self._selected_user_file.name}\n\n"
            f"Вы можете добавить еще замены или нажать кнопку «Установить звуковой пак в Minecraft»!"
        )

    def _render_replacements(self):
        self.rep_tree.delete(*self.rep_tree.get_children())
        for i, r in enumerate(self._replacements):
            self.rep_tree.insert(
                "", "end", iid=str(i),
                values=(r["name"], r["user_file"].name)
            )
        cnt = len(self._replacements)
        self.rep_count_lbl.config(text=f"Замен в наборе: {cnt}")
        if cnt > 0:
            self.btn_install_mc.config(state="normal")
            self.btn_export_zip.config(state="normal")
        else:
            self.btn_install_mc.config(state="normal")
            self.btn_export_zip.config(state="normal")

    def _delete_replacement(self):
        sel = self.rep_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < len(self._replacements):
            removed = self._replacements.pop(idx)
            self._render_replacements()
            self.set_status(f"Удалена замена: {removed['name']}")

    def _clear_replacements(self):
        if not self._replacements:
            return
        if messagebox.askyesno("Очистить список", "Удалить все добавленные замены звуков?"):
            self._replacements.clear()
            self._render_replacements()
            self.set_status("Список замен звуков очищен")

    def _install_to_mc(self):
        if not self._replacements:
            messagebox.showinfo("Список пуст", "Добавьте хотя бы одну замену звука в набор перед установкой!")
            return

        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Ошибка", f"Папка .minecraft не найдена:\n{mc}")
            return

        pack_name = self.pack_name_var.get().strip() or "My Custom Sounds"
        self._build_and_install_pack(mc, pack_name, is_export=False)

    def _export_to_zip(self):
        if not self._replacements:
            messagebox.showinfo("Список пуст", "Добавьте хотя бы одну замену звука в набор перед экспортом!")
            return

        pack_name = self.pack_name_var.get().strip() or "My Custom Sounds"
        target_zip = filedialog.asksaveasfilename(
            title="Сохранить звуковой ресурс-пак",
            initialfile=f"{pack_name}.zip",
            filetypes=[("ZIP архивы", "*.zip"), ("Все файлы", "*.*")]
        )
        if not target_zip:
            return

        self._build_and_install_pack(Path(target_zip).parent, pack_name, is_export=True, explicit_zip=Path(target_zip))

    def _build_and_install_pack(self, dest_root, pack_name, is_export=False, explicit_zip=None):
        if self._is_working:
            return
        self._is_working = True
        self.btn_install_mc.config(state="disabled")
        self.btn_export_zip.config(state="disabled")
        self.set_status("Создание звукового ресурс-пака...")

        def worker():
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_pack = Path(tmp_dir) / pack_name
                    tmp_pack.mkdir(parents=True, exist_ok=True)

                    # 1. pack.mcmeta
                    meta = {
                        "pack": {
                            "pack_format": 34,
                            "supported_formats": [1, 99],
                            "description": f"Custom Sound Pack - {pack_name}"
                        }
                    }
                    with open(tmp_pack / "pack.mcmeta", "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)

                    # 2. pack.png icon
                    make_sound_pack_png(tmp_pack / "pack.png")

                    # 3. Convert and place audio files
                    total_files = sum(len(r["target_paths"]) for r in self._replacements)
                    current_file = 0

                    for r in self._replacements:
                        src_audio = r["user_file"]
                        for target_rel in r["target_paths"]:
                            current_file += 1
                            pct = int((current_file / max(1, total_files)) * 100)
                            self.after(0, lambda p=pct, n=r['name']: self.set_status(f"Конвертация аудио ({p}%): {n}..."))

                            dest_ogg = tmp_pack / target_rel
                            convert_audio_to_ogg(src_audio, dest_ogg)

                    # 4. Install or export
                    if is_export:
                        out_zip = explicit_zip or (dest_root / f"{pack_name}.zip")
                        zip_pack(tmp_pack, out_zip)
                        self.after(0, lambda: self._on_export_success(out_zip))
                    else:
                        install_pack(tmp_pack, dest_root)
                        self.after(0, lambda: self._on_install_success(pack_name, dest_root))

            except Exception as e:
                self.after(0, lambda err=str(e): self._on_build_error(err))
            finally:
                self._is_working = False
                self.after(0, lambda: (
                    self.btn_install_mc.config(state="normal"),
                    self.btn_export_zip.config(state="normal")
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_success(self, pack_name, mc):
        self.set_status(f"Успешно установлен звуковой пак: {pack_name}")
        messagebox.showinfo(
            "Готово! Звуковой пак установлен",
            f"Звуковой ресурс-пак «{pack_name}» успешно создан и установлен в папку:\n"
            f"{mc / 'resourcepacks'}\n\n"
            f"Как включить в игре:\n"
            f"1. Откройте Minecraft ➔ Настройки ➔ Наборы ресурсов (Resource Packs)\n"
            f"2. Переместите «{pack_name}» стрелочкой в правую колонку ➔ Нажмите «Готово»!\n\n"
            f"💡 Если Minecraft уже запущен, нажмите F3 + T для мгновенной перезагрузки звуков!"
        )

    def _on_export_success(self, zip_path):
        self.set_status(f"Экспортирован архив: {zip_path.name}")
        messagebox.showinfo(
            "Экспорт завершён!",
            f"Звуковой ресурс-пак успешно экспортирован в архив:\n{zip_path}\n\n"
            f"Вы можете передать этот .zip друзьям или загрузить на GitHub!"
        )

    def _on_build_error(self, err_msg):
        self.set_status(f"Ошибка создания пака: {err_msg}", err=True)
        messagebox.showerror("Ошибка создания пака", f"Произошла ошибка при создании ресурс-пака:\n{err_msg}")

# ── Main Application Window ───────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Resource & Shader Manager v3.2")
        self.geometry("1260x830")
        self.minsize(1050, 680)
        self.configure(bg=BG)
        apply_style(self)

        self.mc_path_var = tk.StringVar(value=str(DEFAULT_MC))

        hdr = tk.Frame(self, bg=SURFACE, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🎮 Minecraft Resource & Shader Manager", font=("Segoe UI", 18, "bold"), bg=SURFACE, fg=ACCENT).pack(side="left", padx=16)
        tk.Label(hdr, text="Папка .minecraft:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(20, 4))
        tk.Entry(hdr, textvariable=self.mc_path_var, width=46, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(hdr, text="Обзор", command=self._browse_mc).pack(side="left", padx=6)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.tex_tab    = TextureTab(nb, self.mc_path_var, self._set_status)
        self.sound_tab  = SoundTab(nb, self.mc_path_var, self._set_status)
        self.github_tab = GitHubTab(nb, self.mc_path_var, self._set_status)
        self.shader_tab = ShaderTab(nb, self.mc_path_var, self._set_status)

        nb.add(self.tex_tab,    text="  ✏️ Заменить на свои фото  ")
        nb.add(self.sound_tab,  text="  🔊 Звуки  ")
        nb.add(self.github_tab, text="  ⭐ Текстур-паки GitHub  ")
        nb.add(self.shader_tab, text="  ☀️ Шейдеры  ")

        self.status_var = tk.StringVar(value="Готов к работе")
        sb = tk.Frame(self, bg=SURFACE, pady=5)
        sb.pack(fill="x", side="bottom")
        self._status_lbl = tk.Label(sb, textvariable=self.status_var, bg=SURFACE, fg=SUCCESS, font=("Segoe UI", 9))
        self._status_lbl.pack(side="left", padx=16)

    def _browse_mc(self):
        p = filedialog.askdirectory(title="Папка .minecraft")
        if p: self.mc_path_var.set(p)

    def _set_status(self, msg, err=False):
        self.status_var.set(msg)
        self._status_lbl.config(fg=WARNING if err else SUCCESS)

if __name__ == "__main__":
    app = App()
    app.mainloop()