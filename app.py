"""
Minecraft Texture Replacer v3.0
=================================
Tab 1 - Replace textures with your own photos (Totem, Grass, etc.)
Tab 2 - Download texture packs from GitHub with 1.png / 1.jpg screenshot preview
"""

import sys, subprocess, importlib

# Auto-install dependencies if running from Python directly
for _mod, _pkg in [("PIL", "pillow"), ("requests", "requests"), ("bs4", "beautifulsoup4")]:
    try:
        importlib.import_module(_mod)
    except ImportError:
        if not getattr(sys, "frozen", False):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", _pkg])

import html, io, json, os, posixpath, re, shutil, tempfile, threading, time, webbrowser, zipfile
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageOps, ImageTk

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

# ── Main Application Window ───────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Texture Replacer v3.0")
        self.geometry("1250x820")
        self.minsize(1050, 680)
        self.configure(bg=BG)
        apply_style(self)

        self.mc_path_var = tk.StringVar(value=str(DEFAULT_MC))

        hdr = tk.Frame(self, bg=SURFACE, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🎮 Minecraft Texture Replacer", font=("Segoe UI", 18, "bold"), bg=SURFACE, fg=ACCENT).pack(side="left", padx=16)
        tk.Label(hdr, text="Папка .minecraft:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(20, 4))
        tk.Entry(hdr, textvariable=self.mc_path_var, width=46, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(hdr, text="Обзор", command=self._browse_mc).pack(side="left", padx=6)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.tex_tab    = TextureTab(nb, self.mc_path_var, self._set_status)
        self.github_tab = GitHubTab(nb, self.mc_path_var, self._set_status)

        nb.add(self.tex_tab,    text="  ✏️ Заменить на свои фото  ")
        nb.add(self.github_tab, text="  ⭐ Избранное и GitHub  ")

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