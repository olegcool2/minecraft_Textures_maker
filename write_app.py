import pathlib
p = pathlib.Path(r"C:\Users\user\.gemini\antigravity\scratch\mc-texture-replacer\app.py")
print("Writing app.py ...")
p.write_text("# placeholder", encoding="utf-8")
print("Done:", p.stat().st_size, "bytes")
