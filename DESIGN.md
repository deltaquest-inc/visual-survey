# Visual survey design system

The generated correction page is a maintained browser interface. Tailwind v4 compiles local CSS at development time; the Python generator embeds the committed output so respondents need no Node runtime, no network request for the Tailwind output and no extra asset file. The page template still loads the Google Fonts stylesheet.

## Token sources

`scripts/design.source.css` owns the dark page, panel, ink, muted, accent, state, radius and font roles. `@theme inline` maps them into semantic Tailwind utilities. `scripts/page.tpl.html` and the card renderer in `scripts/build_page.py` consume those utilities and existing component CSS. `scripts/design.css` is generated; never edit it directly. Build with `npm ci && npm run design:build` after changing source or class usage.

## Components

Keep the correction-page filter/jump bar, image cards, vote controls and notes consistent. Reuse the single card template in build_page.py rather than introducing independently styled card variants. Use literal classes so the Tailwind compiler detects them. Existing complex grid, sticky and state styling stays in the components layer.

## Accessibility

Preserve button/textarea labels, aria-live save status and pressed states. Review text/accent contrast, focus rings, long descriptions, keyboard filter/jump interactions and reduced motion at mobile/desktop widths. Generated pages retain the original provider/storage/privacy boundaries; styling changes do not authorize any new image upload.

## Review and learning

Read [the task-triggered pinned references](docs/design-references.md) when its matching occasion arises. Record which practice was actually used and what it improved.


Run `npm run design:check` and `python3 -m unittest discover -s tests`. CI checks the source contract, contrast pairs and byte-for-byte freshness of compiled Tailwind output. Build a sample correction page and compare the same assets/descriptions/viewport before and after a visual change. Keep useful craft rules in this owner, not a separate unlinked reference library. Static checks are not a full rendered accessibility certification.
