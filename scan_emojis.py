import os, sys
base = r"B:\Study\App\Financial App"
results = []
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "data", "backups"]]
    for f in files:
        if not f.endswith(".py"):
            continue
        p = os.path.join(root, f)
        lines = open(p, encoding="utf-8", errors="replace").readlines()
        for i, line in enumerate(lines, 1):
            bad = [c for c in line if ord(c) > 0x2500]
            if bad:
                rel = p.replace(base + chr(92), "")
                results.append((rel, i, "".join(set(bad)), line.strip()[:70]))
sys.stdout.buffer.write(b"=== EMOJI SCAN ===\n")
for rel, i, chars, ctx in results:
    out = f"{rel} | L{i} | {chars} | {ctx}\n"
    sys.stdout.buffer.write(out.encode("utf-8", "replace"))
