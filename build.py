#!/usr/bin/env python3
"""
Build /workspace/data/templates-overview/index.html — a static catalog
of all Blueberry creative templates (image templates from
puppeteer-asset-render, motion chassis from meta-ad-video).

Reads:
  - Each image template's config.json (description, layouts, defaults)
  - Symlinked example PNGs under assets/image-templates/<name>/
  - Symlinked rendered MP4s under assets/video-chassis/<name>/

Writes:
  - index.html
"""

import json
import os
import html
from datetime import date
from pathlib import Path

ROOT = Path("/workspace/data/templates-overview/public")
IMG_TPL_SRC = Path("/workspace/.claude/skills/puppeteer-asset-render/templates")
VIDEO_SRC = Path("/workspace/data/meta-ad-video")

# ─── Video chassis descriptions (from skill description) ────────────────
# Hardcoded because chassis live in compositions/ but the canonical
# rhetorical purpose is documented in the meta-ad-video skill description.
CHASSIS_META = {
    "cold-open": {
        "title": "Cold Open",
        "use_when": "Hook + evidence-stagger + end-card. Best for shock-claim ads where the first second has to stop the scroll.",
        "structure": "shock-claim → evidence stagger → end-card",
        "kind": "main",
    },
    "stat-counter": {
        "title": "Stat Counter",
        "use_when": "Single hero stat carries the whole ad. Numeric punch (cost, time, percentage) is the message.",
        "structure": "single hero stat with overshoot-punch animation",
        "kind": "main",
    },
    "us-vs-them": {
        "title": "Us vs Them",
        "use_when": "Side-by-side contrast against a competitor or alternative (urgent care, ER, generic telehealth).",
        "structure": "split-screen contrast — color variant or photo variant",
        "kind": "main",
    },
    "us-vs-them-scene": {
        "title": "Us vs Them — Scene Variant",
        "use_when": "Photo / scene variant of us-vs-them with real-world imagery instead of color blocks.",
        "structure": "photo split-screen contrast",
        "kind": "scene",
    },
    "quote-stagger": {
        "title": "Quote Stagger",
        "use_when": "Parent-voice testimonial. Letter-by-letter stagger reveals the quote at a readable cadence.",
        "structure": "parent-quote letter-stagger reveal at 14 CPS",
        "kind": "main",
    },
    "before-after-scenario": {
        "title": "Before / After Scenario",
        "use_when": "Life-context contrast — show the parent's situation before Blueberry and after. NEVER body-state (no sick→healthy child shots).",
        "structure": "life-context wipe (kitchen / car / bedroom scene change)",
        "kind": "main",
    },
    "before-after-scenario-scene": {
        "title": "Before / After — Scene Variant",
        "use_when": "Scene variant with photographic life-context shots rather than illustrated environments.",
        "structure": "photo life-context wipe",
        "kind": "scene",
    },
    "if-then-rules": {
        "title": "If / Then Rules",
        "use_when": "Parent-voice listicle. Rules of thumb formatted as if-then statements (eyebrow + 4 rules cascade).",
        "structure": "eyebrow + 4 rules slide-in cascade",
        "kind": "main",
    },
    "letter-treatment": {
        "title": "Letter Treatment",
        "use_when": "Intimate clinician or founder letter. High-trust register; pairs with named real-person sign-off (e.g. Dr. Garbi).",
        "structure": "typed salutation + 5-line body fade-up + key-sentence scale-up + named sign-off",
        "kind": "main",
    },
    "letter-treatment-scene": {
        "title": "Letter Treatment — Scene Variant",
        "use_when": "Visual sibling of letter-treatment: paper-on-brand-color or handwriting-on-photo treatment.",
        "structure": "letter on photographic background or paper texture",
        "kind": "scene",
    },
}

# ─── Helpers ─────────────────────────────────────────────────────────────


def find_canonical_thumbnail(template_name: str, default_layout: str | None) -> str | None:
    """Return relative path to the canonical 1:1 PNG for a template."""
    examples_dir = ROOT / "assets" / "image-templates" / template_name
    if not examples_dir.exists():
        return None
    # Try defaults.layout first
    if default_layout:
        candidate = examples_dir / f"{default_layout}__square_1_1.png"
        if candidate.exists():
            return f"assets/image-templates/{template_name}/{default_layout}__square_1_1.png"
    # Fallback: any *__square_1_1.png
    for f in sorted(examples_dir.iterdir()):
        if f.name.endswith("__square_1_1.png"):
            return f"assets/image-templates/{template_name}/{f.name}"
    return None


def list_all_variant_renders(template_name: str) -> list[dict]:
    """Return list of {layout, variant, path} for every PNG under the
    template's examples dir."""
    examples_dir = ROOT / "assets" / "image-templates" / template_name
    out = []
    if not examples_dir.exists():
        return out
    for f in sorted(examples_dir.iterdir()):
        if not f.name.endswith(".png"):
            continue
        # filename: <layout>__<variant>.png
        stem = f.name[:-4]  # strip .png
        if "__" not in stem:
            continue
        layout, variant = stem.rsplit("__", 1)
        out.append({
            "layout": layout,
            "variant": variant,
            "path": f"assets/image-templates/{template_name}/{f.name}",
        })
    return out


def first_sentence(text: str, max_chars: int = 200) -> str:
    """Extract a leading one-sentence summary."""
    text = text.strip()
    for sep in (". ", "! ", "? "):
        if sep in text:
            cut = text.index(sep) + 1
            if cut <= max_chars:
                return text[:cut].strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def load_image_templates() -> list[dict]:
    """Load all image-template configs in alpha order."""
    out = []
    for d in sorted(IMG_TPL_SRC.iterdir()):
        if not d.is_dir() or d.name == "_partials":
            continue
        cfg_path = d / "config.json"
        if not cfg_path.exists():
            continue
        cfg = json.loads(cfg_path.read_text())
        name = d.name
        default_layout = cfg.get("defaults", {}).get("layout")
        out.append({
            "name": name,
            "description": cfg.get("description", ""),
            "summary": first_sentence(cfg.get("description", "")),
            "layouts": list(cfg.get("layouts", {}).keys()),
            "default_layout": default_layout,
            "variants": list(cfg.get("variants", {}).keys()),
            "thumbnail": find_canonical_thumbnail(name, default_layout),
            "all_renders": list_all_variant_renders(name),
        })
    return out


def load_video_chassis() -> list[dict]:
    """Load all video chassis with their rendered MP4s."""
    out = []
    for name in sorted(CHASSIS_META.keys()):
        meta = CHASSIS_META[name]
        chassis_dir = ROOT / "assets" / "video-chassis" / name
        renders = {}
        for aspect in ("1x1", "4x5", "9x16"):
            mp4 = chassis_dir / f"{aspect}.mp4"
            if mp4.exists():
                renders[aspect] = f"assets/video-chassis/{name}/{aspect}.mp4"
        out.append({
            "name": name,
            "title": meta["title"],
            "use_when": meta["use_when"],
            "structure": meta["structure"],
            "kind": meta["kind"],
            "renders": renders,
        })
    return out


# ─── HTML rendering ──────────────────────────────────────────────────────


def render_chassis_card(c: dict) -> str:
    primary = c["renders"].get("1x1") or next(iter(c["renders"].values()), None)
    other_aspects = [(a, p) for a, p in c["renders"].items() if a != "1x1"]
    if not primary:
        video_html = '<div class="missing">no render found</div>'
    else:
        video_html = (
            f'<video class="chassis-video" autoplay muted loop playsinline '
            f'preload="metadata" src="{primary}"></video>'
        )
    other_links = " · ".join(
        f'<a href="{p}" target="_blank">{a}</a>' for a, p in other_aspects
    )
    kind_badge = (
        '<span class="badge badge-scene">scene variant</span>'
        if c["kind"] == "scene"
        else '<span class="badge badge-main">main chassis</span>'
    )
    return f"""
    <div class="card chassis-card" id="chassis-{html.escape(c["name"])}">
      <div class="card-media">{video_html}</div>
      <div class="card-body">
        <div class="card-head">
          <h3>{html.escape(c["title"])}</h3>
          {kind_badge}
        </div>
        <p class="use-when"><strong>Use when:</strong> {html.escape(c["use_when"])}</p>
        <p class="structure"><strong>Structure:</strong> {html.escape(c["structure"])}</p>
        <p class="aspects"><strong>Other aspects:</strong> {other_links or '—'}</p>
        <p class="meta">Slug: <code>{html.escape(c["name"])}</code></p>
      </div>
    </div>
    """


def render_template_card(t: dict) -> str:
    name = t["name"]
    if t["thumbnail"]:
        thumb = (
            f'<img class="tpl-thumb" src="{t["thumbnail"]}" '
            f'loading="lazy" alt="{html.escape(name)} canonical render" />'
        )
    else:
        thumb = '<div class="missing">no example render</div>'

    layouts_pills = "".join(
        f'<span class="pill{(" pill-default" if l == t["default_layout"] else "")}">{html.escape(l)}</span>'
        for l in t["layouts"]
    )
    n_renders = len(t["all_renders"])
    expand_id = f"expand-{name}"
    # Build hidden expansion grid (all layouts × all variants)
    grid_items = "".join(
        f'<figure class="render-cell"><img src="{r["path"]}" loading="lazy" alt=""/>'
        f'<figcaption>{html.escape(r["layout"])} · {html.escape(r["variant"])}</figcaption></figure>'
        for r in t["all_renders"]
    )
    return f"""
    <div class="card tpl-card" id="tpl-{html.escape(name)}">
      <div class="card-media">{thumb}</div>
      <div class="card-body">
        <div class="card-head">
          <h3>{html.escape(name)}</h3>
          <span class="badge badge-img">{len(t["layouts"])} layout{"s" if len(t["layouts"]) != 1 else ""}</span>
        </div>
        <p class="summary">{html.escape(t["summary"])}</p>
        <p class="layouts-line"><strong>Layouts:</strong> {layouts_pills}</p>
        <p class="meta">
          Default variant: <code>{html.escape(t["variants"][0] if t["variants"] else "—")}</code> ·
          {n_renders} render{"s" if n_renders != 1 else ""}
        </p>
        <details>
          <summary>Show all {n_renders} renders</summary>
          <div class="render-grid">{grid_items}</div>
        </details>
        <details class="desc-details">
          <summary>Full description</summary>
          <p class="desc">{html.escape(t["description"])}</p>
        </details>
      </div>
    </div>
    """


def render_html(chassis: list[dict], templates: list[dict]) -> str:
    today = date.today().isoformat()
    n_chassis_main = sum(1 for c in chassis if c["kind"] == "main")
    n_chassis_scene = sum(1 for c in chassis if c["kind"] == "scene")
    chassis_cards = "\n".join(render_chassis_card(c) for c in chassis)
    tpl_cards = "\n".join(render_template_card(t) for t in templates)

    chassis_toc = "".join(
        f'<a href="#chassis-{c["name"]}" class="toc-link">{html.escape(c["title"])}</a>'
        for c in chassis
    )
    tpl_toc = "".join(
        f'<a href="#tpl-{t["name"]}" class="toc-link">{html.escape(t["name"])}</a>'
        for t in templates
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Blueberry Creative Templates Overview</title>
<style>
  :root {{
    --bg: #0e1116;
    --surface: #161a22;
    --surface-2: #1e2330;
    --border: #2a3140;
    --ink: #e6e9ef;
    --ink-dim: #9aa3b2;
    --accent: #5b8def;
    --accent-2: #7c5cff;
    --warm: #f4a261;
    --good: #4ade80;
    --max: 1280px;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--ink); }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.55;
  }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{
    background: var(--surface-2);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.85em;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }}

  header.page-head {{
    background: linear-gradient(135deg, #14305c 0%, #2a1c5b 100%);
    padding: 56px 32px 48px;
    border-bottom: 1px solid var(--border);
  }}
  .page-head .inner {{ max-width: var(--max); margin: 0 auto; }}
  .page-head h1 {{
    margin: 0 0 12px; font-size: 36px; font-weight: 700; letter-spacing: -0.5px;
  }}
  .page-head .subtitle {{ color: #c4cad6; font-size: 16px; max-width: 720px; }}
  .page-head .stats {{
    margin-top: 24px; display: flex; gap: 24px; flex-wrap: wrap;
    color: #c4cad6; font-size: 14px;
  }}
  .page-head .stats span strong {{ color: #fff; font-size: 20px; display: block; }}
  .page-head .meta-line {{
    margin-top: 16px; color: #8590a3; font-size: 13px; font-family: ui-monospace, monospace;
  }}

  nav.section-nav {{
    position: sticky; top: 0; z-index: 10;
    background: rgba(14, 17, 22, 0.92);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
    padding: 10px 32px;
  }}
  nav.section-nav .inner {{
    max-width: var(--max); margin: 0 auto;
    display: flex; gap: 16px; align-items: center; flex-wrap: wrap;
  }}
  nav.section-nav a {{
    color: var(--ink-dim); font-size: 13px; padding: 4px 10px; border-radius: 4px;
  }}
  nav.section-nav a:hover {{ color: var(--ink); background: var(--surface); text-decoration: none; }}
  nav.section-nav .label {{ color: var(--ink-dim); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}

  main {{ max-width: var(--max); margin: 0 auto; padding: 32px; }}

  section.template-section {{ margin: 56px 0 80px; }}
  section.template-section > h2 {{
    margin: 0 0 8px; font-size: 28px; font-weight: 700;
    border-left: 4px solid var(--accent); padding-left: 16px;
  }}
  section.template-section > .section-blurb {{
    color: var(--ink-dim); margin: 0 0 32px 20px; max-width: 720px;
  }}

  details.toc-block {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    margin: 0 0 32px 20px;
  }}
  details.toc-block summary {{
    cursor: pointer; color: var(--ink-dim); font-size: 13px;
  }}
  details.toc-block .toc-link {{
    display: inline-block; margin: 4px 8px 4px 0;
    color: var(--accent); font-size: 13px;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 20px;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    display: flex; flex-direction: column;
    transition: border-color 0.15s, transform 0.15s;
  }}
  .card:hover {{ border-color: var(--accent); }}
  .card-media {{
    background: #000;
    aspect-ratio: 1 / 1;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
  }}
  .card-media .missing {{ color: #555; font-size: 13px; padding: 24px; text-align: center; }}
  .chassis-video, .tpl-thumb {{
    width: 100%; height: 100%; object-fit: contain; display: block;
    background: #000;
  }}
  .card-body {{ padding: 16px 18px; flex: 1; display: flex; flex-direction: column; gap: 10px; }}
  .card-head {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .card-head h3 {{
    margin: 0; font-size: 17px; font-weight: 600;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    color: #fff;
  }}
  .badge {{
    font-size: 10px; padding: 2px 8px; border-radius: 999px; text-transform: uppercase;
    letter-spacing: 0.5px; font-weight: 600;
  }}
  .badge-main {{ background: rgba(91, 141, 239, 0.15); color: var(--accent); }}
  .badge-scene {{ background: rgba(244, 162, 97, 0.15); color: var(--warm); }}
  .badge-img {{ background: rgba(124, 92, 255, 0.15); color: var(--accent-2); }}

  .use-when, .structure, .summary, .layouts-line, .aspects, .meta {{
    margin: 0; font-size: 13px;
  }}
  .summary {{ color: var(--ink); }}
  .meta {{ color: var(--ink-dim); font-size: 12px; }}
  .use-when strong, .structure strong, .layouts-line strong, .aspects strong {{
    color: var(--ink-dim); font-weight: 500;
  }}

  .pill {{
    display: inline-block; margin: 2px 4px 2px 0;
    background: var(--surface-2); color: var(--ink-dim);
    padding: 1px 8px; border-radius: 4px;
    font-size: 11px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  .pill-default {{ background: rgba(74, 222, 128, 0.12); color: var(--good); }}

  details {{ margin-top: 4px; }}
  details summary {{
    cursor: pointer; font-size: 12px; color: var(--ink-dim);
    padding: 4px 0;
  }}
  details summary:hover {{ color: var(--accent); }}
  details[open] summary {{ color: var(--ink); }}
  .render-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
    margin-top: 12px;
  }}
  .render-cell {{ margin: 0; }}
  .render-cell img {{
    width: 100%; height: auto; display: block; border-radius: 4px;
    background: #000;
    border: 1px solid var(--border);
  }}
  .render-cell figcaption {{
    font-size: 10px; color: var(--ink-dim);
    padding: 4px 0 0; font-family: ui-monospace, monospace;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .desc {{
    font-size: 13px; color: var(--ink-dim);
    background: var(--surface-2); padding: 12px; border-radius: 6px;
    margin: 8px 0 0;
  }}
  footer {{
    max-width: var(--max); margin: 32px auto 64px; padding: 0 32px;
    color: var(--ink-dim); font-size: 12px; text-align: center;
  }}
</style>
</head>
<body>

<header class="page-head">
  <div class="inner">
    <h1>Blueberry Creative Templates Overview</h1>
    <p class="subtitle">
      The full creative template catalog — motion-native video chassis (rendered via HeyGen
      HyperFrames) and static image templates (rendered via puppeteer-asset-render).
      Stakeholder reference + brief-author cookbook in one page.
    </p>
    <div class="stats">
      <span><strong>{n_chassis_main}</strong>main video chassis</span>
      <span><strong>{n_chassis_scene}</strong>scene variants</span>
      <span><strong>{len(templates)}</strong>image templates</span>
      <span><strong>{sum(len(t["layouts"]) for t in templates)}</strong>image layouts</span>
      <span><strong>{sum(len(t["all_renders"]) for t in templates)}</strong>example renders</span>
    </div>
    <p class="meta-line">Generated {today} · agent: Ember · source: /workspace/.claude/skills/{{meta-ad-video, puppeteer-asset-render}}</p>
  </div>
</header>

<nav class="section-nav">
  <div class="inner">
    <span class="label">Jump:</span>
    <a href="#video-chassis">Video chassis</a>
    <a href="#image-templates">Image templates</a>
  </div>
</nav>

<main>

<section class="template-section" id="video-chassis">
  <h2>Video chassis</h2>
  <p class="section-blurb">
    Motion-native ad chassis at 9:16, 1:1, and 4:5. Each chassis ships HTML + GSAP
    compositions with parameter slots for copy and brand assets. Renders below
    auto-play muted; click an aspect link to open the full-resolution MP4.
  </p>
  <details class="toc-block">
    <summary>Quick jump · {len(chassis)} chassis</summary>
    <div>{chassis_toc}</div>
  </details>
  <div class="grid">
    {chassis_cards}
  </div>
</section>

<section class="template-section" id="image-templates">
  <h2>Image templates</h2>
  <p class="section-blurb">
    Static creative templates rendered via headless Chromium. Each template has 1+
    layouts × 3 aspect ratios (1:1, 4:5, 9:16). The thumbnail shows the canonical
    default layout at 1:1 — expand "Show all renders" for the full layout × aspect grid.
    The matcher in <code>email-screenshot-to-template</code> uses these renders for
    competitor-ad triage.
  </p>
  <details class="toc-block">
    <summary>Quick jump · {len(templates)} templates</summary>
    <div>{tpl_toc}</div>
  </details>
  <div class="grid">
    {tpl_cards}
  </div>
</section>

</main>

<footer>
  Blueberry Creative Templates Overview · generated by Ember (fb-ad-agent)<br/>
  Source of truth: per-template <code>config.json</code> files in
  <code>puppeteer-asset-render/templates/</code> and chassis compositions in
  <code>meta-ad-video/compositions/</code>.<br/>
  Hosted on Cloudflare. Source repo:
  <a href="https://github.com/harrisonmgordon/creative-templates">harrisonmgordon/creative-templates</a>
  — auto-deploys on push to <code>main</code>.
</footer>

</body>
</html>
"""


def main():
    chassis = load_video_chassis()
    templates = load_image_templates()
    html_doc = render_html(chassis, templates)
    out_path = ROOT / "index.html"
    out_path.write_text(html_doc)
    print(f"Wrote {out_path} ({len(html_doc):,} bytes)")
    print(f"  Video chassis:    {len(chassis)}")
    print(f"  Image templates:  {len(templates)}")
    print(f"  Total renders:    {sum(len(t['all_renders']) for t in templates)}")


if __name__ == "__main__":
    main()
