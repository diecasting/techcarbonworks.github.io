import glob

block = "robots:\n  - noindex\n  - nofollow\n"
targets = []
for ext in ("de", "es", "fr", "ja"):
    targets += glob.glob(f"content/**/*.{ext}.md", recursive=True)

print("Target count:", len(targets))
for f in targets:
    with open(f, encoding="utf-8") as fh:
        txt = fh.read()
    if not txt.startswith("---"):
        print("SKIP (no leading fence):", f)
        continue
    new = "---" + "\n" + block + txt[3:]
    with open(f, "w", encoding="utf-8") as out:
        out.write(new)
    print("OK:", f)
