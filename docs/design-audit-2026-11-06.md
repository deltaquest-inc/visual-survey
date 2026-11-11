# Correction-page migration evidence

Both versions use the same eight CC0 sample images, descriptions, comments and viewport sizes. The baseline uses the pre-migration Python template; the candidate embeds the locally compiled Tailwind stylesheet. No AI model or new provider is invoked.

| Viewport | Before | Candidate |
| --- | --- | --- |
| 1440px | [Before](design-audit-2026-11-06/before-1440.png) | [Candidate](design-audit-2026-11-06/after-1440.png) |
| 390px | [Before](design-audit-2026-11-06/before-390.png) | [Candidate](design-audit-2026-11-06/after-390.png) |

All eight decoded image-source hashes, buttons and the h1 match between baseline and candidate. No horizontal overflow or broken image was detected at either width. Tailwind Preflight removes incidental browser form spacing; intended comment bullets are explicitly retained with list-disc. The UTF-8 document declaration also prevents the circled section marker from rendering as mojibake.

`npm run design:check` verifies the source contract, explicit contrast pairs and byte-for-byte freshness of compiled CSS; its regression tests cover absent imports/tokens, insufficient contrast, empty inventory and missing theme coverage. `python3 -m unittest discover -s tests` passes all ten existing tests. The committed CSS keeps Python generation and respondent viewing independent of a Node runtime or CSS CDN.

Practice used: the pinned Impeccable existing-page audit from `docs/design-references.md` (hierarchy, color, interaction and responsive review), applied under the DESIGN.md contract. It improved the page by fixing the document charset declaration, restoring `list-disc` on comment bullets after Preflight, and replacing implicit colors with explicit, checked contrast pairs.

These comparisons verify the scoped migration and visible content, not every browser/interaction or a full accessibility certification.
