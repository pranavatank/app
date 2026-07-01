import os, sys

base = r"B:\Study\App\Financial App\ui"
results = []
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if not f.endswith(".py"):
            continue
        p = os.path.join(root, f)
        lines = open(p, encoding="utf-8", errors="replace").readlines()
        for i, line in enumerate(lines, 1):
            # skip comment lines and icons.py registry (those are intentional fallbacks)
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "icons.py" in p and '", "' in line:
                continue
            bad = [c for c in line if ord(c) > 0x2500 and c not in ("═", "─", "│", "┌", "┐", "└", "┘", "●", "○", "▼", "▲", "✓", "✗", "✕", "✔", "·", "—", "…")]
            if bad:
                rel = p.replace(base + chr(92), "").replace(base + "/", "")
                results.append((rel, i, "".join(set(bad)), stripped[:70]))

sys.stdout.buffer.write(b"=== REMAINING EMOJI IN UI ===\n")
for rel, i, chars, ctx in results:
    out = f"{rel} | L{i} | {chars} | {ctx}\n"
    sys.stdout.buffer.write(out.encode("utf-8", "replace"))
print(f"\nTotal: {len(results)} lines", flush=True)
