"""Wiki builder — generates static HTML wiki + Obsidian vault from knowledge base."""
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import markdown as md

from config import CATEGORIES, CATEGORY_LABELS, WIKI_HTML_DIR, WIKI_OBSIDIAN_DIR
from tools.ontology import ENTITY_TYPES

_HTML_BASE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Agenturgeschichte</title>
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<nav class="sidebar">
  <a class="logo" href="{root}index.html">Agentur<span>Geschichte</span></a>
  <a href="{root}graph.html" class="graph-nav-link">⬡ Wissensgraph</a>
  <div class="nav-section">Kategorien</div>
  {nav_links}
</nav>
<main>
  <header class="page-header{header_class}">
    <div class="breadcrumb">{breadcrumb}</div>
    <h1>{title}</h1>
    {meta_badges}
  </header>
  <article class="content{content_class}">
    {body}
  </article>
  {related_panel}
</main>
<script src="{root}assets/search.js"></script>
</body>
</html>"""

_CSS = """
:root {
  --bg:    #0f0f0f;
  --bg2:   #181818;
  --bg3:   #212121;
  --bg4:   #1c1c1c;
  --accent:  #c8a96e;
  --accent2: #e8c99e;
  --accent3: #9a7a48;
  --text:  #e8e4dc;
  --text2: #a09890;
  --text3: #706860;
  --border:  #2e2e2e;
  --border2: #252525;
  --link:    #c8a96e;
  --sidebar-w: 256px;
  --font-serif: 'Georgia', 'Times New Roman', serif;
  --font-sans: -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', 'Consolas', 'Courier New', monospace;

  --c-agency:     #c8a96e;
  --c-person:     #7eb8d4;
  --c-era:        #9b7ec8;
  --c-work:       #7ec87e;
  --c-concept:    #c87e7e;
  --c-scandal:    #d44444;
  --c-life:       #d4a44c;
  --c-technology: #7ec8c8;
  --c-visual:     #a0a0a0;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
a { text-decoration: none; color: inherit; }
html {
  font-size: 15px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  line-height: 1.7;
  display: flex;
  min-height: 100vh;
}

/* ─── Sidebar ─── */
.sidebar {
  width: var(--sidebar-w);
  min-height: 100vh;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  position: fixed;
  top: 0; left: 0;
  overflow-y: auto;
  flex-shrink: 0;
  z-index: 100;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.sidebar .logo {
  display: block;
  padding: 22px 20px 18px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text2);
  text-decoration: none;
  border-bottom: 1px solid var(--border);
  transition: color 0.15s;
}
.sidebar .logo span { color: var(--accent); }
.sidebar .logo:hover { color: var(--text2); }
.sidebar .graph-nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #9b7ec8;
  text-decoration: none;
  border-bottom: 1px solid var(--border);
  transition: color 0.18s, background 0.18s;
}
.sidebar .graph-nav-link:hover { color: #c4a8f0; background: rgba(155,126,200,0.07); }
.sidebar .nav-section {
  padding: 16px 20px 5px;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text2);
  font-weight: 600;
}
.sidebar a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 20px;
  min-height: 40px;
  color: var(--text2);
  text-decoration: none;
  font-size: 13px;
  transition: color 0.15s, background 0.12s, border-color 0.15s;
  border-left: 2px solid transparent;
}
.sidebar a:hover {
  color: var(--text);
  background: rgba(255,255,255,0.025);
  border-left-color: rgba(200,169,110,0.2);
}
.sidebar a.active {
  color: var(--accent);
  background: rgba(200,169,110,0.05);
  border-left: 2px solid var(--accent);
  font-weight: 500;
}
.sidebar a .cat-count {
  font-size: 11px;
  color: var(--text2);
  background: rgba(255,255,255,0.04);
  padding: 1px 7px;
  border-radius: 10px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.sidebar a:hover .cat-count { color: var(--text2); }

/* ─── Main ─── */
main {
  margin-left: var(--sidebar-w);
  flex: 1;
  padding: 52px 60px 88px;
  max-width: 1100px;
  min-width: 0;
}

/* ─── Page header ─── */
.page-header {
  margin-bottom: 48px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 32px;
}
.breadcrumb {
  font-size: 11px;
  color: var(--text3);
  margin-bottom: 14px;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 7px;
}
.breadcrumb a { color: var(--text3); text-decoration: none; transition: color 0.15s; }
.breadcrumb a:hover { color: var(--accent); }
h1, h2, h3, h4 { text-wrap: balance; }
h1 {
  font-family: var(--font-serif);
  font-size: 2.55rem;
  font-weight: normal;
  line-height: 1.14;
  color: var(--text);
  letter-spacing: -0.02em;
  max-width: 760px;
}
/* Category/index pages use a lighter header */
.page-header.is-index h1 {
  font-family: var(--font-sans);
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text2);
}
.page-header.is-index {
  margin-bottom: 32px;
  padding-bottom: 20px;
}

/* ─── Meta badges ─── */
.meta-badges {
  display: flex; flex-wrap: wrap; gap: 7px;
  margin-top: 18px; align-items: center;
}
.badge {
  padding: 3px 10px; border-radius: 3px;
  font-size: 11px; letter-spacing: 0.06em;
  font-weight: 600; text-transform: uppercase;
  line-height: 1.6; font-family: var(--font-sans);
}
.badge-era { background: rgba(200,169,110,0.08); color: var(--accent); border: 1px solid rgba(200,169,110,0.28); }
.badge-tag { background: rgba(255,255,255,0.04); color: var(--text2); border: 1px solid var(--border); }
.badge-confidence-high { background: rgba(100,168,100,0.08); color: #7ab87a; border: 1px solid rgba(100,168,100,0.24); }
.badge-confidence-medium { background: rgba(160,160,80,0.08); color: #b0a870; border: 1px solid rgba(160,160,80,0.24); }
.badge-verified  { background: rgba(80,180,130,0.09); color: #60d0a0; border: 1px solid rgba(80,180,130,0.28); }
.badge-corrected { background: rgba(210,90,70,0.09);  color: #e09080; border: 1px solid rgba(210,90,70,0.28); }
.badge-uncertain { background: rgba(200,160,60,0.09); color: #c8a050; border: 1px solid rgba(200,160,60,0.28); }

/* Inline [ungesichert] markers in article text */
.content .ungesichert {
  color: var(--text3);
  font-size: 0.78em;
  font-family: var(--font-sans);
  font-style: normal;
  background: rgba(200,160,60,0.08);
  border: 1px solid rgba(200,160,60,0.2);
  border-radius: 2px;
  padding: 1px 5px;
  margin-left: 3px;
  letter-spacing: 0.04em;
  vertical-align: middle;
  white-space: nowrap;
}

/* ─── Content ─── */
.content {
  font-family: var(--font-serif);
  font-size: 16.5px;
  line-height: 1.88;
  color: var(--text);
  max-width: 680px;
}
.content h2 {
  font-family: var(--font-sans);
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent); margin: 3em 0 1em;
  padding-bottom: 9px; border-bottom: 1px solid var(--border);
}
.content h3 {
  font-family: var(--font-sans);
  font-size: 1rem; color: var(--text);
  margin: 2.5em 0 0.7em; font-weight: 600;
}
.content h4 {
  font-family: var(--font-sans);
  font-size: 0.75rem; color: var(--text2);
  margin: 2em 0 0.5em; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
}
.content p { margin-bottom: 1.3em; text-wrap: pretty; }
.content li { margin-bottom: 0.42em; text-wrap: pretty; }
.content a {
  color: var(--link);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  transition: color 0.15s;
}
.content a:hover { color: var(--accent2); }
/* Cards and list rows inside .content — suppress underline rule */
.content a.entry-card, .content a.entry-card:hover,
.content a.entry-row,  .content a.entry-row:hover  { text-decoration: none; color: inherit; }
.content ul, .content ol { padding-left: 1.5em; margin-bottom: 1.3em; }
.content li::marker { color: var(--accent3); }
.content strong { color: var(--accent2); font-weight: 600; }
.content em { color: var(--text); font-style: italic; }
.content blockquote {
  border-left: 3px solid var(--accent3);
  padding: 14px 24px; margin: 2.2em 0;
  background: rgba(200,169,110,0.035);
  color: var(--text2); font-style: italic;
  font-size: 1.05em; line-height: 1.72;
}
.content blockquote p { margin-bottom: 0; }
.content code {
  background: var(--bg3); padding: 2px 7px;
  border-radius: 3px; font-family: var(--font-mono);
  font-size: 0.82em; color: var(--accent2);
  border: 1px solid var(--border);
}
.content hr { border: none; border-top: 1px solid var(--border); margin: 2.5em 0; }

/* ─── Footnote citations ─── */
.fn-ref {
  font-size: 0.7em;
  line-height: 0;
  vertical-align: super;
}
.fn-ref a {
  color: var(--accent3);
  text-decoration: none;
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
  padding: 0 1px;
  transition: color 0.15s;
}
.fn-ref a:hover { color: var(--accent); }

.footnote-list {
  list-style: none;
  padding: 0;
  margin: 0;
  counter-reset: footnote-counter;
}
.footnote-list li {
  font-family: var(--font-sans);
  font-size: 12.5px;
  color: var(--text2);
  line-height: 1.6;
  padding: 6px 0 6px 2em;
  border-bottom: 1px solid var(--border2);
  position: relative;
  counter-increment: footnote-counter;
}
.footnote-list li::before {
  content: counter(footnote-counter) ".";
  position: absolute;
  left: 0;
  color: var(--text3);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  min-width: 1.5em;
}
.footnote-list li:last-child { border-bottom: none; }
.footnote-list li a {
  color: var(--link);
  font-size: 11.5px;
  word-break: break-all;
}

/* ─── Sources section ─── */
.sources-panel {
  margin-top: 36px; padding: 18px 20px;
  background: var(--bg2); border-radius: 4px;
  border: 1px solid var(--border);
  max-width: 680px;
}
.sources-panel h4 {
  font-family: var(--font-sans); font-size: 11px;
  font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--text2);
  margin-bottom: 10px;
}
.sources-panel ul { list-style: none; padding: 0; margin: 0; }
.sources-panel li {
  font-family: var(--font-sans); font-size: 12px;
  color: var(--text2); line-height: 1.5;
  padding: 4px 0; border-bottom: 1px solid var(--border2);
}
.sources-panel li:last-child { border-bottom: none; }
.sources-panel li::before { content: '↳ '; color: var(--text3); }

/* ─── Image gallery ─── */
.img-gallery {
  display: flex; flex-wrap: wrap; gap: 12px;
  margin: 0 0 28px 0;
}
.img-gallery figure {
  margin: 0; flex: 0 0 auto; max-width: 220px;
  background: var(--bg2); border-radius: 4px;
  border: 1px solid var(--border);
  overflow: hidden;
}
.img-gallery figure img {
  display: block; width: 100%; height: 140px;
  object-fit: cover;
  outline: 1px solid rgba(0,0,0,0.1);
}
.img-gallery figcaption {
  padding: 7px 9px;
  font-family: var(--font-sans); font-size: 10.5px;
  color: var(--text2); line-height: 1.4;
}
.img-gallery figcaption .img-caption { display: block; margin-bottom: 3px; color: var(--text); }
.img-gallery figcaption .img-credit { display: block; color: var(--text3); font-size: 10px; }
.img-gallery figcaption .img-copyright-unknown {
  display: inline-block; margin-top: 2px;
  color: #c8a050; font-size: 9.5px; font-weight: 600;
  background: rgba(200,160,60,0.08); padding: 1px 5px; border-radius: 3px;
}

/* ─── Related / relation panel ─── */
.related-panel {
  margin-top: 60px; padding-top: 32px;
  border-top: 1px solid var(--border);
  max-width: 860px;
}
.related-panel h3 {
  font-family: var(--font-sans);
  font-size: 11px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--text2);
  margin-bottom: 18px; font-weight: 600;
}
.related-cards { display: flex; flex-wrap: wrap; gap: 8px; }
.related-card {
  background: var(--bg2);
  border: none;
  border-radius: 5px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08);
  padding: 12px 16px 12px 16px;
  font-size: 13px; text-decoration: none; color: var(--text);
  transition-property: box-shadow, transform, scale;
  transition-duration: 0.18s;
  transition-timing-function: ease;
  max-width: 240px; min-width: 150px;
  position: relative; overflow: hidden;
}
.related-card::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0; width: 3px;
  background: var(--card-accent, var(--accent3));
}
.related-card:hover {
  box-shadow: 0 0 0 1px rgba(255,255,255,0.13), 0 4px 16px rgba(0,0,0,0.45);
  transform: translateY(-2px);
}
.related-card:active { scale: 0.96; transform: translateY(0); }
.related-card small {
  display: block; font-size: 11px;
  margin-bottom: 5px; letter-spacing: 0.07em;
  text-transform: uppercase; font-family: var(--font-sans);
  font-weight: 600; color: var(--card-accent, var(--text2));
}
.related-card strong {
  display: block; font-size: 12.5px;
  font-weight: 500; line-height: 1.35; color: var(--text);
}

/* ─── Index hero ─── */
.index-hero {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}
.index-hero p {
  font-family: var(--font-serif);
  font-size: 1.08rem; color: var(--text2);
  line-height: 1.8; max-width: 560px; margin-top: 16px;
}
.index-stats {
  display: flex; gap: 32px; margin-top: 24px; flex-wrap: wrap;
}
.stat-item {
  font-family: var(--font-sans); font-size: 11px;
  color: var(--text2); letter-spacing: 0.07em; text-transform: uppercase;
}
.stat-item strong {
  display: block; font-size: 2.2rem; font-weight: 700;
  color: var(--accent); letter-spacing: -0.04em; line-height: 1;
  margin-bottom: 4px; font-family: var(--font-serif);
  font-variant-numeric: tabular-nums;
}

/* Index/category pages: full-width content, no text-column limit */
.content-wide { max-width: none; }

/* ─── Category sections ─── */
.category-section { margin-bottom: 60px; }
.category-section h2 {
  font-family: var(--font-sans);
  font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text2); margin-bottom: 20px;
  padding-bottom: 10px; border-bottom: 1px solid var(--border);
  font-weight: 600; display: flex; align-items: baseline;
  justify-content: space-between;
}
.category-section h2 strong { color: var(--text); font-weight: 600; letter-spacing: inherit; }
.category-section h2 a {
  font-size: 1em; font-weight: 500;
  color: var(--text2); letter-spacing: 0.06em; text-decoration: none;
}
.category-section h2 a:hover { color: var(--accent); }

.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
@media (min-width: 900px) {
  .entry-grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
}

/* ─── Entry Card ─── */
.entry-card {
  background: var(--bg2);
  border: none;
  border-radius: 4px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08);
  padding: 0;
  text-decoration: none; color: var(--text);
  transition-property: transform, box-shadow, background, scale;
  transition-duration: 0.18s;
  transition-timing-function: ease;
  display: flex; flex-direction: column;
  position: relative; overflow: hidden;
  min-height: 130px;
}
/* Top accent bar */
.entry-card::before {
  content: '';
  display: block; height: 3px;
  background: var(--card-accent, var(--border));
  flex-shrink: 0;
  transition: opacity 0.2s;
}
.entry-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.13), 0 8px 24px rgba(0,0,0,0.45);
  background: var(--bg3);
}
.entry-card:active {
  scale: 0.96;
  transform: translateY(0);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.1), 0 2px 8px rgba(0,0,0,0.3);
}
/* Card body */
.card-body {
  padding: 14px 16px 16px;
  display: flex; flex-direction: column; flex: 1;
}
.card-type {
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase;
  font-family: var(--font-sans);
  color: var(--card-accent, var(--text2));
  margin-bottom: 6px;
  display: block;
}
.entry-card h3 {
  font-family: var(--font-serif);
  font-size: 0.97rem; font-weight: normal;
  margin-bottom: 9px; line-height: 1.4;
  color: var(--text); transition: color 0.15s;
}
.entry-card:hover h3 { color: var(--accent2); }
.entry-card .era {
  font-size: 11px; color: var(--accent3);
  margin-bottom: 6px; font-family: var(--font-sans);
  letter-spacing: 0.04em; font-weight: 600; text-transform: uppercase;
}
.entry-card .excerpt {
  font-size: 12px; color: var(--text2);
  line-height: 1.52; font-family: var(--font-sans);
  display: -webkit-box;
  -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  flex: 1; text-wrap: pretty;
}
.entry-card .tags {
  margin-top: 11px; display: flex; flex-wrap: wrap; gap: 4px;
}
.entry-card .tag {
  font-size: 11px;
  background: rgba(255,255,255,0.04);
  color: var(--text2); padding: 2px 7px;
  border-radius: 2px; font-family: var(--font-sans);
  letter-spacing: 0.02em;
}

/* ─── Search ─── */
.search-bar { margin-bottom: 36px; position: relative; display: block; }
.search-bar::before {
  content: '⌕'; position: absolute;
  left: 14px; top: 50%; transform: translateY(-50%);
  color: var(--text3); font-size: 17px; pointer-events: none;
}
.search-bar input {
  width: 100%; max-width: 860px;
  background: var(--bg2); border: 1px solid var(--border);
  color: var(--text); padding: 11px 16px 11px 42px;
  font-size: 14px; outline: none;
  font-family: var(--font-sans); border-radius: 4px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-bar input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(200,169,110,0.07);
}
.search-bar input::placeholder { color: var(--text3); }

/* ─── View toggle ─── */
.view-controls {
  display: flex; justify-content: flex-end; margin-bottom: 16px;
}
.view-toggle {
  display: flex;
  background: var(--bg2);
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08);
  border-radius: 5px; overflow: hidden;
}
.view-btn {
  background: none; border: none;
  color: var(--text3);
  padding: 6px 12px; gap: 5px;
  font-size: 12px; font-family: var(--font-sans);
  font-weight: 500; cursor: pointer;
  transition-property: color, background;
  transition-duration: 0.12s;
  display: flex; align-items: center;
  letter-spacing: 0.02em;
}
.view-btn:hover { color: var(--text2); background: rgba(255,255,255,0.04); }
.view-btn.active { color: var(--text); background: rgba(255,255,255,0.07); }

/* ─── List view ─── */
.entry-list { display: flex; flex-direction: column; }
.entry-row {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  column-gap: 20px;
  padding: 13px 6px;
  border-bottom: 1px solid var(--border);
  text-decoration: none; color: var(--text);
  transition-property: background; transition-duration: 0.1s;
}
.entry-list .entry-row:first-child { border-top: 1px solid var(--border); }
.entry-row:hover { background: rgba(255,255,255,0.025); }
.entry-row-title {
  font-family: var(--font-serif);
  font-size: 15px; line-height: 1.4;
  color: var(--text);
  grid-column: 1; grid-row: 1;
  transition: color 0.12s;
}
.entry-row:hover .entry-row-title { color: var(--accent2); }
.entry-row-type {
  font-family: var(--font-sans);
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--card-accent, var(--text2));
  white-space: nowrap;
  grid-column: 2; grid-row: 1; align-self: center;
}
.entry-row-excerpt {
  font-family: var(--font-sans);
  font-size: 12.5px; color: var(--text2);
  line-height: 1.5; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
  grid-column: 1 / 3; grid-row: 2;
  margin-top: 3px;
}

@media (max-width: 1000px) { main { padding: 36px 32px 60px; } }
@media (max-width: 768px) {
  .sidebar { display: none; }
  main { margin-left: 0; padding: 24px 18px 40px; }
}
"""

def _first_paragraph(content: str, max_len: int = 200) -> str:
    """Extract first substantive paragraph — skips all markdown headings and section labels."""
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            continue
        # Skip bare single-word section labels left over from heading stripping
        if len(line.split()) <= 2 and line[0].isupper():
            continue
        # Strip wikilinks, bold, italic markers
        line = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]', r'\1', line)
        line = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', line)
        line = re.sub(r'\[ungesichert\]', '', line)
        line = line.strip()
        if len(line) > 40:
            return line[:max_len] + ('…' if len(line) > max_len else '')
    return ''


_SEARCH_JS = """
document.addEventListener('DOMContentLoaded', function() {
  const input = document.getElementById('search-input');
  const grid  = document.querySelector('.entry-grid');
  const list  = document.querySelector('.entry-list');
  const toggleBtns = document.querySelectorAll('.view-btn');

  // Search — filters both views at once
  if (input) {
    input.addEventListener('input', function() {
      const q = this.value.toLowerCase();
      document.querySelectorAll('.entry-card, .entry-row').forEach(item => {
        item.style.display = item.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }

  // View toggle — persists to localStorage
  if (!toggleBtns.length) return;
  function setView(v) {
    toggleBtns.forEach(b => b.classList.toggle('active', b.dataset.view === v));
    if (grid) grid.style.display = v === 'grid' ? '' : 'none';
    if (list) list.style.display = v === 'list' ? '' : 'none';
    try { localStorage.setItem('wiki-view', v); } catch(e) {}
  }
  let saved = 'grid';
  try { saved = localStorage.getItem('wiki-view') || 'grid'; } catch(e) {}
  setView(saved);
  toggleBtns.forEach(btn => btn.addEventListener('click', () => setView(btn.dataset.view)));
});
"""

_GRAPH_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wissensgraph — Agenturgeschichte</title>
<link rel="stylesheet" href="assets/style.css">
<style>
html, body {{ height: 100%; margin: 0; overflow: hidden; }}
body {{ display: block; }}
#graph-wrap {{
  position: fixed;
  top: 0; left: var(--sidebar-w); right: 0; bottom: 0;
  display: flex; flex-direction: column;
}}
#graph-toolbar {{
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  padding: 8px 16px;
  display: flex; align-items: center; gap: 12px;
  flex-shrink: 0; z-index: 10;
  height: 44px;
}}
#graph-search {{
  background: var(--bg3); border: 1px solid var(--border);
  color: var(--text); padding: 5px 11px;
  border-radius: 3px; font-size: 13px; width: 190px; outline: none;
  transition: border-color 0.15s;
}}
#graph-search:focus {{ border-color: var(--accent); }}
#graph-stats {{ color: var(--text2); font-size: 11px; white-space: nowrap; }}
.zoom-btn {{
  background: var(--bg3); border: 1px solid var(--border);
  color: var(--text2); width: 26px; height: 26px;
  border-radius: 3px; cursor: pointer; font-size: 15px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s, color 0.15s; flex-shrink: 0; line-height: 1;
}}
.zoom-btn:hover {{ background: var(--bg4,#242424); color: var(--accent); border-color: var(--accent); }}
#graph-hint {{ color: var(--text3,#706860); font-size: 10px; margin-left: auto; white-space: nowrap; }}
#graph-svg {{ flex: 1; display: block; width: 100%; min-height: 0; cursor: grab; }}
#graph-svg:active {{ cursor: grabbing; }}
.leg-item {{
  display: flex; align-items: center; gap: 7px;
  padding: 5px 16px; cursor: pointer; user-select: none;
  font-size: 12px; color: var(--text2); transition: background 0.1s;
}}
.leg-item:hover {{ background: rgba(255,255,255,0.04); color: var(--text); }}
.leg-item.off {{ opacity: 0.3; }}
.leg-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
.node {{ cursor: pointer; }}
.node text {{ pointer-events: none; font-family: 'Helvetica Neue', Arial, sans-serif; }}
#tooltip {{
  position: fixed; display: none;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: 4px; padding: 9px 13px;
  font-size: 12px; pointer-events: none; z-index: 300;
  max-width: 240px; line-height: 1.5;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}}
#tooltip .t-type {{ font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700; margin-bottom: 3px; }}
#tooltip .t-title {{ color: var(--text); font-weight: 600; font-size: 13px; line-height: 1.3; }}
#tooltip .t-sub {{ color: var(--text2); font-size: 11px; margin-top: 3px; }}
#loading {{
  position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
  color: var(--text2); font-size: 13px; pointer-events: none;
  transition: opacity 0.4s;
}}
</style>
</head>
<body>
<nav class="sidebar">
  <a class="logo" href="index.html">Agentur<span>Geschichte</span></a>
  <a href="graph.html" class="graph-nav-link">⬡ Wissensgraph</a>
  <div class="nav-section">Typen</div>
  <div id="legend"></div>
  <div class="nav-section" style="margin-top:12px">Kategorien</div>
  {nav_links}
</nav>
<div id="graph-wrap">
  <div id="graph-toolbar">
    <input id="graph-search" type="text" placeholder="Suchen…">
    <span id="graph-stats"></span>
    <button class="zoom-btn" id="btn-fit" title="Alles zeigen">⊕</button>
    <button class="zoom-btn" id="btn-zi"  title="Zoom +">+</button>
    <button class="zoom-btn" id="btn-zo"  title="Zoom −">−</button>
    <span id="graph-hint">Klick = Artikel · Ziehen = bewegen · Scroll = zoom</span>
  </div>
  <svg id="graph-svg"><text id="loading" x="50%" y="50%" text-anchor="middle" fill="#706860" font-size="13" font-family="sans-serif">Initialisiere Graph…</text></svg>
</div>
<div id="tooltip"></div>
<script src="assets/d3.v7.min.js"></script>
<script>
const G = {graph_json};

const T = {{
  agency:     {{ l:"Agentur",      c:"#c8a96e" }},
  person:     {{ l:"Person",       c:"#7eb8d4" }},
  era:        {{ l:"Epoche",       c:"#9b7ec8" }},
  work:       {{ l:"Kampagne",     c:"#7ec87e" }},
  concept:    {{ l:"Konzept",      c:"#c87e7e" }},
  scandal:    {{ l:"Skandal",      c:"#d44444" }},
  life:       {{ l:"Agenturleben", c:"#d4a44c" }},
  technology: {{ l:"Technologie",  c:"#7ec8c8" }},
  visual:     {{ l:"Visuelles",    c:"#a0a0a0" }},
}};

// ── Legend ────────────────────────────────────────────────────────────────
const active = new Set(Object.keys(T));
const legEl = document.getElementById("legend");
Object.entries(T).forEach(([type, cfg]) => {{
  const div = document.createElement("div");
  div.className = "leg-item"; div.id = "leg-"+type;
  div.innerHTML = `<div class="leg-dot" style="background:${{cfg.c}}"></div>${{cfg.l}}`;
  div.addEventListener("click", () => {{
    if (active.has(type)) {{ active.delete(type); div.classList.add("off"); }}
    else {{ active.add(type); div.classList.remove("off"); }}
    applyFilter();
  }});
  legEl.appendChild(div);
}});

// ── Degree & radius ───────────────────────────────────────────────────────
const deg = {{}};
G.nodes.forEach(n => deg[n.id] = 0);
G.edges.forEach(e => {{
  if (deg[e.source] != null) deg[e.source]++;
  if (deg[e.target] != null) deg[e.target]++;
}});
const maxD = Math.max(1, ...Object.values(deg));
const rr = d => 5 + Math.sqrt((deg[d.id]||0) / maxD) * 16;

// Label threshold: show labels for top-30%-degree nodes by default
const sortedDeg = Object.values(deg).sort((a,b)=>b-a);
const labelThreshold = sortedDeg[Math.floor(sortedDeg.length * 0.25)] || 3;

// ── Neighbor map for hover highlighting ──────────────────────────────────
const neighborSet = new Map();
G.nodes.forEach(n => neighborSet.set(n.id, new Set()));
G.edges.forEach(e => {{
  const s = typeof e.source==="object" ? e.source.id : e.source;
  const t = typeof e.target==="object" ? e.target.id : e.target;
  neighborSet.get(s)?.add(t);
  neighborSet.get(t)?.add(s);
}});

// ── D3 setup ──────────────────────────────────────────────────────────────
const svgEl = document.getElementById("graph-svg");
const svg = d3.select(svgEl);
const g = svg.append("g");

const zoom = d3.zoom().scaleExtent([0.03, 10]).on("zoom", e => {{
  g.attr("transform", e.transform);
  // Show more labels as user zooms in
  const k = e.transform.k;
  nodeText.style("display", d =>
    k >= 1.4 || (deg[d.id]||0) >= labelThreshold ? null : "none"
  );
}});
svg.call(zoom);

const edgeColor = t => {{
  if (t==="founded_by")                 return "rgba(200,169,110,0.7)";
  if (t==="employed"||t==="worked_at")  return "rgba(126,184,212,0.5)";
  if (t==="belongs_to_era")             return "rgba(155,126,200,0.5)";
  if (t==="influenced"||t==="mentored") return "rgba(212,164,76,0.5)";
  if (t==="competed_with")              return "rgba(200,80,80,0.4)";
  if (t==="created")                    return "rgba(126,200,126,0.45)";
  return "rgba(255,255,255,0.09)";
}};

const linkSel = g.append("g").attr("class","links").selectAll("line")
  .data(G.edges).enter().append("line")
  .attr("stroke", d => edgeColor(d.type||"related"))
  .attr("stroke-width", d => d.type==="founded_by"?2:1)
  .attr("stroke-linecap","round");

const nodeSel = g.append("g").attr("class","nodes").selectAll("g")
  .data(G.nodes).enter().append("g").attr("class","node")
  .call(d3.drag()
    .on("start",(e,d)=>{{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
    .on("drag", (e,d)=>{{ d.fx=e.x; d.fy=e.y; }})
    .on("end",  (e,d)=>{{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}));

nodeSel.append("circle")
  .attr("r", rr)
  .attr("fill", d => (T[d.type]||{{}}).c || "#888")
  .attr("stroke", "rgba(0,0,0,0.5)").attr("stroke-width", 1);

const nodeText = nodeSel.append("text")
  .attr("dy","0.35em").attr("dx", d => rr(d)+4)
  .style("font-size","9px").style("fill","#c8c4bc")
  .style("display", d => (deg[d.id]||0) >= labelThreshold ? null : "none")
  .text(d => d.label.length>32 ? d.label.slice(0,29)+"…" : d.label);

// ── Tooltip + hover highlight ─────────────────────────────────────────────
const tip = document.getElementById("tooltip");
nodeSel
  .on("mouseover", (e, d) => {{
    const neighbors = neighborSet.get(d.id) || new Set();
    linkSel.attr("opacity", l => {{
      const s = typeof l.source==="object" ? l.source.id : l.source;
      const t = typeof l.target==="object" ? l.target.id : l.target;
      return (s===d.id || t===d.id) ? 1 : 0.06;
    }});
    nodeSel.selectAll("circle").attr("opacity", n =>
      n.id===d.id || neighbors.has(n.id) ? 1 : 0.18
    );
    nodeSel.selectAll("text").attr("opacity", n =>
      n.id===d.id || neighbors.has(n.id) ? 1 : 0.1
    );
  }})
  .on("mousemove", (e, d) => {{
    const cfg = T[d.type]||{{}};
    const x = e.clientX + 14, y = Math.min(e.clientY - 8, window.innerHeight - 100);
    tip.style.cssText = `display:block;left:${{x}}px;top:${{y}}px`;
    tip.innerHTML =
      `<div class="t-type" style="color:${{cfg.c||"#888"}}">${{cfg.l||d.type}}</div>`+
      `<div class="t-title">${{d.label}}</div>`+
      (d.era_from ? `<div class="t-sub">${{d.era_from}}${{d.era_to ? "–"+d.era_to : ""}}</div>` : "")+
      (d.geo_region ? `<div class="t-sub">${{d.geo_region.replace(/_/g," ")}}</div>` : "");
  }})
  .on("mouseout", () => {{
    tip.style.display = "none";
    linkSel.attr("opacity", 1);
    nodeSel.selectAll("circle").attr("opacity", 1);
    nodeSel.selectAll("text").attr("opacity", 1);
  }})
  .on("click", (e, d) => {{ if (d.path) location.href = d.path; }});

// ── Simulation ────────────────────────────────────────────────────────────
const sim = d3.forceSimulation(G.nodes)
  .force("link", d3.forceLink(G.edges).id(d=>d.id).distance(80).strength(0.2))
  .force("charge", d3.forceManyBody().strength(-280).distanceMax(400))
  .force("collide", d3.forceCollide().radius(d => rr(d)+6))
  .alphaDecay(0.025);

sim.on("tick", () => {{
  linkSel
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  nodeSel.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
}});

// ── Stats ─────────────────────────────────────────────────────────────────
document.getElementById("graph-stats").textContent =
  `${{G.nodes.length}} Knoten · ${{G.edges.length}} Kanten`;

// ── Search ────────────────────────────────────────────────────────────────
document.getElementById("graph-search").addEventListener("input", function() {{
  const q = this.value.toLowerCase().trim();
  if (!q) {{
    nodeSel.selectAll("circle").attr("stroke","rgba(0,0,0,0.5)").attr("stroke-width",1).attr("opacity",1);
    nodeSel.selectAll("text").attr("opacity",1);
    linkSel.attr("opacity",1);
    return;
  }}
  const matches = new Set(G.nodes.filter(n => n.label.toLowerCase().includes(q)).map(n=>n.id));
  nodeSel.selectAll("circle")
    .attr("stroke", d => matches.has(d.id) ? "#fff" : "rgba(0,0,0,0.5)")
    .attr("stroke-width", d => matches.has(d.id) ? 2.5 : 1)
    .attr("opacity", d => matches.has(d.id) ? 1 : 0.12);
  nodeSel.selectAll("text").attr("opacity", d => matches.has(d.id) ? 1 : 0.05);
  linkSel.attr("opacity", 0.05);
}});

// ── Filter ────────────────────────────────────────────────────────────────
function applyFilter() {{
  nodeSel.style("display", d => active.has(d.type) ? null : "none");
  linkSel.style("display", d => {{
    const s = typeof d.source==="object" ? d.source.type : null;
    const t = typeof d.target==="object" ? d.target.type : null;
    return (active.has(s) && active.has(t)) ? null : "none";
  }});
}}

// ── Zoom to fit ───────────────────────────────────────────────────────────
function zoomToFit() {{
  const box = g.node().getBBox();
  if (!box.width || !box.height) return;
  const W = svgEl.clientWidth, H = svgEl.clientHeight;
  if (!W || !H) return;
  const pad = 48;
  const scale = Math.min(0.95 * (W-pad*2) / box.width, 0.95 * (H-pad*2) / box.height);
  const tx = W/2 - scale * (box.x + box.width/2);
  const ty = H/2 - scale * (box.y + box.height/2);
  svg.transition().duration(650).ease(d3.easeQuadInOut)
     .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}}

// ── Zoom controls ────────────────────────────────────────────────────────
document.getElementById("btn-fit").addEventListener("click", zoomToFit);
document.getElementById("btn-zi").addEventListener("click", () =>
  svg.transition().duration(250).call(zoom.scaleBy, 1.5));
document.getElementById("btn-zo").addEventListener("click", () =>
  svg.transition().duration(250).call(zoom.scaleBy, 0.67));

// ── Init after layout ────────────────────────────────────────────────────
// requestAnimationFrame defers until after browser has computed flex layout,
// so svgEl.clientWidth/Height are the real pixel values — not 0.
requestAnimationFrame(() => {{
  const W = svgEl.clientWidth  || (window.innerWidth  - 252);
  const H = svgEl.clientHeight || (window.innerHeight - 44);
  sim.force("center", d3.forceCenter(W/2, H/2)).alpha(1).restart();
  // Remove loading indicator
  const ld = document.getElementById("loading");
  if (ld) ld.remove();
  // Auto-fit once simulation is cool
  sim.on("end", zoomToFit);
  // Also fit after 3s in case simulation never truly ends
  setTimeout(zoomToFit, 3000);
  // Resize handler
  window.addEventListener("resize", () => {{
    const nW = svgEl.clientWidth, nH = svgEl.clientHeight;
    sim.force("center", d3.forceCenter(nW/2, nH/2)).alpha(0.1).restart();
  }});
}});
</script>
</body>
</html>"""


def _inject_quellen_anchors(text: str) -> str:
    """
    In the raw markdown ## Quellen section, inject <a id="fn-N"> into each
    numbered list item so that inline [N] refs link to the correct footnote.
    E.g. "4. Source text" → "4. <a id="fn-4"></a>Source text"
    """
    in_quellen = False
    lines = []
    for line in text.split('\n'):
        if re.match(r'#+\s*Quellen', line):
            in_quellen = True
        if in_quellen:
            m = re.match(r'^(\d+)\.\s+(.*)', line)
            if m:
                n, content = m.group(1), m.group(2)
                line = f'{n}. <a id="fn-{n}"></a>{content}'
        lines.append(line)
    return '\n'.join(lines)


def _render_quellen_section(html: str) -> str:
    """Add CSS class to the <ol> that follows <h2>Quellen</h2>."""
    html = re.sub(
        r'(<h2[^>]*>Quellen</h2>\s*<ol)(\b)',
        r'<h2 id="quellen">Quellen</h2>\n<ol class="footnote-list"',
        html,
    )
    return html


class WikiBuilder:
    def __init__(self, kb, html_dir: Optional[Path] = None,
                 obsidian_dir: Optional[Path] = None):
        self.kb = kb
        self.html_dir = html_dir or WIKI_HTML_DIR
        self.obsidian_dir = obsidian_dir or WIKI_OBSIDIAN_DIR
        self.md_ext = ["extra", "smarty", "toc"]

    def build(self):
        print("  [WikiBuilder] Baue HTML-Wiki...")
        self._setup_dirs()
        self._write_assets()
        entries = self.kb.list_all()

        # Build graph first so edges are available for relation panels
        graph_data = self._build_graph_page()

        self._build_entry_pages(entries, graph_data)
        self._build_index(entries)
        print(f"  [WikiBuilder] ✓ HTML-Wiki: {self.html_dir}/index.html")

        print("  [WikiBuilder] Baue Obsidian Vault...")
        self._build_obsidian(entries)
        print(f"  [WikiBuilder] ✓ Obsidian: {self.obsidian_dir}/")

    def _setup_dirs(self):
        self.html_dir.mkdir(parents=True, exist_ok=True)
        (self.html_dir / "assets").mkdir(exist_ok=True)
        pages_dir = self.html_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        self.obsidian_dir.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIES:
            (self.obsidian_dir / cat).mkdir(exist_ok=True)

        # Clean stale HTML files: remove any entry-page HTML in a category dir
        # that no longer has a corresponding MD file in that category.
        for cat in CATEGORIES:
            cat_html_dir = pages_dir / cat
            cat_kb_dir = self.kb.root / cat
            if not cat_html_dir.exists():
                continue
            for html_file in cat_html_dir.glob("*.html"):
                expected_md = cat_kb_dir / f"{html_file.stem}.md"
                if not expected_md.exists():
                    html_file.unlink()
                    print(f"  [WikiBuilder] Removed stale page: pages/{cat}/{html_file.name}")

    def _write_assets(self):
        (self.html_dir / "assets" / "style.css").write_text(_CSS, encoding="utf-8")
        (self.html_dir / "assets" / "search.js").write_text(_SEARCH_JS, encoding="utf-8")
        # Bundle D3.js locally so graph.html works without internet
        d3_src = Path(__file__).parent.parent / "wiki" / "assets" / "d3.v7.min.js"
        d3_dst = self.html_dir / "assets" / "d3.v7.min.js"
        if d3_src.exists() and not d3_dst.exists():
            import shutil
            shutil.copy2(str(d3_src), str(d3_dst))

    def _nav_links(self, active_cat: str = "") -> str:
        lines = []
        for cat in CATEGORIES:
            label = CATEGORY_LABELS.get(cat, cat)
            cls = ' class="active"' if cat == active_cat else ''
            lines.append(f'<a href="../../pages/{cat}.html"{cls}>{label}</a>')
        return "\n  ".join(lines)

    def _nav_links_index(self, active_cat: str = "", prefix: str = "") -> str:
        lines = []
        for cat in CATEGORIES:
            label = CATEGORY_LABELS.get(cat, cat)
            cls = ' class="active"' if cat == active_cat else ''
            lines.append(f'<a href="{prefix}pages/{cat}.html"{cls}>{label}</a>')
        return "\n  ".join(lines)

    def _meta_badges(self, meta: dict) -> str:
        badges = []
        entity_type = meta.get("entity_type")
        if entity_type:
            cfg = ENTITY_TYPES.get(entity_type, {})
            color = cfg.get("color", "#888")
            label = cfg.get("label", entity_type)
            badges.append(
                f'<span class="badge" style="background:transparent;color:{color};'
                f'border:1px solid {color}">⬡ {label}</span>'
            )
        if meta.get("era"):
            badges.append(f'<span class="badge badge-era">{meta["era"]}</span>')
        if meta.get("era_from"):
            era_range = str(meta["era_from"])
            if meta.get("era_to"):
                era_range += f'–{meta["era_to"]}'
            if not meta.get("era"):
                badges.append(f'<span class="badge badge-era">{era_range}</span>')
        if meta.get("geo_region"):
            from tools.ontology import GEO_REGIONS
            geo_label = GEO_REGIONS.get(meta["geo_region"], {}).get("label", meta["geo_region"])
            badges.append(f'<span class="badge badge-tag">📍 {geo_label}</span>')
        conf = meta.get("confidence", "")
        if conf:
            badges.append(f'<span class="badge badge-confidence-{conf}">{conf}</span>')
        # Verification status badges
        if meta.get("strict_verified_wave"):
            ungesichert = meta.get("ungesichert", [])
            if ungesichert:
                badges.append(
                    f'<span class="badge badge-uncertain" '
                    f'title="{len(ungesichert)} ungesicherte Aussagen">⚠ teilw. ungesichert</span>'
                )
            else:
                badges.append('<span class="badge badge-verified">✓ quellengeprüft</span>')
        elif meta.get("verified_wave"):
            badges.append('<span class="badge badge-verified" style="opacity:0.6">geprüft</span>')
        if meta.get("sources"):
            src_count = len(meta["sources"])
            badges.append(
                f'<span class="badge badge-tag" title="{src_count} Quellen">'
                f'{src_count} Quellen</span>'
            )
        for tag in meta.get("tags", [])[:4]:
            badges.append(f'<span class="badge badge-tag">{tag}</span>')
        return f'<div class="meta-badges">{"".join(badges)}</div>' if badges else ""

    def _image_gallery_html(self, images: list) -> str:
        if not images:
            return ""
        figs = []
        for img in images:
            thumb = img.get("thumb_url") or img.get("url", "")
            if not thumb:
                continue
            caption = img.get("caption", "")
            license_str = img.get("license", "")
            artist = img.get("artist", "")
            source = img.get("source", "")
            status = img.get("copyright_status", "unknown")

            credit_parts = []
            if artist and artist != "unbekannt":
                credit_parts.append(artist)
            if license_str and license_str != "© unbekannt":
                credit_parts.append(license_str)
            credit_line = " · ".join(credit_parts) if credit_parts else ""

            source_link = (
                f' <a href="{source}" target="_blank" rel="noopener" '
                f'style="color:var(--link);text-decoration:none;">↗ Commons</a>'
                if source else ""
            )

            unknown_badge = (
                '<span class="img-copyright-unknown">© unklar</span>'
                if status == "unknown" else ""
            )

            figs.append(
                f'<figure>'
                f'<img src="{thumb}" alt="{caption}" loading="lazy">'
                f'<figcaption>'
                f'<span class="img-caption">{caption}</span>'
                f'<span class="img-credit">{credit_line}{source_link}</span>'
                f'{unknown_badge}'
                f'</figcaption>'
                f'</figure>'
            )
        if not figs:
            return ""
        return f'<div class="img-gallery">{"".join(figs)}</div>'

    def _build_title_index(self, entries_map: Dict) -> Dict:
        """Returns dict: lookup_key (lowercase) → (cat, fname, full_title)"""
        index = {}
        for fname, entry in entries_map.items():
            title = entry["meta"].get("title", "")
            cat = entry["path"].parent.name

            def add(key):
                k = key.strip().lower()
                if k and len(k) > 2 and k not in index:
                    index[k] = (cat, fname, title)

            # full title
            if title:
                add(title)

            # short name (before first em-dash, en-dash, or spaced hyphen)
            short = re.split(r'\s[—–-]\s', title)[0].strip()
            if short and short.lower() != title.lower():
                add(short)
                # Also strip parentheticals: "Doyle Dane Bernbach (DDB)" → "Doyle Dane Bernbach"
                no_paren = re.sub(r'\s*\([^)]*\)', '', short).strip()
                if no_paren and no_paren.lower() != short.lower():
                    add(no_paren)

            # the ID/slug itself
            add(fname)

            # Strip parentheticals from full title
            no_paren_full = re.sub(r'\s*\([^)]*\)', '', title).strip()
            if no_paren_full and no_paren_full.lower() != title.lower():
                add(no_paren_full)
                no_paren_short = re.split(r'\s[—–-]\s', no_paren_full)[0].strip()
                if no_paren_short and no_paren_short.lower() != no_paren_full.lower():
                    add(no_paren_short)

            # Extract named entity from long descriptive titles
            # e.g. "Die Geschichte der deutschen Werbeagentur Scholz & Friends" → extract "Scholz & Friends"
            # Look for capitalized proper nouns / brand names at the end after common German prepositions
            # Strategy: find the last segment after typical connectors
            for connector in [' über ', ' über', ' von ', ' zu ', ' nach ', ' bei ', ' für ']:
                if connector.lower() in title.lower():
                    idx_c = title.lower().rfind(connector.lower())
                    suffix = title[idx_c + len(connector):].strip()
                    # Remove trailing parentheticals
                    suffix = re.sub(r'\s*\([^)]*\)', '', suffix).strip()
                    # Remove part after em-dash
                    suffix = re.split(r'\s[—–-]\s', suffix)[0].strip()
                    if suffix and len(suffix) > 2:
                        add(suffix)

            # Strip German descriptive prefixes to expose the brand/proper name
            # e.g. "Die Geschichte der deutschen Werbeagentur Scholz & Friends" → "Scholz & Friends"
            # We progressively strip leading lowercase/common words until we find a capitalized proper noun start
            words = title.split()
            # Find first "proper noun" start (capitalized word that's not a common German article/prep)
            skip_words = {'die', 'der', 'das', 'des', 'dem', 'den', 'eine', 'einer', 'ein', 'eines',
                          'und', 'oder', 'von', 'zu', 'bei', 'für', 'mit', 'nach', 'über', 'unter',
                          'als', 'im', 'in', 'am', 'an', 'auf', 'aus', 'nach', 'zur', 'zum',
                          'geschichte', 'geschichte', 'britische', 'deutsche', 'deutschen', 'britischen',
                          'neue', 'neuen', 'alten', 'alte', 'erste', 'ersten', 'zweite', 'zweiten',
                          'hamburger', 'münchner', 'berliner', 'frankfurter', 'kölner',
                          'amerikanische', 'amerikanischen', 'europäische', 'europäischen',
                          'internationale', 'internationalen', 'werbeagentur', 'agentur',
                          'frühgeschichte', 'gründung'}
            for i, w in enumerate(words):
                clean_w = re.sub(r'[^a-zA-ZäöüÄÖÜß&]', '', w).lower()
                if i > 0 and clean_w and clean_w not in skip_words and w[0].isupper():
                    suffix = ' '.join(words[i:])
                    suffix = re.sub(r'\s*\([^)]*\)', '', suffix).strip()
                    suffix_short = re.split(r'\s[—–-]\s', suffix)[0].strip()
                    if len(suffix_short) > 3 and suffix_short.lower() != title.lower():
                        add(suffix_short)
                        add(suffix)
                    break

            # Also index tags as aliases (tags often contain the canonical short name)
            for tag in entry["meta"].get("tags", []):
                if tag and len(tag) > 2:
                    add(tag)

        return index

    def _render_md(self, text: str, entries_map: Dict) -> str:
        title_index = self._build_title_index(entries_map)

        def replace_wikilink(m):
            target = m.group(1)
            # 1. Direct lookup in title index
            key = target.lower()
            if key in title_index:
                cat, fname, full_title = title_index[key]
                return f'<a href="../../pages/{cat}/{fname}.html">{target}</a>'
            # 2. Slugify the target and look up
            slug = re.sub(r'[äÄ]', 'ae', target.lower())
            slug = re.sub(r'[öÖ]', 'oe', slug)
            slug = re.sub(r'[üÜ]', 'ue', slug)
            slug = re.sub(r'[ß]', 'ss', slug)
            slug = re.sub(r'[^a-z0-9_]+', '_', slug).strip('_')[:80]
            if slug in title_index:
                cat, fname, full_title = title_index[slug]
                return f'<a href="../../pages/{cat}/{fname}.html">{target}</a>'
            # 3. Partial match: check if target is contained in a key (e.g. "BBDO" in "bbdo — batten...")
            for key_lc, (cat, fname, full_title) in title_index.items():
                if key_lc.startswith(target.lower() + ' ') or key_lc == target.lower():
                    return f'<a href="../../pages/{cat}/{fname}.html">{target}</a>'
            return f"<em>{target}</em>"

        text = re.sub(r"\[\[([^\]]+)\]\]", replace_wikilink, text)
        # Convert [ungesichert] markers to styled inline badges
        text = re.sub(
            r'\[ungesichert\]',
            '<span class="ungesichert" title="Nicht durch externe Quellen belegt">ungesichert</span>',
            text,
        )
        # Convert (?) to a subtle uncertainty marker
        text = re.sub(r'\(\?\)', '<sup title="Unsichere Angabe">(?)</sup>', text)
        # Convert inline [1], [2][3] citation refs to superscript footnote anchors
        # Must run before markdown() so we can insert raw HTML
        text = re.sub(
            r'\[(\d+)\]',
            lambda m: f'<sup class="fn-ref"><a href="#fn-{m.group(1)}">[{m.group(1)}]</a></sup>',
            text,
        )
        # Inject anchor IDs into ## Quellen list items before rendering,
        # so "4. source text" gets <a id="fn-4"> that matches inline [4] refs.
        text = _inject_quellen_anchors(text)

        rendered = md.markdown(text, extensions=self.md_ext)

        # Post-process ## Quellen section: add CSS class to the <ol>
        rendered = _render_quellen_section(rendered)
        return rendered

    def _build_entry_pages(self, entries: List[Dict], graph_data: Optional[Dict] = None):
        entries_map = {e["path"].stem: e for e in entries}

        # Build adjacency: node_id → list of edges
        adj: Dict[str, List[Dict]] = {}
        if graph_data:
            for edge in graph_data.get("edges", []):
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                if src:
                    adj.setdefault(src, []).append(edge)
                if tgt:
                    # Add reverse for undirected display
                    adj.setdefault(tgt, []).append({**edge, "source": tgt, "target": src})

        for entry in entries:
            meta = entry["meta"]
            cat = entry["path"].parent.name
            fname = entry["path"].stem
            title = meta.get("title", fname)

            (self.html_dir / "pages" / cat).mkdir(exist_ok=True)

            body = self._render_md(entry["content"], entries_map)
            node_id = meta.get("id", fname)
            related = self._build_relation_panel(entry, entries, "../../pages/",
                                                  adj.get(node_id, []), entries_map)
            breadcrumb = (
                f'<a href="../../index.html">Start</a> › '
                f'<a href="../{cat}.html">{CATEGORY_LABELS.get(cat, cat)}</a> › '
                f'{title}'
            )

            gallery = self._image_gallery_html(meta.get("images", []))
            if gallery:
                body = gallery + body

            html = _HTML_BASE.format(
                title=title,
                root="../../",
                nav_links=self._nav_links(cat),
                breadcrumb=breadcrumb,
                meta_badges=self._meta_badges(meta),
                body=body,
                related_panel=related,
                header_class="",
                content_class="",
            )
            out = self.html_dir / "pages" / cat / f"{fname}.html"
            out.write_text(html, encoding="utf-8")

    def _build_relation_panel(self, entry: Dict, all_entries: List[Dict],
                              base_path: str, graph_edges: Optional[List] = None,
                              entries_map: Optional[Dict] = None) -> str:
        meta = entry["meta"]
        if entries_map is None:
            entries_map = {e["path"].stem: e for e in all_entries}

        seen_ids: set = set()
        cards: list = []

        # Graph-derived edges (most informative — typed relationships)
        for edge in (graph_edges or [])[:12]:
            # The edge was built with this node as source; target is the other end
            tgt_id = edge.get("target", "")
            if not tgt_id or tgt_id in seen_ids or tgt_id not in entries_map:
                continue
            seen_ids.add(tgt_id)
            e = entries_map[tgt_id]
            cat = e["path"].parent.name
            fname = e["path"].stem
            rel_type = edge.get("type", "related")
            rel_label = edge.get("label", rel_type)
            entity_type = e["meta"].get("entity_type", "")
            type_color = ENTITY_TYPES.get(entity_type, {}).get("color", "#888")
            cards.append(
                f'<a class="related-card" href="{base_path}{cat}/{fname}.html">'
                f'<small style="color:{type_color}">{rel_label}</small>'
                f'<strong>{e["meta"].get("title", fname)}</strong>'
                f'</a>'
            )

        # Frontmatter typed relations (enrichment-added)
        entries_by_id = entries_map
        for rel in meta.get("relations", [])[:8]:
            tgt_id = rel.get("target_id", "")
            if not tgt_id or tgt_id in seen_ids or tgt_id not in entries_by_id:
                continue
            seen_ids.add(tgt_id)
            e = entries_by_id[tgt_id]
            cat = e["path"].parent.name
            fname = e["path"].stem
            rel_label = rel.get("label", rel.get("type", ""))
            entity_type = e["meta"].get("entity_type", "")
            type_color = ENTITY_TYPES.get(entity_type, {}).get("color", "#888")
            cards.append(
                f'<a class="related-card" href="{base_path}{cat}/{fname}.html">'
                f'<small style="color:{type_color}">{rel_label}</small>'
                f'<strong>{e["meta"].get("title", fname)}</strong>'
                f'</a>'
            )

        if not cards:
            return ""
        return (
            '<div class="related-panel"><h3>Verbindungen</h3>'
            f'<div class="related-cards">{"".join(cards)}</div></div>'
        )

    def _build_index(self, entries: List[Dict]):
        for cat in CATEGORIES:
            cat_entries = [e for e in entries if e["path"].parent.name == cat]
            if not cat_entries:
                continue
            label = CATEGORY_LABELS.get(cat, cat)
            cards = []
            rows = []
            for e in cat_entries:
                meta = e["meta"]
                fname = e["path"].stem
                title = meta.get("title", fname)
                excerpt = _first_paragraph(e["content"], max_len=180)
                tags_html = "".join(
                    f'<span class="tag">{t}</span>'
                    for t in meta.get("tags", [])[:3]
                )
                era = meta.get("era", "")
                entity_type = meta.get("entity_type", "")
                entity_cfg = ENTITY_TYPES.get(entity_type, {})
                entity_color = entity_cfg.get("color", "")
                entity_label = entity_cfg.get("label", "")
                style_attr = f' style="--card-accent:{entity_color}"' if entity_color else ""
                cards.append(
                    f'<a class="entry-card" href="{cat}/{fname}.html"{style_attr}>'
                    f'<div class="card-body">'
                    f'{"<span class=\'card-type\'>" + entity_label + "</span>" if entity_label else ""}'
                    f'{"<div class=\'era\'>" + era + "</div>" if era else ""}'
                    f'<h3>{title}</h3>'
                    f'<div class="excerpt">{excerpt}</div>'
                    f'<div class="tags">{tags_html}</div>'
                    f'</div>'
                    f"</a>"
                )
                rows.append(
                    f'<a class="entry-row" href="{cat}/{fname}.html"{style_attr}>'
                    f'<span class="entry-row-title">{title}</span>'
                    f'{"<span class=\'entry-row-type\'>" + entity_label + "</span>" if entity_label else ""}'
                    f'<div class="entry-row-excerpt">{excerpt}</div>'
                    f'</a>'
                )

            _ico_grid = ('<svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor">'
                         '<rect x="0" y="0" width="5" height="5" rx="1"/>'
                         '<rect x="8" y="0" width="5" height="5" rx="1"/>'
                         '<rect x="0" y="8" width="5" height="5" rx="1"/>'
                         '<rect x="8" y="8" width="5" height="5" rx="1"/>'
                         '</svg>')
            _ico_list = ('<svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor">'
                         '<rect x="0" y="1" width="13" height="2" rx="1"/>'
                         '<rect x="0" y="5.5" width="13" height="2" rx="1"/>'
                         '<rect x="0" y="10" width="13" height="2" rx="1"/>'
                         '</svg>')
            toggle_html = (
                f'<div class="view-controls">'
                f'<div class="view-toggle">'
                f'<button class="view-btn active" data-view="grid">{_ico_grid} Kacheln</button>'
                f'<button class="view-btn" data-view="list">{_ico_list} Liste</button>'
                f'</div></div>'
            )
            cat_html = (
                f'<div class="search-bar"><input type="text" id="search-input" '
                f'placeholder="Suche in {label}…"></div>'
                + toggle_html
                + f'<div class="entry-grid">{"".join(cards)}</div>'
                + f'<div class="entry-list" style="display:none">{"".join(rows)}</div>'
            )
            html = _HTML_BASE.format(
                title=label,
                root="../",
                nav_links=self._nav_links_index(cat, prefix="../"),
                breadcrumb=f'<a href="../index.html">Start</a> › {label}',
                meta_badges="",
                body=cat_html,
                related_panel="",
                header_class=" is-index",
                content_class=" content-wide",
            )
            (self.html_dir / "pages" / f"{cat}.html").write_text(html, encoding="utf-8")

        # Main index
        stats = self.kb.get_stats()
        sections = []
        for cat in CATEGORIES:
            cat_entries = [e for e in entries if e["path"].parent.name == cat]
            if not cat_entries:
                continue
            label = CATEGORY_LABELS.get(cat, cat)
            def _mini_card(e, cat=cat):
                m = e["meta"]
                et = m.get("entity_type", "")
                cfg = ENTITY_TYPES.get(et, {})
                ec = cfg.get("color", "")
                el = cfg.get("label", "")
                sa = f' style="--card-accent:{ec}"' if ec else ""
                excerpt = _first_paragraph(e["content"], max_len=120)
                return (f'<a class="entry-card" href="pages/{cat}/{e["path"].stem}.html"{sa}>'
                        f'<div class="card-body">'
                        f'{"<span class=\'card-type\'>" + el + "</span>" if el else ""}'
                        f'<h3>{m.get("title", "")}</h3>'
                        f'<div class="excerpt">{excerpt}</div>'
                        f'</div>'
                        f'</a>')
            cards = "".join(_mini_card(e) for e in cat_entries[:4])
            sections.append(
                f'<div class="category-section">'
                f'<h2><strong>{label}</strong>'
                f'<a href="pages/{cat}.html">alle {stats.get(cat,0)} →</a></h2>'
                f'<div class="entry-grid">{cards}</div>'
                f"</div>"
            )

        hero = (
            f'<div class="index-hero">'
            f'<p>Eine kuratierte Wissenssammlung zur Geschichte der Werbebranche — '
            f'Agenturen, Persönlichkeiten, Epochen und die Kultur des kreativen Betriebs.</p>'
            f'<div class="index-stats">'
            f'<div class="stat-item"><strong>{stats["total"]}</strong>Einträge</div>'
            f'<div class="stat-item"><strong>{len([c for c in CATEGORIES if stats.get(c,0)>0])}</strong>Kategorien</div>'
            f'</div>'
            f'</div>'
        )
        body = (
            hero
            + f'<div class="search-bar"><input type="text" id="search-input" '
            f'placeholder="Suche in allen Einträgen…"></div>'
            + "".join(sections)
        )
        html = _HTML_BASE.format(
            title="Agenturgeschichte",
            root="",
            nav_links=self._nav_links_index(),
            breadcrumb="Start",
            meta_badges="",
            body=body,
            related_panel="",
            header_class=" is-index",
            content_class=" content-wide",
        )
        (self.html_dir / "index.html").write_text(html, encoding="utf-8")

    def _build_graph_page(self) -> Optional[Dict]:
        """Generate wiki/graph.html with embedded D3.js force graph. Returns graph data."""
        try:
            from tools.graph_builder import GraphBuilder
            graph_data = GraphBuilder(self.kb).build()
        except Exception as e:
            graph_json_path = self.html_dir / "graph.json"
            if graph_json_path.exists():
                graph_data = json.loads(graph_json_path.read_text(encoding="utf-8"))
            else:
                print(f"  [WikiBuilder] Graph übersprungen: {e}")
                return None

        nav = self._nav_links_index()
        html = _GRAPH_HTML.format(
            graph_json=json.dumps(graph_data, ensure_ascii=False),
            nav_links=nav,
        )
        (self.html_dir / "graph.html").write_text(html, encoding="utf-8")
        print(f"  [WikiBuilder] ✓ Wissensgraph: {self.html_dir}/graph.html")
        return graph_data

    def _build_obsidian(self, entries: List[Dict]):
        """Write Obsidian-compatible markdown with [[wikilinks]]."""
        for entry in entries:
            meta = entry["meta"]
            cat = entry["path"].parent.name
            fname = entry["path"].stem
            title = meta.get("title", fname)

            fm_lines = [
                "---",
                f"title: \"{title}\"",
                f"type: {cat}",
                f"era: \"{meta.get('era', '')}\"",
                f"tags: [{', '.join(meta.get('tags', []))}]",
                f"confidence: {meta.get('confidence', 'medium')}",
                f"wave: {meta.get('wave', 0)}",
            ]
            if meta.get("entity_type"):
                fm_lines.append(f"entity_type: {meta['entity_type']}")
            if meta.get("geo_region"):
                fm_lines.append(f"geo_region: {meta['geo_region']}")
            if meta.get("era_from"):
                fm_lines.append(f"era_from: {meta['era_from']}")
            if meta.get("era_to"):
                fm_lines.append(f"era_to: {meta['era_to']}")
            fm_lines += ["---", ""]

            out_path = self.obsidian_dir / cat / f"{fname}.md"
            out_path.write_text(
                "\n".join(fm_lines) + entry["content"],
                encoding="utf-8",
            )

        readme = (
            "# Agenturgeschichte — Obsidian Vault\n\n"
            f"_Generiert: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
            "Öffne diesen Ordner als Vault in Obsidian.\n\n"
            "## Kategorien\n"
            + "\n".join(f"- [[{CATEGORY_LABELS[cat]}]]" for cat in CATEGORIES)
        )
        (self.obsidian_dir / "README.md").write_text(readme, encoding="utf-8")
