"""Build the litecode website from docs/*.md. Stdlib only.

  python scripts/build_site.py

Writes docs/<slug>.html for every page, plus sitemap.xml, robots.txt, llms.txt and
llms-full.txt. The Markdown files stay the single source of truth. The home page
(docs/index.html) is hand-written and shares assets/site.css and assets/site.js.
Built by Konko Maji.
"""
from __future__ import annotations
import html, json, re, sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
BASE = "https://konkomaji.github.io/litecode/"
REPO = "https://github.com/konkomaji/litecode"
AUTHOR = {"@type": "Person", "name": "Konko Maji", "email": "mailto:work.konkomaji@gmail.com",
          "url": "https://www.linkedin.com/in/konkomaji/",
          "sameAs": ["https://www.linkedin.com/in/konkomaji/", "https://x.com/konkomaji", "https://github.com/konkomaji"]}

# (slug, source, nav title, section, meta description)
PAGES = [
    ("quickstart", "QUICKSTART.md", "Quickstart", "Get started",
     "Install litecode and run your first local AI coding task in about 10 minutes. Works on Windows, Linux and macOS, with or without a GPU."),
    ("guide", "GUIDE.md", "User guide", "Get started",
     "Complete litecode guide: setup, interface, daily commands, memory, skills, MCP, security, speed tuning and file locations."),
    ("hardware", "HARDWARE.md", "Hardware and models", "Get started",
     "Which AI models litecode runs on your hardware, from a 4 GB laptop without GPU to a 24 GB GPU workstation."),
    ("use-cases", "USE-CASES.md", "Use cases", "Get started",
     "What litecode does: coding and security first, plus writing, study, and data tasks, all offline on your own PC."),
    ("commands", "COMMANDS.md", "Commands", "Use litecode",
     "Every litecode shell command, slash command and config key in one reference."),
    ("security", "SECURITY.md", "Security review", "Use litecode",
     "Offline security review: static scan with zero model tokens, then a model verdict per finding for SQLi, XSS, command injection and more."),
    ("memory", "MEMORY.md", "Memory and learning", "Use litecode",
     "How litecode remembers sessions, learns your preferences and project facts, and exports data for LoRA fine-tuning."),
    ("skills", "SKILLS.md", "Skills", "Use litecode",
     "Create and run litecode skills: SKILL.md instruction packs with project, user and built-in scopes."),
    ("mcp", "MCP.md", "MCP servers", "Use litecode",
     "Connect Model Context Protocol servers to litecode using a standard .mcp.json config file."),
    ("editors", "EDITORS.md", "Editor autocomplete", "Use litecode",
     "Local fill-in-the-middle autocomplete for VS Code and other editors with litecode fim."),
    ("benchmarks", None, "Benchmarks", "Results",
     "Measured results: speed and 30 real coding, security and writing challenges for every model on a low-end Ryzen 3 PC."),
    ("faq", "FAQ.md", "FAQ", "Help",
     "Answers to common questions: running AI coding without a GPU, RAM needs, privacy, models, and how litecode compares."),
    ("troubleshooting", "TROUBLESHOOTING.md", "Troubleshooting", "Help",
     "Fix common litecode problems: engine not found, slow first answer, RAM limits, Windows shell issues and more."),
]
MD2SLUG = {src: slug for slug, src, *_ in PAGES if src}
MD2SLUG.update({"README.md": "index", "BENCHMARKS.md": "benchmarks"})


# ---------------------------------------------------------------- markdown
def slugify(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "section"


def inline(t: str) -> str:
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    t = re.sub(r"`([^`]+)`", keep, t)
    t = html.escape(t, quote=False)

    def link(m):
        text, url = m.group(1), m.group(2)
        page = url.split("#")[0]
        if page.endswith(".md") and "/" not in page:
            slug = MD2SLUG.get(page)
            url = (f"{slug}.html" if slug != "index" else "./") + (("#" + url.split("#")[1]) if "#" in url else "") \
                if slug else f"{REPO}/blob/main/docs/{url}"
        elif not re.match(r"^(https?:|mailto:|#)", url):
            url = f"{REPO}/blob/main/{url}"
        ext = ' rel="noopener"' if url.startswith("http") else ""
        return f'<a href="{html.escape(url, quote=True)}"{ext}>{text}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{html.escape(codes[int(m.group(1))], quote=False)}</code>", t)


def md_to_html(md: str):
    """Returns (title, body_html, toc[(level, id, text)], plain_text)."""
    lines = md.replace("\r\n", "\n").split("\n")
    out, toc, title, i = [], [], "", 0
    used = set()

    def hid(text):
        base = slugify(text)
        k, n = base, 2
        while k in used:
            k, n = f"{base}-{n}", n + 1
        used.add(k)
        return k
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("```"):
            lang = ln[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lv, text = len(m.group(1)), m.group(2).strip()
            if lv == 1 and not title:
                title = re.sub(r"[`*]", "", text)
                i += 1
                continue
            k = hid(text)
            if lv in (2, 3):
                toc.append((lv, k, re.sub(r"<[^>]+>", "", inline(text))))
            anchor = f'<a class="anchor" href="#{k}" aria-label="Link to this section">#</a>' if lv in (2, 3) else ""
            out.append(f'<h{lv} id="{k}">{inline(text)}{anchor}</h{lv}>')
            i += 1
            continue
        if re.match(r"^-{3,}\s*$", ln):
            out.append("<hr>")
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1]):
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            head = cells(ln)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i].replace("\\|", "&#124;")))
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>")
            continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote><p>{inline(' '.join(buf))}</p></blockquote>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            ordered = m.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                m2 = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m2 and (m2.group(2)[0].isdigit()) == ordered:
                    items.append(m2.group(3))
                    i += 1
                elif lines[i].startswith("   ") and items and lines[i].strip():
                    items[-1] += " " + lines[i].strip()
                    i += 1
                else:
                    break
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|```|\||>|\s*([-*]|\d+\.)\s)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")
        else:
            out.append(f"<p>{inline(ln.strip())}</p>")
            i += 1
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", "\n".join(out))).strip()
    return title, "\n".join(out), toc, plain


# ---------------------------------------------------------------- benchmarks
def _cls(p, t):
    r = p / t if t else 0
    return "hi" if r >= 0.75 else "mid" if r >= 0.4 else "lo"


def bench_md_html():
    data_p = DOCS / "data" / "benchmarks.json"
    data = json.loads(data_p.read_text(encoding="utf-8")) if data_p.exists() else {}
    m = data.get("machine", {})
    parts = ["<p>All numbers on this page were measured on one low-end reference PC. "
             "A faster machine gives higher speed. Pass rates depend on the model, not the machine.</p>"]
    if m:
        parts.append("<table><tbody>" + "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>"
                                                for k, v in m.items()) + "</tbody></table>")
    toc = []
    ev = data.get("evals", [])
    if ev:
        toc.append((2, "challenge-results", "Challenge results"))
        parts.append('<h2 id="challenge-results">Challenge results</h2>')
        parts.append(f"<p>{len(ev[0].get('results', [])) or 30} real tasks in 3 levels: basic, medium, hard. "
                     "Each task runs the full agent in auto mode, then a script checks the result by running code. "
                     "Kinds: fix, feature, refactor, security, testfix, qa, data, shell, writing.</p>")
        rows = []
        for e in sorted(ev, key=lambda x: -x["passed"]):
            lv = e.get("by_level", {})
            mins = e.get("seconds", 0) / 60
            bar = f'<span class="bar-s" style="width:{int(80 * e["passed"] / max(1, e["total"]))}px"></span>'
            rows.append(
                f"<tr><td><strong>{html.escape(e['model'].replace('.gguf', ''))}</strong></td>"
                f"<td><span class='score {_cls(e['passed'], e['total'])}'>{e['passed']}/{e['total']}</span>{bar}</td>"
                + "".join(f"<td class='num'>{lv.get(x, '-')}</td>" for x in ("basic", "medium", "hard"))
                + f"<td class='num'>{mins:.0f} min</td><td class='num'>{e.get('protocol_errors', 0)}</td></tr>")
        parts.append("<table><thead><tr><th>Model</th><th>Passed</th><th>Basic</th><th>Medium</th><th>Hard</th>"
                     "<th>Total time</th><th>Protocol errors</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
        kinds = sorted({k for e in ev for k in e.get("by_kind", {})})
        toc.append((3, "by-kind", "By kind of work"))
        parts.append('<h3 id="by-kind">By kind of work</h3>')
        parts.append("<table><thead><tr><th>Model</th>" + "".join(f"<th>{k}</th>" for k in kinds) + "</tr></thead><tbody>"
                     + "".join(f"<tr><td>{html.escape(e['model'].replace('.gguf', ''))}</td>"
                               + "".join(f"<td class='num'>{e.get('by_kind', {}).get(k, '-')}</td>" for k in kinds) + "</tr>"
                               for e in sorted(ev, key=lambda x: -x["passed"])) + "</tbody></table>")
    sp = data.get("speed", [])
    if sp:
        toc.append((2, "speed-and-quick-tests", "Speed and quick tests"))
        parts.append('<h2 id="speed-and-quick-tests">Speed and quick tests</h2>')
        parts.append("<p>Speed from llama-bench (prompt 512 tokens, generate 64 tokens, 4 threads, CPU only). "
                     "Quick tests: 8 single-function coding tasks, 10 vulnerability classes to identify, "
                     "5 small tool-building tasks.</p>")
        parts.append("<table><thead><tr><th>Model</th><th>Prompt tok/s</th><th>Generate tok/s</th><th>Coding</th>"
                     "<th>Vuln ID</th><th>Tools</th></tr></thead><tbody>" + "".join(
                         f"<tr><td><strong>{html.escape(r['model'])}</strong></td><td class='num'>{r['pp'] or '-'}</td>"
                         f"<td class='num'>{r['tg'] or '-'}</td><td class='num'>{r['coding']}</td>"
                         f"<td class='num'>{r['security']}</td><td class='num'>{r['tools']}</td></tr>" for r in sp)
                     + "</tbody></table>")
    notes = data.get("notes", [])
    if notes:
        toc.append((2, "notes", "Notes"))
        parts.append('<h2 id="notes">Notes</h2><ul>' + "".join(f"<li>{inline(n)}</li>" for n in notes) + "</ul>")
    toc.append((2, "run-it-yourself", "Run it yourself"))
    parts.append('<h2 id="run-it-yourself">Run it yourself</h2><p>Run the same tests on your machine:</p>'
                 "<pre><code>litecode tune                 # speed\nlitecode eval                 # all 30 challenges\n"
                 "litecode eval --level hard    # one level\nlitecode eval --kind security # one kind</code></pre>"
                 "<p>Results are saved in <code>&lt;data_dir&gt;/bench/</code>.</p>")
    if not ev and not sp:
        parts.insert(0, "<blockquote><p>Results are being measured. This page updates when the runs finish.</p></blockquote>")
    body = "\n".join(parts)
    return "Benchmarks", body, toc, re.sub(r"<[^>]+>", " ", body)


# ---------------------------------------------------------------- layout
ICONS = {
    "mail": '<path d="M2 5h20v14H2zm2 2v.4l8 5.2 8-5.2V7zm16 2.8-8 5.2-8-5.2V17h16z"/>',
    "gh": '<path d="M12 .5a11.5 11.5 0 0 0-3.6 22.4c.6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.4-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.2c0 .3.2.7.8.6A11.5 11.5 0 0 0 12 .5z"/>',
    "in": '<path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.5h4V21H3zm7 0h3.8v1.6h.1c.5-1 1.8-2 3.8-2 4 0 4.8 2.6 4.8 6V21h-4v-5.2c0-1.2 0-2.8-1.7-2.8s-2 1.3-2 2.7V21h-4z"/>',
    "x": '<path d="M18.2 2.3h3.4l-7.4 8.4 8.7 11.5h-6.8l-5.3-7-6.1 7H1.3l7.9-9L.9 2.3h7l4.8 6.4zm-1.2 17.9h1.9L7 4.2H5z"/>',
}
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230b1420'/%3E%3Crect x='5' y='20' width='6' height='6' rx='1' fill='%234da3ff'/%3E%3Crect x='13' y='14' width='6' height='12' rx='1' fill='%234da3ff'/%3E%3Crect x='21' y='7' width='6' height='19' rx='1' fill='%234da3ff'/%3E%3C/svg%3E")


def header(active=""):
    nav = [("quickstart.html", "Docs", "docs"), ("benchmarks.html", "Benchmarks", "benchmarks"),
           ("faq.html", "FAQ", "faq"), (REPO, "GitHub", "")]
    cur = ' aria-current="page"'
    links = "".join(f'<a href="{u}"{cur if a and a == active else ""}>{t}</a>' for u, t, a in nav)
    return (f'<header class="top"><div class="wrap"><a class="logo" href="./"><span class="mark" aria-hidden="true"><i></i><i></i><i></i></span>litecode</a>'
            f'<nav aria-label="Main">{links}</nav>'
            f'<button class="theme" id="theme" type="button" aria-label="Switch color theme">theme</button></div></header>')


def footer():
    li = lambda href, ic, text: (f'<li><a href="{href}"><svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[ic]}</svg>'
                                 f'{text}</a></li>')
    return ('<footer><div class="wrap foot"><div><div class="credit">Built by <em>Konko Maji</em></div>'
            '<p style="color:var(--ink-2);max-width:32em">litecode is a free, open-source (MIT) AI assistant for coding '
            'and security that runs on your own computer, from a 4 GB laptop to a GPU workstation.</p>'
            '<p class="fine">© 2026 Konko Maji · MIT License</p></div><ul class="links" aria-label="Contact and links">'
            + li("mailto:work.konkomaji@gmail.com", "mail", "work.konkomaji@gmail.com")
            + li(REPO, "gh", "github.com/konkomaji/litecode")
            + li("https://www.linkedin.com/in/konkomaji/", "in", "linkedin.com/in/konkomaji")
            + li("https://x.com/konkomaji", "x", "@konkomaji") + "</ul></div></footer>")


def head(title, desc, slug, jsonld):
    url = BASE + (f"{slug}.html" if slug != "index" else "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc, quote=True)}">
<meta name="author" content="Konko Maji">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="litecode">
<meta property="og:title" content="{html.escape(title, quote=True)}">
<meta property="og:description" content="{html.escape(desc, quote=True)}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<meta name="twitter:site" content="@konkomaji">
<meta name="theme-color" content="#1f6fe5">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="assets/site.css">
<script>try{{var t=localStorage.getItem("lc-theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
<a class="sr" href="#main">Skip to content</a>
"""


def sidebar(cur):
    out, section = [], None
    for slug, _src, t, sec, _d in PAGES:
        if sec != section:
            out.append(f"<h4>{sec}</h4>")
            section = sec
        cur_attr = ' aria-current="page"' if slug == cur else ""
        out.append(f'<a href="{slug}.html"{cur_attr}>{t}</a>')
    return ('<button class="menu-btn" type="button" aria-expanded="false">Menu: all docs pages</button>'
            '<nav class="side" aria-label="Documentation">' + "".join(out) + "</nav>")


def faq_ld(body_html):
    qa = re.findall(r'<h2 id="[^"]+">(.*?)<a class="anchor".*?</h2>\s*(.*?)(?=<h2|\Z)', body_html, re.S)
    ents = [{"@type": "Question", "name": re.sub(r"<[^>]+>", "", q).strip(),
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", a)).strip()}}
            for q, a in qa]
    return {"@type": "FAQPage", "mainEntity": ents}


def build():
    built, full = [], []
    order = [p[0] for p in PAGES]
    for idx, (slug, src, nav_title, section, desc) in enumerate(PAGES):
        if src:
            md = (DOCS / src).read_text(encoding="utf-8")
            title, body, toc, plain = md_to_html(md)
        else:
            title, body, toc, plain = bench_md_html()
        page_title = f"{title} - litecode docs"
        graph = [
            {"@type": "TechArticle", "headline": title, "description": desc, "author": AUTHOR,
             "url": BASE + f"{slug}.html", "isPartOf": {"@type": "WebSite", "name": "litecode", "url": BASE},
             "about": {"@type": "SoftwareApplication", "name": "litecode", "url": BASE}},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "litecode", "item": BASE},
                {"@type": "ListItem", "position": 2, "name": section, "item": BASE + f"{slug}.html"},
                {"@type": "ListItem", "position": 3, "name": title, "item": BASE + f"{slug}.html"}]},
        ]
        if slug == "faq":
            graph.append(faq_ld(body))
        ld = {"@context": "https://schema.org", "@graph": graph}
        toc_html = "".join(f'<a class="l{lv}" href="#{k}">{t}</a>' for lv, k, t in toc)
        prev_ = PAGES[idx - 1] if idx > 0 else None
        next_ = PAGES[idx + 1] if idx + 1 < len(PAGES) else None
        pager = '<div class="pager">'
        if prev_:
            pager += f'<a href="{prev_[0]}.html"><span>Previous</span><b>{prev_[2]}</b></a>'
        if next_:
            pager += f'<a class="next" href="{next_[0]}.html"><span>Next</span><b>{next_[2]}</b></a>'
        pager += "</div>"
        edit = (f'<p class="edit">Source: <a href="{REPO}/blob/main/docs/{src}">docs/{src}</a></p>' if src else "")
        page = (head(page_title, desc, slug, ld) + header("benchmarks" if slug == "benchmarks" else "faq" if slug == "faq" else "docs")
                + f'<div class="wrap docs"><aside>{sidebar(slug)}</aside>'
                + f'<main id="main" class="prose"><div class="crumb">{section}</div><h1>{html.escape(title)}</h1>\n{body}\n{pager}{edit}</main>'
                + (f'<nav class="toc" aria-label="On this page"><div class="label">On this page</div>{toc_html}</nav>' if toc else "<div></div>")
                + "</div>" + footer() + '<script src="assets/site.js" defer></script>\n</body>\n</html>\n')
        (DOCS / f"{slug}.html").write_text(page, encoding="utf-8")
        built.append(slug)
        full.append(f"# {title}\n\nURL: {BASE}{slug}.html\n\n" + (
            (DOCS / src).read_text(encoding="utf-8") if src else plain))
    # sitemap, robots, llms
    urls = [BASE] + [f"{BASE}{s}.html" for s in built]
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")
    llms = ["# litecode", "",
            "> litecode is a free, open-source AI assistant for coding and security that runs locally on your own "
            "computer with open-weight models (llama.cpp). It works offline, adapts to the hardware from a 4 GB "
            "laptop without GPU to a GPU workstation, and also helps with writing, study and data tasks. "
            "Built by Konko Maji.", "",
            "Key facts:",
            "- Category: local AI coding agent / offline AI coding assistant (terminal).",
            "- Main focus: coding and security review. Also: writing, study questions, CSV/JSON/log data.",
            "- Runs on CPU only; uses NVIDIA (CUDA), Vulkan or Apple Metal GPUs when present.",
            "- Measured on a Ryzen 3 3200G, 16 GB RAM, no GPU: MiniCPM5-2B generates 15.2 tokens/s and passed 8/8 single-function coding tasks.",
            "- Features: tool-using agent, automatic memory and learning, SKILL.md skills, MCP client, static security scan plus model verdicts, test-fix loop, editor autocomplete.",
            "- License: MIT. Python 3.10+, no Python dependencies.",
            f"- Source: {REPO}",
            "- Contact: Konko Maji, work.konkomaji@gmail.com, https://www.linkedin.com/in/konkomaji/, https://x.com/konkomaji",
            "", "## Docs", ""]
    llms += [f"- [{t}]({BASE}{s}.html): {d}" for s, _src, t, _sec, d in PAGES]
    (DOCS / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")
    (DOCS / "llms-full.txt").write_text("\n\n---\n\n".join(full) + "\n", encoding="utf-8")
    print(f"built {len(built)} pages + sitemap.xml, robots.txt, llms.txt, llms-full.txt")
    return built


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
