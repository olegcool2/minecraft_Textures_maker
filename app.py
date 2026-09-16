"""
Minecraft Texture Replacer v2.1
=================================
Self-bootstrapping: auto-installs Pillow, requests, beautifulsoup4 on first run.
Users just need Python installed. Run: python app.py (or double-click run.bat)
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP  (stdlib only - no third-party imports here)
# ═══════════════════════════════════════════════════════════════════════════════
import sys, subprocess, threading, importlib
import tkinter as tk
from tkinter import ttk

REQUIRED = [
    ("PIL",      "pillow>=10.0.0"),
    ("requests", "requests>=2.31.0"),
    ("bs4",      "beautifulsoup4>=4.12.0"),
]

BG_BOOT  = "#1e1e2e"
FG_BOOT  = "#cdd6f4"
ACC_BOOT = "#89b4fa"
GRN_BOOT = "#a6e3a1"
RED_BOOT = "#f38ba8"


def _check_missing():
    missing = []
    for mod, pkg in REQUIRED:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append((mod, pkg))
    return missing


class SplashInstaller(tk.Tk):
    """Shown while dependencies are being installed."""

    def __init__(self, missing):
        super().__init__()
        self.missing = missing
        self.title("Minecraft Texture Replacer – Setup")
        self.geometry("480x300")
        self.resizable(False, False)
        self.configure(bg=BG_BOOT)
        # Center on screen
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"480x300+{(sw-480)//2}+{(sh-300)//2}")
        self._build()
        self._success = False

    def _build(self):
        tk.Label(self, text="Minecraft Texture Replacer",
                 font=("Segoe UI", 16, "bold"),
                 bg=BG_BOOT, fg=ACC_BOOT).pack(pady=(28, 4))
        tk.Label(self,
                 text="Installing required packages...",
                 font=("Segoe UI", 10),
                 bg=BG_BOOT, fg=FG_BOOT).pack(pady=(0, 20))

        self.log_frame = tk.Frame(self, bg=BG_BOOT)
        self.log_frame.pack(fill="x", padx=40)
        self._pkg_labels = {}
        for mod, pkg in self.missing:
            row = tk.Frame(self.log_frame, bg=BG_BOOT)
            row.pack(fill="x", pady=2)
            name = pkg.split(">=")[0].split(">")[0]
            tk.Label(row, text=f"  {name}", width=22, anchor="w",
                     font=("Consolas", 10),
                     bg=BG_BOOT, fg=FG_BOOT).pack(side="left")
            status = tk.Label(row, text="waiting...", anchor="w",
                              font=("Consolas", 10),
                              bg=BG_BOOT, fg=FG_BOOT)
            status.pack(side="left")
            self._pkg_labels[mod] = status

        self.prog = ttk.Progressbar(self, mode="indeterminate", length=400)
        self.prog.pack(pady=20)

        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TProgressbar", troughcolor="#313244",
                    background=ACC_BOOT, borderwidth=0)

        self.status_lbl = tk.Label(self, text="",
                                   font=("Segoe UI", 9),
                                   bg=BG_BOOT, fg=FG_BOOT)
        self.status_lbl.pack()

    def _set_status(self, mod, text, color=None):
        lbl = self._pkg_labels.get(mod)
        if lbl:
            lbl.config(text=text, fg=color or FG_BOOT)

    def _set_bottom(self, text, color=None):
        self.status_lbl.config(text=text, fg=color or FG_BOOT)

    def run(self):
        self.prog.start(12)
        threading.Thread(target=self._install_all, daemon=True).start()
        self.mainloop()
        return self._success

    def _install_all(self):
        all_ok = True
        for mod, pkg in self.missing:
            name = pkg.split(">=")[0]
            self.after(0, lambda m=mod: self._set_status(m, "installing...", ACC_BOOT))
            self.after(0, lambda n=name: self._set_bottom(f"pip install {n}"))
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "--quiet", pkg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.after(0, lambda m=mod: self._set_status(m, "OK", GRN_BOOT))
            except Exception as e:
                all_ok = False
                self.after(0, lambda m=mod, er=str(e):
                           self._set_status(m, f"FAILED: {er}", RED_BOOT))
        self._success = all_ok
        if all_ok:
            self.after(0, lambda: self._set_bottom("All done! Launching...", GRN_BOOT))
            self.after(800, self.destroy)
        else:
            self.after(0, lambda: self._set_bottom(
                "Some packages failed. Try: pip install pillow requests beautifulsoup4",
                RED_BOOT))


def _bootstrap():
    """Check deps, show splash installer if needed. Returns True if ready.

    When running as a PyInstaller bundle (sys.frozen=True), all deps are
    already bundled inside the .exe — skip the installer entirely.
    """
    # Running as compiled .exe — deps are embedded, nothing to install
    if getattr(sys, "frozen", False):
        return True

    missing = _check_missing()
    if not missing:
        return True
    splash = SplashInstaller(missing)
    ok = splash.run()
    if not ok:
        print("Could not install required packages.",
              "Run manually: pip install pillow requests beautifulsoup4")
    return ok


# ─── Run bootstrap BEFORE importing third-party packages ──────────────────────
if not _bootstrap():
    sys.exit(1)

# ─── Now safe to import everything ────────────────────────────────────────────
import io, json, os, re, shutil, tempfile, time, zipfile
import urllib.parse
from pathlib import Path
from tkinter import filedialog, messagebox

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps, ImageTk

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS AND GLOBALS
# ═══════════════════════════════════════════════════════════════════════════════

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
SITE_BASE = "https://minecraft-inside.ru"
SITE_CATEGORIES = {
    "Все":          SITE_BASE + "/resource-packs/",
    "PvP":          SITE_BASE + "/resource-packs/pvp/",
    "Реалистичные": SITE_BASE + "/resource-packs/realism/",
    "3D":           SITE_BASE + "/resource-packs/3d/",
    "Современные":  SITE_BASE + "/resource-packs/modern/",
    "Средневековые":SITE_BASE + "/resource-packs/medieval/",
    "Мультяшные":   SITE_BASE + "/resource-packs/mult/",
    "FPS":          SITE_BASE + "/resource-packs/fps/",
    "Популярные":   SITE_BASE + "/resource-packs/?sort=rating",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru,en;q=0.9",
}
THUMB_W, THUMB_H = 200, 140
IMG_PLACEHOLDER = None


# ═══════════════════════════════════════════════════════════════════════════════
# TEXTURE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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
    with open(pack_dir / "pack.mcmeta", "w", encoding="utf-8") as f:
        json.dump({"pack": {"pack_format": 34, "description": desc}}, f, indent=2)
    for r in replacements:
        dest = pack_dir / Path(r["mc_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        r["image"].save(dest, "PNG")
    return pack_dir


def zip_pack(pack_dir):
    zp = pack_dir.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pack_dir.rglob("*"):
            zf.write(f, f.relative_to(pack_dir.parent))
    return zp


def install_pack(pack_dir, mc):
    dest = mc / "resourcepacks" / pack_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(pack_dir, dest)
    return dest


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER  (minecraft-inside.ru)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_html(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            if i == retries - 1:
                print(f"[fetch] {url}: {e}")
            time.sleep(1)
    return None


def scrape_listing(url):
    soup = fetch_html(url)
    if not soup:
        return []
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
                thumb = SITE_BASE + thumb
        pack_url = href if href.startswith("http") else SITE_BASE + href
        packs.append({"title": title, "url": pack_url, "thumb": thumb})
    return packs


def scrape_pack_detail(url):
    soup = fetch_html(url)
    if not soup: return {}
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    images, seen_imgs = [], set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src in seen_imgs: continue
        try:
            if int(img.get("width", 999)) < 100: continue
            if int(img.get("height", 999)) < 100: continue
        except Exception:
            pass
        if any(x in src for x in ["/avatars/", "/icons/", "/emoji/", "/logo"]):
            continue
        full = src if src.startswith("http") else SITE_BASE + src
        seen_imgs.add(src)
        images.append(full)
    downloads = []
    for a in soup.find_all("a", href=re.compile(r"/download/\d+/")):
        label = a.get_text(strip=True)
        href  = a["href"]
        dl_url = href if href.startswith("http") else SITE_BASE + href
        entry = {"label": label or "Download", "url": dl_url}
        if entry not in downloads:
            downloads.append(entry)
    desc_parts = []
    for p in soup.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 40 and "Скачать" not in txt and "http" not in txt:
            desc_parts.append(txt)
        if len(desc_parts) >= 4: break
    return {"title": title, "images": images,
            "downloads": downloads,
            "description": "\n\n".join(desc_parts[:3])}


def fetch_image(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        return None


def resolve_download(dl_url):
    try:
        resp = requests.get(dl_url, headers=HEADERS, timeout=15, allow_redirects=True)
        if "text/html" in resp.headers.get("content-type", ""):
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(href.endswith(ext) for ext in [".zip", ".jar"]):
                    return href if href.startswith("http") else SITE_BASE + href
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

# ═══════════════════════════════════════════════════════════════════════════════
# STYLE
# ═══════════════════════════════════════════════════════════════════════════════

def apply_style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE, font=("Segoe UI", 10))
    s.configure("TButton", background=ACCENT, foreground="#1e1e2e",
                font=("Segoe UI", 10, "bold"), relief="flat", padding=(10, 5))
    s.map("TButton", background=[("active", "#74c7ec"), ("pressed", "#89dceb")])
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, insertcolor=TEXT)
    s.configure("TCombobox", fieldbackground=SURFACE, foreground=TEXT, selectbackground=ACCENT)
    s.configure("Treeview", background=SURFACE, foreground=TEXT, rowheight=26,
                fieldbackground=SURFACE, borderwidth=0)
    s.configure("Treeview.Heading", background=BG, foreground=ACCENT,
                font=("Segoe UI", 10, "bold"))
    s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#1e1e2e")])
    s.configure("TNotebook", background=BG, borderwidth=0)
    s.configure("TNotebook.Tab", background=SURFACE, foreground=SUBTEXT,
                padding=(14, 7), font=("Segoe UI", 11, "bold"))
    s.map("TNotebook.Tab", background=[("selected", ACCENT)],
          foreground=[("selected", "#1e1e2e")])
    s.configure("TFrame", background=BG)
    s.configure("TScrollbar", background=SURFACE, troughcolor=BG,
                arrowcolor=SUBTEXT, borderwidth=0)
    s.configure("TCheckbutton", background=BG, foreground=TEXT)
    s.configure("TRadiobutton", background=BG, foreground=TEXT)
    s.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT, borderwidth=0)
    s.configure("TLabelframe", background=BG, foreground=ACCENT)
    s.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                font=("Segoe UI", 10, "bold"))


def make_placeholder(size=(128, 128)):
    img = Image.new("RGBA", size, (49, 50, 68, 255))
    return ImageTk.PhotoImage(img)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – MY PHOTOS
# ═══════════════════════════════════════════════════════════════════════════════

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

    def _build(self):
        ctrl = tk.Frame(self, bg=BG, pady=6)
        ctrl.pack(fill="x", padx=14)
        tk.Label(ctrl, text="Version:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.jar_combo = ttk.Combobox(ctrl, state="readonly", width=28)
        self.jar_combo.pack(side="left", padx=6)
        self.jar_combo.bind("<<ComboboxSelected>>", self._on_jar)
        ttk.Button(ctrl, text="Load versions", command=self._load_jars).pack(side="left", padx=2)

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
        tk.Label(bot, text="Pack name:", bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(16, 4))
        tk.Entry(bot, textvariable=self.pack_name, width=24, bg=BG, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=(0, 10))
        ttk.Button(bot, text="Save Folder", command=self._save_folder).pack(side="left", padx=3)
        ttk.Button(bot, text="Save ZIP",    command=self._save_zip).pack(side="left", padx=3)
        ttk.Button(bot, text="Install to MC", command=self._install).pack(side="left", padx=3)

    def _build_left(self, p):
        r = tk.Frame(p, bg=BG, pady=2)
        r.pack(fill="x")
        tk.Label(r, text="Category:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.cat_combo = ttk.Combobox(r, state="readonly", values=list(TEXTURE_CATEGORIES.keys()), width=22)
        self.cat_combo.current(0)
        self.cat_combo.pack(side="left", padx=6)
        self.cat_combo.bind("<<ComboboxSelected>>", self._filter)
        r2 = tk.Frame(p, bg=BG, pady=2)
        r2.pack(fill="x")
        tk.Label(r2, text="Search:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        tk.Entry(r2, textvariable=self.search_var, width=24, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=6)
        lf = tk.Frame(p, bg=BG)
        lf.pack(fill="both", expand=True, pady=4)
        self.tex_list = tk.Listbox(lf, bg=SURFACE, fg=TEXT, selectbackground=ACCENT,
                                   selectforeground="#1e1e2e", relief="flat",
                                   font=("Consolas", 9), activestyle="none")
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
        self.orig_lbl, self.orig_sz = card(prev, "Original")
        self.res_lbl,  self.res_sz  = card(prev, "Result")
        sf = ttk.LabelFrame(p, text=" Conversion settings ")
        sf.pack(fill="x", pady=4)
        mr = tk.Frame(sf, bg=BG)
        mr.pack(fill="x", padx=8, pady=4)
        tk.Label(mr, text="Resize:", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        for txt, val in [("Fill", "fill"), ("Fit", "fit"), ("Stretch", "stretch"), ("Tile", "tile")]:
            tk.Radiobutton(mr, text=txt, variable=self.fit_mode, value=val,
                           bg=BG, fg=TEXT, selectcolor=SURFACE, activebackground=BG,
                           command=self._update_preview).pack(side="left", padx=5)
        sr = tk.Frame(sf, bg=BG)
        sr.pack(fill="x", padx=8, pady=4)
        tk.Label(sr, text="Size:", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        self.size_combo = ttk.Combobox(sr, values=[str(s) for s in TEXTURE_SIZES],
                                       width=6, state="readonly")
        self.size_combo.set("16")
        self.size_combo.pack(side="left", padx=(4, 14))
        self.size_combo.bind("<<ComboboxSelected>>", lambda e: (
            self.size_var.set(int(self.size_combo.get())),
            self._update_preview()))
        tk.Checkbutton(sr, text="Preserve alpha", variable=self.keep_alpha,
                       bg=BG, fg=TEXT, selectcolor=SURFACE, activebackground=BG,
                       command=self._update_preview).pack(side="left")
        pr = tk.Frame(p, bg=BG)
        pr.pack(fill="x", pady=6)
        ttk.Button(pr, text="Choose photo", command=self._browse_img).pack(side="left")
        self.photo_lbl = tk.Label(pr, text="No file selected", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))
        self.photo_lbl.pack(side="left", padx=10)
        ttk.Button(p, text="Add replacement", command=self._add).pack(fill="x", pady=4)
        rf = ttk.LabelFrame(p, text=" Planned replacements ")
        rf.pack(fill="both", expand=True, pady=4)
        cols = ("texture", "photo", "mode", "size")
        self.rep_tree = ttk.Treeview(rf, columns=cols, show="headings", height=6)
        for col, hd, w in zip(cols, ["Texture", "Photo", "Mode", "Size"], [240, 150, 80, 60]):
            self.rep_tree.heading(col, text=hd)
            self.rep_tree.column(col, width=w, anchor="w")
        rsb = ttk.Scrollbar(rf, command=self.rep_tree.yview)
        self.rep_tree.configure(yscrollcommand=rsb.set)
        self.rep_tree.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")
        ttk.Button(p, text="Remove selected", command=self._remove).pack(fill="x")

    def _load_jars(self):
        jars = find_mc_jars(Path(self.mc_path_var.get()))
        if not jars:
            messagebox.showwarning("Not found", "No .jar version files found.\nCheck your .minecraft path.")
            return
        self._jars = jars
        self.jar_combo["values"] = [j.stem for j in jars]
        self.jar_combo.current(0)
        self._on_jar()

    def _on_jar(self, *_):
        idx = self.jar_combo.current()
        if idx < 0: return
        self.selected_jar = self._jars[idx]
        self.set_status("Loading textures...")
        threading.Thread(target=self._bg_load, daemon=True).start()

    def _bg_load(self):
        tx = list_textures(self.selected_jar)
        self.all_textures = tx
        self.after(0, self._filter)
        self.after(0, lambda: self.set_status(f"Loaded {len(tx)} textures"))

    def _filter(self, *_):
        cat = TEXTURE_CATEGORIES.get(self.cat_combo.get(), "")
        pfx = f"assets/minecraft/{cat}" if cat else "assets/minecraft/textures"
        q   = self.search_var.get().lower()
        self.filtered_textures = [t for t in self.all_textures if t.startswith(pfx) and q in t.lower()]
        self.tex_list.delete(0, "end")
        for t in self.filtered_textures:
            self.tex_list.insert("end", Path(t).name)
        self.cnt.config(text=f"{len(self.filtered_textures)} textures")

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
        p = filedialog.askopenfilename(title="Choose image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"), ("All", "*.*")])
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
            self.set_status(f"Preview error: {e}", err=True)

    def _add(self):
        if not self.selected_texture:
            messagebox.showwarning("No texture", "Select a texture from the list first.")
            return
        if not self.user_image_path:
            messagebox.showwarning("No photo", "Choose a photo first.")
            return
        sz   = self.size_var.get()
        mode = self.fit_mode.get()
        img  = process_image(self.user_image_path, (sz, sz), mode, self.keep_alpha.get())
        self.replacements.append({"mc_path": self.selected_texture, "image": img})
        self.rep_tree.insert("", "end", values=(
            Path(self.selected_texture).name, Path(self.user_image_path).name, mode, f"{sz}px"))
        self.set_status(f"Added: {Path(self.selected_texture).name}")

    def _remove(self):
        sel = self.rep_tree.selection()
        if not sel: return
        idx = self.rep_tree.index(sel[0])
        self.rep_tree.delete(sel[0])
        if 0 <= idx < len(self.replacements):
            self.replacements.pop(idx)

    def _check(self):
        if not self.replacements:
            messagebox.showwarning("Empty", "Add at least one replacement first.")
            return False
        return True

    def _save_folder(self):
        if not self._check(): return
        d = filedialog.askdirectory(title="Output folder")
        if not d: return
        pd = build_pack(Path(d) / self.pack_name.get(), self.replacements)
        self.set_status(f"Saved: {pd}")
        messagebox.showinfo("Done!", f"Resource pack saved:\n{pd}")

    def _save_zip(self):
        if not self._check(): return
        d = filedialog.askdirectory(title="Output folder")
        if not d: return
        pd = Path(d) / self.pack_name.get()
        build_pack(pd, self.replacements)
        zp = zip_pack(pd)
        shutil.rmtree(pd, ignore_errors=True)
        self.set_status(f"Saved: {zp}")
        messagebox.showinfo("Done!", f"ZIP saved:\n{zp}")

    def _install(self):
        if not self._check(): return
        mc = Path(self.mc_path_var.get())
        if not mc.exists():
            messagebox.showerror("Error", f".minecraft not found:\n{mc}")
            return
        with tempfile.TemporaryDirectory() as tmp:
            pd   = build_pack(Path(tmp) / self.pack_name.get(), self.replacements)
            dest = install_pack(pd, mc)
        self.set_status(f"Installed: {dest}")
        messagebox.showinfo("Installed!",
            f"Installed to:\n{dest}\n\nOptions > Resource Packs > select it")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – BROWSE PACKS
# ═══════════════════════════════════════════════════════════════════════════════

class BrowseTab(tk.Frame):
    def __init__(self, parent, mc_path_var, status_fn):
        super().__init__(parent, bg=BG)
        self.mc_path_var = mc_path_var
        self.set_status = status_fn
        self._packs = []
        self._thumb_cache = {}
        self._gallery_phs = []
        self._current_page = 1
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=BG, pady=6)
        top.pack(fill="x", padx=14)
        tk.Label(top, text="Category:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left")
        self.cat_var = tk.StringVar(value="Все")
        cat_cb = ttk.Combobox(top, textvariable=self.cat_var,
                              values=list(SITE_CATEGORIES.keys()), state="readonly", width=18)
        cat_cb.pack(side="left", padx=6)
        cat_cb.bind("<<ComboboxSelected>>", lambda e: self._load_page(1))
        tk.Label(top, text="Search:", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))
        self.search_site = tk.StringVar()
        tk.Entry(top, textvariable=self.search_site, width=22, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left", padx=4)
        ttk.Button(top, text="Search", command=self._do_search).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh", command=lambda: self._load_page(1)).pack(side="left", padx=2)
        pag = tk.Frame(top, bg=BG)
        pag.pack(side="right")
        ttk.Button(pag, text="< Prev",
                   command=lambda: self._load_page(self._current_page - 1)).pack(side="left", padx=2)
        self.page_lbl = tk.Label(pag, text="Page 1", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))
        self.page_lbl.pack(side="left", padx=6)
        ttk.Button(pag, text="Next >",
                   command=lambda: self._load_page(self._current_page + 1)).pack(side="left", padx=2)

        paned = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=480)
        self._build_grid(left)
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=360)
        self._build_detail(right)

    def _build_grid(self, parent):
        self.grid_canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.grid_canvas.yview)
        self.grid_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.grid_canvas.pack(side="left", fill="both", expand=True)
        self.grid_frame = tk.Frame(self.grid_canvas, bg=BG)
        self._grid_win = self.grid_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>",
            lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self.grid_canvas.bind("<Configure>",
            lambda e: self.grid_canvas.itemconfig(self._grid_win, width=e.width))
        self.grid_canvas.bind_all("<MouseWheel>",
            lambda e: self.grid_canvas.yview_scroll(-1*(e.delta//120), "units"))

    def _build_detail(self, parent):
        self.detail_title = tk.Label(parent, text="<-- Click a pack",
                                     bg=BG, fg=ACCENT,
                                     font=("Segoe UI", 12, "bold"),
                                     wraplength=340, justify="left")
        self.detail_title.pack(anchor="w", padx=10, pady=(8, 4))
        # Gallery
        gal_outer = tk.Frame(parent, bg=SURFACE, height=190)
        gal_outer.pack(fill="x", padx=10, pady=4)
        gal_outer.pack_propagate(False)
        self.gal_canvas = tk.Canvas(gal_outer, bg=SURFACE, height=170, highlightthickness=0)
        gal_hsb = ttk.Scrollbar(gal_outer, orient="horizontal", command=self.gal_canvas.xview)
        self.gal_canvas.configure(xscrollcommand=gal_hsb.set)
        gal_hsb.pack(side="bottom", fill="x")
        self.gal_canvas.pack(side="left", fill="both", expand=True)
        self.gal_inner = tk.Frame(self.gal_canvas, bg=SURFACE)
        self._gal_win = self.gal_canvas.create_window((0, 0), window=self.gal_inner, anchor="nw")
        self.gal_inner.bind("<Configure>",
            lambda e: self.gal_canvas.configure(scrollregion=self.gal_canvas.bbox("all")))
        # Description
        self.detail_desc = tk.Text(parent, bg=SURFACE, fg=TEXT, relief="flat",
                                   font=("Segoe UI", 9), wrap="word", height=5, state="disabled")
        self.detail_desc.pack(fill="x", padx=10, pady=4)
        # Downloads
        dl_lf = ttk.LabelFrame(parent, text=" Downloads ")
        dl_lf.pack(fill="x", padx=10, pady=4)
        self.dl_frame = tk.Frame(dl_lf, bg=BG)
        self.dl_frame.pack(fill="x", padx=4, pady=4)
        # Progress
        self.prog_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(parent, variable=self.prog_var, maximum=100)
        self.prog_bar.pack(fill="x", padx=10, pady=(0, 2))
        self.prog_lbl = tk.Label(parent, text="", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        self.prog_lbl.pack()

    def _load_page(self, page):
        if page < 1: return
        self._current_page = page
        cat_url = SITE_CATEGORIES.get(self.cat_var.get(), SITE_BASE + "/resource-packs/")
        if page == 1:
            url = cat_url
        else:
            base = cat_url.rstrip("/").split("?")[0]
            qs   = ("?" + cat_url.split("?")[1]) if "?" in cat_url else ""
            url  = f"{base}/page/{page}/{qs}"
        self.page_lbl.config(text=f"Page {page}")
        self.set_status(f"Loading page {page}...")
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self._gallery_phs.clear()
        threading.Thread(target=self._bg_listing, args=(url,), daemon=True).start()

    def _do_search(self):
        q = self.search_site.get().strip()
        if not q:
            self._load_page(1)
            return
        url = SITE_BASE + "/search/?q=" + urllib.parse.quote(q) + "&type=resource-packs"
        self._current_page = 1
        self.page_lbl.config(text="Search")
        self.set_status("Searching...")
        for w in self.grid_frame.winfo_children():
            w.destroy()
        threading.Thread(target=self._bg_listing, args=(url,), daemon=True).start()

    def _bg_listing(self, url):
        packs = scrape_listing(url)
        self._packs = packs
        self.after(0, lambda: self._render_cards(packs))
        self.after(0, lambda: self.set_status(f"Found {len(packs)} packs"))

    def _render_cards(self, packs):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        if not packs:
            tk.Label(self.grid_frame, text="No packs found. Try another category or page.",
                     bg=BG, fg=SUBTEXT, font=("Segoe UI", 10)).pack(pady=20)
            return
        COLS = 3
        for i, pack in enumerate(packs):
            row, col = divmod(i, COLS)
            self._make_card(self.grid_frame, pack, row, col)

    def _make_card(self, parent, pack, row, col):
        card = tk.Frame(parent, bg=SURFACE, padx=6, pady=6, cursor="hand2")
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        parent.columnconfigure(col, weight=1)
        if IMG_PLACEHOLDER:
            img_lbl = tk.Label(card, image=IMG_PLACEHOLDER, bg=SURFACE)
        else:
            img_lbl = tk.Label(card, bg=SURFACE, width=THUMB_W, height=THUMB_H)
        img_lbl.pack()
        if pack.get("thumb"):
            threading.Thread(target=self._load_thumb, args=(pack["thumb"], img_lbl),
                             daemon=True).start()
        title = pack["title"]
        if len(title) > 38: title = title[:35] + "..."
        tk.Label(card, text=title, bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 9, "bold"), wraplength=190, justify="center").pack(pady=(4, 2))
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
        if url in self._thumb_cache:
            ph = self._thumb_cache[url]
        else:
            img = fetch_image(url)
            if not img: return
            img = ImageOps.fit(img, (THUMB_W, THUMB_H), Image.LANCZOS)
            ph  = ImageTk.PhotoImage(img)
            self._thumb_cache[url] = ph
        self.after(0, lambda: self._set_thumb(lbl, ph))

    def _set_thumb(self, lbl, ph):
        try:
            lbl.configure(image=ph)
            lbl._ph = ph
        except Exception:
            pass

    def _open_detail(self, pack):
        self.detail_title.config(text="Loading...")
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
        detail = scrape_pack_detail(pack["url"])
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
        for item in (detail.get("downloads") or []):
            label = item.get("label", "Download")
            if len(label) > 55: label = label[:52] + "..."
            btn = ttk.Button(self.dl_frame,
                             text="Download: " + label,
                             command=lambda u=item["url"]: self._download(u))
            btn.pack(fill="x", pady=2)
        self.set_status(f"Loaded: {title}")

    def _load_gallery_img(self, url):
        img = fetch_image(url)
        if not img: return
        h = 160
        ratio = h / img.height
        w = max(1, int(img.width * ratio))
        img = img.resize((w, h), Image.LANCZOS)
        ph = ImageTk.PhotoImage(img)
        self.after(0, lambda: self._add_gallery_img(ph, url))

    def _add_gallery_img(self, ph, url):
        self._gallery_phs.append(ph)
        lbl = tk.Label(self.gal_inner, image=ph, bg=SURFACE, cursor="hand2")
        lbl.pack(side="left", padx=4, pady=4)
        lbl._ph = ph
        lbl.bind("<Button-1>", lambda e, u=url: self._view_full(u))

    def _view_full(self, url):
        img = fetch_image(url)
        if not img: return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        img.save(tmp, "PNG")
        os.startfile(tmp)

    def _download(self, dl_url):
        mc = Path(self.mc_path_var.get())
        init_dir = str(mc / "resourcepacks") if mc.exists() else str(Path.home())
        save_dir = filedialog.askdirectory(title="Save pack to...", initialdir=init_dir)
        if not save_dir: return
        threading.Thread(target=self._bg_download,
                         args=(dl_url, Path(save_dir)), daemon=True).start()

    def _bg_download(self, dl_url, save_dir):
        self.after(0, lambda: self.set_status("Resolving download link..."))
        real_url = resolve_download(dl_url)
        fname = real_url.split("/")[-1].split("?")[0] or "resourcepack.zip"
        if not (fname.endswith(".zip") or fname.endswith(".jar")):
            fname += ".zip"
        dest = save_dir / fname
        def prog_cb(done, total):
            if total > 0:
                pct = done / total * 100
                self.after(0, lambda p=pct, d=done, t=total: self._upd_prog(p, d, t))
        self.after(0, lambda: self.set_status(f"Downloading {fname}..."))
        ok = download_file(real_url, dest, prog_cb)
        if ok:
            self.after(0, lambda: self.set_status(f"Saved: {dest}"))
            self.after(0, lambda: messagebox.showinfo("Downloaded!",
                f"Saved to:\n{dest}\n\nCopy to .minecraft/resourcepacks and enable in-game."))
        else:
            self.after(0, lambda: self.set_status("Download failed", err=True))
            self.after(0, lambda: messagebox.showerror("Error",
                "Download failed.\nOpen in your browser:\n" + dl_url))

    def _upd_prog(self, pct, done, total):
        self.prog_var.set(pct)
        self.prog_lbl.config(text=f"{done//1024} KB / {total//1024} KB  ({pct:.0f}%)")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Texture Replacer")
        self.geometry("1250x820")
        self.minsize(1050, 680)
        self.configure(bg=BG)
        apply_style(self)
        global IMG_PLACEHOLDER
        IMG_PLACEHOLDER = make_placeholder((THUMB_W, THUMB_H))
        self.mc_path_var = tk.StringVar(value=str(DEFAULT_MC))
        # Header
        hdr = tk.Frame(self, bg=SURFACE, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  Minecraft Texture Replacer",
                 font=("Segoe UI", 18, "bold"), bg=SURFACE, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text=".minecraft:", bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(30, 4))
        tk.Entry(hdr, textvariable=self.mc_path_var, width=48,
                 bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat").pack(side="left")
        ttk.Button(hdr, text="...", width=3, command=self._browse_mc).pack(side="left", padx=4)
        # Tabs
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.tex_tab    = TextureTab(nb, self.mc_path_var, self._set_status)
        self.browse_tab = BrowseTab(nb, self.mc_path_var, self._set_status)
        nb.add(self.tex_tab,    text="  My Photos  ")
        nb.add(self.browse_tab, text="  Browse Packs (minecraft-inside.ru)  ")
        # Status bar
        self.status_var = tk.StringVar(value="Ready – all packages installed")
        sb = tk.Frame(self, bg=SURFACE, pady=4)
        sb.pack(fill="x", side="bottom")
        self._status_lbl = tk.Label(sb, textvariable=self.status_var,
                                    bg=SURFACE, fg=SUCCESS, font=("Segoe UI", 9))
        self._status_lbl.pack(side="left", padx=14)

    def _browse_mc(self):
        p = filedialog.askdirectory(title=".minecraft folder")
        if p: self.mc_path_var.set(p)

    def _set_status(self, msg, err=False):
        self.status_var.set(msg)
        self._status_lbl.config(fg=WARNING if err else SUCCESS)


if __name__ == "__main__":
    app = App()
    app.mainloop()