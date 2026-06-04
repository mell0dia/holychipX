# Holy Chip — Book Project

Experiments toward a printed book of the Holy Chip comics + origin stories.

## Folder layout

```
book/
├── README.md          ← this file
├── src/               ← per-story chapters (auto-generated, can be regenerated)
├── templates/         ← layout templates (LaTeX, HTML/CSS, Pandoc CSS)
├── assets/            ← cover, fonts, decorative elements specific to the book
└── build/             ← compiled output (PDF, EPUB, etc.) — git-ignored
```

## Current state

- **Source content lives in:** `~/holy-chip/website/holy-chip-site/stories/`
  - Images: `HC###.png`
  - English blog: `analysis/HC###.blog.md`
  - PT/ES/FR blogs: `analysis/HC###.blog.<lang>.md`
- **Total stories:** 23 (HC000-HC022)

## Approach options (to experiment)

1. **Pandoc → PDF (LaTeX)** — markdown blogs + images compiled via Pandoc with a custom LaTeX template. Good control, single source of truth, regenerates with every new story.
2. **Pandoc → PDF (HTML/CSS via WeasyPrint or Prince)** — same source, but CSS-based layout. Easier to iterate visually.
3. **InDesign** — manual layout, prettiest result, but locked-in per page.

Recommended first experiment: option 1 (Pandoc + LaTeX). Build target: 8.5"×11" full-color hardcover, ~150 pages, English-only.

## Next steps

- Build a Pandoc script that pulls blogs + images and emits one PDF
- Decide: English-only or 4-language editions?
- Cover design
- POD vendor: Blurb (premium paper) vs KDP (reach) vs Lulu vs IngramSpark
