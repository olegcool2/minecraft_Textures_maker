"""
Minecraft Texture Replacer v2.7
=================================
Tab 1 - Replace textures with your own photos
Tab 2 - Browse texture packs from:
        * Minecraft-Inside.ru
        * MinecraftExpert.ru
"""

import sys, subprocess, importlib

# Auto-install dependencies if running from Python directly
for _mod, _pkg in [("PIL", "pillow"), ("requests", "requests"), ("bs4", "beautifulsoup4")]:
    try:
        importlib.import_module(_mod)
    except ImportError:
        if not getattr(sys, "frozen", False):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", _pkg])

import html, io, json, os, re, shutil, tempfile, threading, time, webbrowser, zipfile
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps, ImageTk

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

def download_file(url, dest_path, progress_cb=None):
    try:
        resp = requests.get(url, headers=HEADERS, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done  = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
        return True
    except Exception as e:
        print(f"[download] {e}")
        return False

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
        self._build()
        self.after(300, self._load_jars)

    def _build(self):
        ctrl = tk.Frame(self, bg=BG, pady=6)
        ctrl.pack(fill="x", padx=14)
        tk.Label(ctrl, text="Версия:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.jar_combo = ttk.Combobox(ctrl, state="readonly", width=28)
        self.jar_combo.pack(side="left", padx=6)
        self.jar_combo.bind("<<ComboboxSelected>>", self._on_jar)
        ttk.Button(ctrl, text="Загрузить версии", command=self._load_jars).pack(side="left", padx=2)

        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=12)
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=270)
        self._build_left(left)
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=440)
        self._build_right(right)

        bot = tk.Frame(self, bg=SURFACE, pady=8)
        bot.pack(fill="x", side="bottom")
        tk.Label(bot, text="Название пака:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(16, 4))
        tk.Entry(bot, textvariable=self.pack_name, width=24, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat").pack(side="left", padx=(0, 10))
        ttk.Button(bot, text="📁 Папка", command=self._save_folder).pack(side="left", padx=3)
        ttk.Button(bot, text="🗜 ZIP", command=self._save_zip).pack(side="left", padx=3)
        ttk.Button(bot, text="🚀 Установить в MC", command=self._install).pack(side="left", padx=3)

    def _build_left(self, p):
        r = tk.Frame(p, bg=BG, pady=2)
        r.pack(fill="x")
        tk.Label(r, text="Категория:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.cat_combo = ttk.Combobox(r, state="readonly", values=list(TEXTURE_CATEGORIES.keys()), width=22)
        self.cat_combo.current(0)
        self.cat_combo.pack(side="left", padx=6)
        self.cat_combo.bind("<<ComboboxSelected>>", self._filter)
        r2 = tk.Frame(p, bg=BG, pady=2)
        r2.pack(fill="x")
        tk.Label(r2, text="Поиск:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        tk.Entry(r2, textvariable=self.search_var, width=24, bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat").pack(side="left", padx=6)
        lf = tk.Frame(p, bg=BG)
        lf.pack(fill="both", expand=True, pady=4)
        self.tex_list = tk.Listbox(lf, bg=SURFACE, fg=TEXT, selectbackground=ACCENT, selectforeground="#1e1e2e", relief="flat", font=("Consolas", 9), activestyle="none")
        sb = ttk.Scrollbar(lf, command=self.tex_list.yview)
        self.tex_list.configure(yscrollcommand=sb.set)
        self.tex_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tex_list.bind("<<ListboxSelect>>", self._on_tex)
        self.cnt = tk.Label(p, text="", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        self.cnt.pack()

    def _build_right(self, p):
        prev = tk.Frame(p, bg=BG)
        prev.pack(fill="x", pady=(0, 8))
        def card(f, lbl):
            c = tk.Frame(f, bg=SURFACE, padx=10, pady=8)
            c.pack(side="left", padx=(0, 10))
            tk.Label(c, text=lbl, bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack()
            il = tk.Label(c, bg=SURFACE, width=130, height=130)
            il.pack()
            sl = tk.Label(c, text="--", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 8))
            sl.pack()
            return il, sl
        self.orig_lbl, self.orig_sz = card(prev, "Оригинал")
        self.res_lbl,  self.res_sz  = card(prev, "Результат")
        sf = ttk.LabelFrame(p, text=" Настройки замены ")
        sf.pack(fill="x", pady=4)
        mr = tk.Frame(sf, bg=BG)
        mr.pack(fill="x", padx=8, pady=4)
        tk.Label(mr, text="Масштаб:", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        for txt, val in [("Fill", "fill"), ("Fit", "fit"), ("Stretch", "stretch"), ("Tile", "tile")]:
            tk.Radiobutton(mr, text=txt, variable=self.fit_mode, value=val, bg=BG, fg=TEXT, selectcolor=SURFACE, activebackground=BG, command=self._update_preview).pack(side="left", padx=5)
        sr = tk.Frame(sf, bg=BG)
        sr.pack(fill="x", padx=8, pady=4)
        tk.Label(sr, text="Размер:", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        self.size_combo = ttk.Combobox(sr, values=[str(s) for s in TEXTURE_SIZES], width=6, state="readonly")
        self.size_combo.set("16")
        self.size_combo.pack(side="left", padx=(4, 14))
        self.size_combo.bind("<<ComboboxSelected>>", lambda e: (self.size_var.set(int(self.size_combo.get())), self._update_preview()))
        tk.Checkbutton(sr, text="Сохранять альфа-канал", variable=self.keep_alpha, bg=BG, fg=TEXT, selectcolor=SURFACE, activebackground=BG, command=self._update_preview).pack(side="left")
        pr = tk.Frame(p, bg=BG)
        pr.pack(fill="x", pady=6)
        ttk.Button(pr, text="Выбрать фото", command=self._browse_img).pack(side="left")
        self.photo_lbl = tk.Label(pr, text="Файл не выбран", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))
        self.photo_lbl.pack(side="left", padx=10)
        ttk.Button(p, text="Добавить замену", command=self._add).pack(fill="x", pady=4)
        rf = ttk.LabelFrame(p, text=" Запланированные замены ")
        rf.pack(fill="both", expand=True, pady=4)
        cols = ("texture", "photo", "mode", "size")
        self.rep_tree = ttk.Treeview(rf, columns=cols, show="headings", height=6)
        for col, hd, w in zip(cols, ["Текстура", "Фото", "Режим", "Размер"], [240, 150, 80, 60]):
            self.rep_tree.heading(col, text=hd)
            self.rep_tree.column(col, width=w, anchor="w")
        rsb = ttk.Scrollbar(rf, command=self.rep_tree.yview)
        self.rep_tree.configure(yscrollcommand=rsb.set)
        self.rep_tree.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")
        ttk.Button(p, text="Удалить выбранное", command=self._remove).pack(fill="x")

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
            self.size_var.set(orig.width)
            self.size_combo.set(str(orig.width) if orig.width in TEXTURE_SIZES else "16")
        self._update_preview()

    def _browse_img(self):
        p = filedialog.askopenfilename(title="Выберите фото", filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff")])
        if p:
            self.user_image_path = p
            short = Path(p).name
            self.photo_lbl.config(text=(short[:36]+"...") if len(short)>38 else short, fg=SUCCESS)
            self._update_preview()

    def _update_preview(self, *_):
        if not self.user_image_path: return
        try:
            sz = self.size_var.get()
            r  = process_image(self.user_image_path, (sz, sz), self.fit_mode.get(), self.keep_alpha.get())
            ph = ImageTk.PhotoImage(r.resize((128, 128), Image.NEAREST))
            self.res_lbl.configure(image=ph)
            self._res_ph = ph
            self.res_sz.config(text=f"{sz}x{sz}")
        except Exception as e:
            self.set_status(f"Ошибка превью: {e}", err=True)

    def _add(self):
        if not self.selected_texture:
            messagebox.showwarning("Нет текстуры", "Выберите текстуру.")
            return
        if not self.user_image_path:
            messagebox.showwarning("Нет фото", "Выберите фото.")
            return
        sz   = self.size_var.get()
        mode = self.fit_mode.get()
        img  = process_image(self.user_image_path, (sz, sz), mode, self.keep_alpha.get())
        self.replacements.append({"mc_path": self.selected_texture, "image": img})
        self.rep_tree.insert("", "end", values=(Path(self.selected_texture).name, Path(self.user_image_path).name, mode, f"{sz}px"))
        self.set_status(f"Добавлено: {Path(self.selected_texture).name}")

    def _remove(self):
        sel = self.rep_tree.selection()
        if not sel: return
        idx = self.rep_tree.index(sel[0])
        self.rep_tree.delete(sel[0])
        if 0 <= idx < len(self.replacements):
            self.replacements.pop(idx)

    def _check(self):
        if not self.replacements:
            messagebox.showwarning("Пусто", "Добавьте хотя бы одну замену.")
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
            messagebox.showerror("Ошибка", f".minecraft не найдена:\n{mc}")
            return
        with tempfile.TemporaryDirectory() as tmp:
            pd   = build_pack(Path(tmp) / self.pack_name.get(), self.replacements)
            dest = install_pack(pd, mc)
        self.set_status(f"Установлено: {dest}")
        messagebox.showinfo("Установлено!", f"Установлено в:\n{dest}\n\nНастройки > Пакеты ресурсов > выберите пак")

# ── Tab 2: Browse Packs (Minecraft-Inside.ru & MinecraftExpert.ru) ────────────
class BrowseTab(tk.Frame):
    def __init__(self, parent, mc_path_var, status_fn):
        super().__init__(parent, bg=BG)
        self.mc_path_var = mc_path_var
        self.set_status = status_fn
        self._packs = []
        self._gallery_phs = []
        self._card_images = []
        self._current_page = 1
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=BG, pady=6)
        top.pack(fill="x", padx=14)

        # Site selection
        tk.Label(top, text="Сайт:", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.site_var = tk.StringVar(value="Minecraft-Inside.ru")
        self.site_cb = ttk.Combobox(top, textvariable=self.site_var,
                                    values=["Minecraft-Inside.ru", "MinecraftExpert.ru"],
                                    state="readonly", width=20)
        self.site_cb.pack(side="left", padx=6)
        self.site_cb.bind("<<ComboboxSelected>>", self._on_site_change)

        # Category
        tk.Label(top, text="Категория:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
        self.cat_var = tk.StringVar(value="Все текстуры")
        self.cat_cb = ttk.Combobox(top, textvariable=self.cat_var, values=list(INSIDE_CATEGORIES.keys()), state="readonly", width=18)
        self.cat_cb.pack(side="left", padx=4)
        self.cat_cb.bind("<<ComboboxSelected>>", lambda e: self._load_page(1))

        # Search
        tk.Label(top, text="Поиск:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
        self.search_site = tk.StringVar()
        s_ent = tk.Entry(top, textvariable=self.search_site, width=20, bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat")
        s_ent.pack(side="left", padx=4)
        s_ent.bind("<Return>", lambda e: self._do_search())
        ttk.Button(top, text="Искать", command=self._do_search).pack(side="left", padx=3)
        ttk.Button(top, text="Обновить", command=lambda: self._load_page(1)).pack(side="left", padx=2)

        # Pagination
        pag = tk.Frame(top, bg=BG)
        pag.pack(side="right")
        ttk.Button(pag, text="◀ Назад", command=lambda: self._load_page(self._current_page - 1)).pack(side="left", padx=2)
        self.page_lbl = tk.Label(pag, text="Стр. 1", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9, "bold"))
        self.page_lbl.pack(side="left", padx=6)
        ttk.Button(pag, text="Вперед ▶", command=lambda: self._load_page(self._current_page + 1)).pack(side="left", padx=2)

        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=480)
        self._build_grid(left)

        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=360)
        self._build_detail(right)

    def _on_site_change(self, event=None):
        site = self.site_var.get()
        if "Expert" in site:
            self.cat_cb["values"] = list(EXPERT_CATEGORIES.keys())
            self.cat_var.set("Все текстуры")
        else:
            self.cat_cb["values"] = list(INSIDE_CATEGORIES.keys())
            self.cat_var.set("Все текстуры")
        self._load_page(1)

    def _build_grid(self, parent):
        self.grid_canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.grid_canvas.yview)
        self.grid_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.grid_canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = tk.Frame(self.grid_canvas, bg=BG)
        self._grid_win = self.grid_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

        def on_f_configure(e):
            self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))
        def on_c_configure(e):
            if e.width > 50:
                self.grid_canvas.itemconfig(self._grid_win, width=e.width)

        self.grid_frame.bind("<Configure>", on_f_configure)
        self.grid_canvas.bind("<Configure>", on_c_configure)
        self.grid_canvas.bind_all("<MouseWheel>", lambda e: self.grid_canvas.yview_scroll(-1*(e.delta//120), "units"))

    def _build_detail(self, parent):
        self.detail_title = tk.Label(parent, text="👈 Нажмите на любой пак", bg=BG, fg=ACCENT, font=("Segoe UI", 12, "bold"), wraplength=340, justify="left")
        self.detail_title.pack(anchor="w", padx=10, pady=(8, 4))

        gal_outer = tk.Frame(parent, bg=SURFACE, height=180)
        gal_outer.pack(fill="x", padx=10, pady=4)
        gal_outer.pack_propagate(False)
        self.gal_canvas = tk.Canvas(gal_outer, bg=SURFACE, height=160, highlightthickness=0)
        gal_hsb = ttk.Scrollbar(gal_outer, orient="horizontal", command=self.gal_canvas.xview)
        self.gal_canvas.configure(xscrollcommand=gal_hsb.set)
        gal_hsb.pack(side="bottom", fill="x")
        self.gal_canvas.pack(side="left", fill="both", expand=True)
        self.gal_inner = tk.Frame(self.gal_canvas, bg=SURFACE)
        self._gal_win = self.gal_canvas.create_window((0, 0), window=self.gal_inner, anchor="nw")
        self.gal_inner.bind("<Configure>", lambda e: self.gal_canvas.configure(scrollregion=self.gal_canvas.bbox("all")))

        self.detail_desc = tk.Text(parent, bg=SURFACE, fg=TEXT, relief="flat", font=("Segoe UI", 9), wrap="word", height=5, state="disabled")
        self.detail_desc.pack(fill="x", padx=10, pady=4)

        dl_lf = ttk.LabelFrame(parent, text=" Скачать версии ")
        dl_lf.pack(fill="both", expand=True, padx=10, pady=4)

        dl_canvas = tk.Canvas(dl_lf, bg=BG, highlightthickness=0, height=120)
        dl_vsb = ttk.Scrollbar(dl_lf, orient="vertical", command=dl_canvas.yview)
        dl_canvas.configure(yscrollcommand=dl_vsb.set)
        dl_vsb.pack(side="right", fill="y")
        dl_canvas.pack(side="left", fill="both", expand=True)
        self.dl_frame = tk.Frame(dl_canvas, bg=BG)
        dl_win = dl_canvas.create_window((0, 0), window=self.dl_frame, anchor="nw")
        self.dl_frame.bind("<Configure>", lambda e: dl_canvas.configure(scrollregion=dl_canvas.bbox("all")))
        dl_canvas.bind("<Configure>", lambda e: dl_canvas.itemconfig(dl_win, width=e.width))

        self.prog_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(parent, variable=self.prog_var, maximum=100)
        self.prog_bar.pack(fill="x", padx=10, pady=(4, 2))
        self.prog_lbl = tk.Label(parent, text="", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        self.prog_lbl.pack()

    def _load_page(self, page):
        if page < 1: return
        self._current_page = page
        self.page_lbl.config(text=f"Стр. {page}")

        for w in self.grid_frame.winfo_children():
            w.destroy()
        self._gallery_phs.clear()
        self._card_images.clear()

        is_expert = "Expert" in self.site_var.get()
        if is_expert:
            cat_url = EXPERT_CATEGORIES.get(self.cat_var.get(), f"{SITE_EXPERT_BASE}/textures/")
            if page == 1:
                url = cat_url
            else:
                base = cat_url.rstrip("/")
                url  = f"{base}/page/{page}/"
            self.set_status(f"Загрузка MinecraftExpert (стр. {page})...")
            threading.Thread(target=self._bg_listing, args=(url, "expert"), daemon=True).start()
        else:
            cat_url = INSIDE_CATEGORIES.get(self.cat_var.get(), f"{SITE_INSIDE_BASE}/resource-packs/")
            if page == 1:
                url = cat_url
            else:
                base = cat_url.rstrip("/").split("?")[0]
                qs   = ("?" + cat_url.split("?")[1]) if "?" in cat_url else ""
                url  = f"{base}/page/{page}/{qs}"
            self.set_status(f"Загрузка Minecraft-Inside (стр. {page})...")
            threading.Thread(target=self._bg_listing, args=(url, "inside"), daemon=True).start()

    def _do_search(self):
        q = self.search_site.get().strip()
        if not q:
            self._load_page(1)
            return
        is_expert = "Expert" in self.site_var.get()
        self._current_page = 1
        self.page_lbl.config(text="Поиск")
        self.set_status("Поиск...")
        for w in self.grid_frame.winfo_children():
            w.destroy()
        if is_expert:
            url = f"{SITE_EXPERT_BASE}/?s=" + urllib.parse.quote(q)
            threading.Thread(target=self._bg_listing, args=(url, "expert"), daemon=True).start()
        else:
            url = f"{SITE_INSIDE_BASE}/search/?q=" + urllib.parse.quote(q) + "&type=resource-packs"
            threading.Thread(target=self._bg_listing, args=(url, "inside"), daemon=True).start()

    def _bg_listing(self, url, site):
        if site == "expert":
            packs = scrape_expert_listing(url)
        else:
            packs = scrape_inside_listing(url)
        self._packs = packs
        self.after(0, lambda: self._render_cards(packs))
        self.after(0, lambda: self.set_status(f"Найдено {len(packs)} паков ({self.site_var.get()})"))

    def _render_cards(self, packs):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self._card_images.clear()

        if not packs:
            tk.Label(self.grid_frame, text="Ничего не найдено. Попробуйте другую категорию или поиск.",
                     bg=BG, fg=SUBTEXT, font=("Segoe UI", 10)).pack(pady=40)
            self.grid_frame.update_idletasks()
            self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))
            return

        COLS = 3
        for i, pack in enumerate(packs):
            row, col = divmod(i, COLS)
            self._make_card(self.grid_frame, pack, row, col)

        self.grid_frame.update_idletasks()
        self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))
        self.grid_canvas.yview_moveto(0)

    def _make_card(self, parent, pack, row, col):
        card = tk.Frame(parent, bg=SURFACE, padx=6, pady=6, cursor="hand2")
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        parent.columnconfigure(col, weight=1)

        img_lbl = tk.Label(card, bg="#2a2b3d", width=25, height=7)
        img_lbl.pack()

        if pack.get("thumb"):
            threading.Thread(target=self._load_thumb, args=(pack["thumb"], img_lbl), daemon=True).start()

        title = pack.get("title", "")
        if len(title) > 36: title = title[:33] + "..."
        tk.Label(card, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 9, "bold"), wraplength=180, justify="center").pack(pady=(4, 2))

        for w in (card, img_lbl):
            w.bind("<Button-1>", lambda e, p=pack: self._open_detail(p))

        def on_enter(e, c=card):
            c.configure(bg="#45475a")
            for child in c.winfo_children():
                try: child.configure(bg="#45475a")
                except Exception: pass
        def on_leave(e, c=card):
            c.configure(bg=SURFACE)
            for child in c.winfo_children():
                try: child.configure(bg=SURFACE)
                except Exception: pass
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

    def _load_thumb(self, url, lbl):
        img = fetch_image_pil(url)
        if not img: return
        img = ImageOps.fit(img, (THUMB_W, THUMB_H), Image.LANCZOS)
        self.after(0, lambda: self._apply_thumb(lbl, img))

    def _apply_thumb(self, lbl, img):
        if not lbl.winfo_exists(): return
        try:
            ph = ImageTk.PhotoImage(img)
            self._card_images.append(ph)
            lbl.configure(image=ph, width=THUMB_W, height=THUMB_H)
            lbl._ph = ph
        except Exception:
            pass

    def _open_detail(self, pack):
        self.detail_title.config(text=f"Загрузка: {pack.get('title', '')}...")
        for w in self.gal_inner.winfo_children():
            w.destroy()
        self._gallery_phs.clear()
        for w in self.dl_frame.winfo_children():
            w.destroy()
        self.detail_desc.configure(state="normal")
        self.detail_desc.delete("1.0", "end")
        self.detail_desc.configure(state="disabled")
        self.prog_var.set(0)
        self.prog_lbl.config(text="")
        threading.Thread(target=self._bg_detail, args=(pack,), daemon=True).start()

    def _bg_detail(self, pack):
        if pack.get("source") == "expert":
            detail = scrape_expert_detail(pack["url"])
        else:
            detail = scrape_inside_detail(pack["url"])
        self.after(0, lambda: self._render_detail(pack, detail))

    def _render_detail(self, pack, detail):
        title = detail.get("title") or pack["title"]
        self.detail_title.config(text=title)
        self.detail_desc.configure(state="normal")
        self.detail_desc.delete("1.0", "end")
        self.detail_desc.insert("1.0", detail.get("description", ""))
        self.detail_desc.configure(state="disabled")

        for url in (detail.get("images") or [])[:8]:
            threading.Thread(target=self._load_gallery_img, args=(url,), daemon=True).start()

        dls = detail.get("downloads", [])
        if not dls:
            tk.Label(self.dl_frame, text="Файлы не найдены", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(pady=6)
        for item in dls:
            label = item.get("label", "Скачать")
            if len(label) > 55: label = label[:52] + "..."
            btn = ttk.Button(self.dl_frame, text=label, command=lambda it=item: self._handle_download(it))
            btn.pack(fill="x", pady=2)
        self.set_status(f"Выбран: {title}")

    def _load_gallery_img(self, url):
        img = fetch_image_pil(url)
        if not img: return
        h = 150
        ratio = h / max(1, img.height)
        w = max(1, int(img.width * ratio))
        img = img.resize((w, h), Image.LANCZOS)
        self.after(0, lambda: self._apply_gallery_img(img, url))

    def _apply_gallery_img(self, img, url):
        if not self.gal_inner.winfo_exists(): return
        try:
            ph = ImageTk.PhotoImage(img)
            self._gallery_phs.append(ph)
            lbl = tk.Label(self.gal_inner, image=ph, bg=SURFACE, cursor="hand2")
            lbl.pack(side="left", padx=4, pady=4)
            lbl._ph = ph
            lbl.bind("<Button-1>", lambda e, u=url: self._view_full(u))
        except Exception:
            pass

    def _view_full(self, url):
        threading.Thread(target=self._worker_view_full, args=(url,), daemon=True).start()

    def _worker_view_full(self, url):
        img = fetch_image_pil(url)
        if not img: return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        img.save(tmp, "PNG")
        os.startfile(tmp)

    def _handle_download(self, item):
        url = item.get("url", "")
        if item.get("is_cloud", False):
            webbrowser.open(url)
            messagebox.showinfo("Ссылка открыта в браузере",
                "Страница облачного хранилища открыта в браузере.\n\nСкачайте архив и поместите его в папку:\n" +
                str(Path(self.mc_path_var.get()) / "resourcepacks"))
            return

        mc = Path(self.mc_path_var.get())
        init_dir = str(mc / "resourcepacks") if mc.exists() else str(Path.home())
        save_dir = filedialog.askdirectory(title="Сохранить текстурпак в...", initialdir=init_dir)
        if not save_dir: return
        threading.Thread(target=self._bg_download, args=(url, Path(save_dir)), daemon=True).start()

    def _bg_download(self, dl_url, save_dir):
        self.after(0, lambda: self.set_status("Подготовка ссылки..."))
        real_url = resolve_download(dl_url)
        fname = real_url.split("/")[-1].split("?")[0] or "resourcepack.zip"
        if not (fname.endswith(".zip") or fname.endswith(".jar")):
            fname += ".zip"
        dest = save_dir / fname

        def prog_cb(done, total):
            if total > 0:
                pct = done / total * 100
                self.after(0, lambda p=pct, d=done, t=total: self._upd_prog(p, d, t))

        self.after(0, lambda: self.set_status(f"Скачивание {fname}..."))
        ok = download_file(real_url, dest, prog_cb)
        if ok:
            self.after(0, lambda: self.set_status(f"Сохранено: {dest.name}"))
            self.after(0, lambda: messagebox.showinfo("Готово!", f"Текстурпак сохранен в:\n{dest}\n\nВ игре: Настройки > Пакеты ресурсов > выберите его."))
        else:
            self.after(0, lambda: self.set_status("Ошибка скачивания", err=True))
            self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось скачать. Ссылка:\n" + dl_url))

    def _upd_prog(self, pct, done, total):
        self.prog_var.set(pct)
        self.prog_lbl.config(text=f"{done//1024} KB / {total//1024} KB ({pct:.0f}%)")

# ── Main Application Window ───────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Texture Replacer v2.7")
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
        self.browse_tab = BrowseTab(nb, self.mc_path_var, self._set_status)
        nb.add(self.tex_tab,    text="  ✏️ Заменить на свои фото  ")
        nb.add(self.browse_tab, text="  🌐 Каталог текстур (Minecraft-Inside + MinecraftExpert)  ")

        # Load first page
        self.after(300, lambda: self.browse_tab._load_page(1))

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