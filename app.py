"""
Minecraft Texture Replacer v2.5
=================================
Tab 1 - Replace textures with your own photos
Tab 2 - Browse packs from Minecraft-Inside.ru AND Modrinth (10,000+ packs)
Works directly with Python OR compiles to standalone .exe via GitHub Actions.
"""
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
    def __init__(self, missing):
        super().__init__()
        self.missing = missing
        self.title("Minecraft Texture Replacer - Setup")
        self.geometry("480x300")
        self.resizable(False, False)
        self.configure(bg=BG_BOOT)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"480x300+{(sw-480)//2}+{(sh-300)//2}")
        self._build()
        self._success = False
    def _build(self):
