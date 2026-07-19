#!/usr/bin/env python3
"""
vault_scan.py — turn an Obsidian vault into graph-data.json for Workshop OS
===========================================================================
"It's not software. It's just folders and text files." — the whole trick.

Usage (on the Mac):
    python3 vault_scan.py "/Users/sciontut/Downloads/ObsidianVault"
    python3 -m http.server 4710
    open http://localhost:4710/workshop-os.html

Options:
    --max-per-folder N   cap nodes per folder (default 2000 = everything)
    --exclude NAME       skip a folder (repeatable), e.g. --exclude Templates

Output: graph-data.json next to workshop-os.html (same directory you run from).
Links come from three sources: [[wikilinks]], folder membership (file → folder
hub), and MOC membership (any note a MOC links to joins that suite).
"""

import json
import re
import sys
from pathlib import Path

FOLDER_TYPE = {
    "": "constitution", "Topics": "topic", "People": "people", "Agencies": "agency",
    "Dashboards": "dashboard", "Study Paths": "study", "Templates": "template",
    "Files": "library", "10_Daily": "daily", "daily": "daily",
}
ROUTERS = {"MEMORY.md", "AGENTS.md", "claude.md", "CLAUDE.md"}
WIKILINK = re.compile(r"\[\[([^\]|#]+)")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    vault = Path(args[0]).expanduser()
    cap = 2000
    excl = set()
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--max-per-folder": cap = int(argv[i+1])
        if a == "--exclude": excl.add(argv[i+1])

    nodes, links, seen = [], [], {}
    per_folder = {}

    def add_node(nid, ntype, note=""):
        if nid in seen: return
        seen[nid] = True
        nodes.append({"id": nid, "type": ntype, "note": note[:280]})

    md_files = sorted(vault.rglob("*.md"))
    print(f"scanning {vault} — {len(md_files)} markdown files")

    for f in md_files:
        rel = f.relative_to(vault)
        if any(p.startswith(".") for p in rel.parts): continue
        folder = rel.parts[0] if len(rel.parts) > 1 else ""
        if folder in excl: continue
        per_folder[folder] = per_folder.get(folder, 0) + 1
        if per_folder[folder] > cap: continue

        name = f.stem
        if f.name in ROUTERS: ntype = "router"
        elif name.startswith("MOC-"): ntype = "moc"
        elif re.match(r"\d{4}-\d{2}-\d{2}", name): ntype = "daily"
        else: ntype = FOLDER_TYPE.get(folder, "topic")

        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        excerpt = " ".join(line.strip() for line in text.splitlines()
                           if line.strip() and not line.startswith(("---", "#", "!")))[:280]
        add_node(name, ntype, excerpt)

        if folder and folder not in excl:
            hub = folder + "/"
            add_node(hub, FOLDER_TYPE.get(folder, "topic"), f"{folder} wing")
            links.append([hub, name])

        for m in WIKILINK.finditer(text):
            target = m.group(1).strip().split("/")[-1]
            if target and target != name:
                links.append([name, target])

    from collections import Counter
    unresolved = Counter(t for s, t in links if t not in seen)
    for t, c in unresolved.items():
        if c >= 2: add_node(t, "topic", "linked but not yet created")
    links = [[s, t] for s, t in links if s in seen and t in seen]
    links = [list(x) for x in dict.fromkeys(tuple(sorted(l)) for l in links)]

    out = Path("graph-data.json")
    out.write_text(json.dumps({"nodes": nodes, "links": links}))
    print(f"→ {out}: {len(nodes)} nodes · {len(links)} links")
    print("serve:  python3 -m http.server 4710   then open http://localhost:4710/workshop-os.html")

if __name__ == "__main__":
    main()
