# Worked example: CC0 demo set

Eight CC0 images (see `SOURCES.md`), an invented respondent, and the files the tools expect in
a run directory. Run everything from the repository root. The commands below call paid model
CLIs; read the privacy notice in the top-level README first. Pick any model names your own
accounts support: `<codex-model>`, `<gemini-model>` are placeholders.

## Files

1. `images/<id>.jpg`: the images, named by pin id (digits only).
2. `run/manifest.json`: one entry per image: `id`, `category` (list), `comment` (list), `sentiment` (`like`, `mixed` or `dislike`).
3. `run/context.md`: one paragraph about the product, put into every reviewer prompt.
4. `run/claude.json`: `{id: one-line subject}`, your own first read of each image, written before any model runs. `review.py` refuses to start without it. Here it was written by looking at each image.

## 1. Check inputs without any model call

    python3 scripts/review.py examples/cc0-demo/run examples/cc0-demo/images \
      --codex-model <codex-model> --gemini-model <gemini-model> --dry-run

This validates the images and prints the commands it would run. It sends nothing, but it does
write `assets.json` and `reviewers.json` into `run/`; delete them if you do not run the real
review.

## 2. Two independent reviews (sends the images to OpenAI and Google)

    python3 scripts/review.py examples/cc0-demo/run examples/cc0-demo/images \
      --respondent "the demo respondent" \
      --codex-model <codex-model> --gemini-model <gemini-model>

Writes `codex.json` and `gemini.json` in `run/`. To use Claude as one reviewer instead, add
`--reviewers codex claude_second --claude-model <claude-model>` (images then go to Anthropic).
The same models can come from `VS_CODEX_MODEL`, `VS_GEMINI_MODEL`, `VS_CLAUDE_MODEL`.

## 3. Cross-check

    python3 scripts/compare.py examples/cc0-demo/run

Writes `disagreements.md` (pins where the reviewers describe different things, or disagree on
outline or saturation) and `adjudication.json`. Open each flagged image yourself and fill the
verdicts; an existing `adjudication.json` is never overwritten.

## 4. Counts

    python3 scripts/counts.py examples/cc0-demo/run

Writes `counts.md` and `final-labels.json`: outline and saturation per sentiment, on the final
labels. It stops if a pin has no final label.

## 5. Correction page

Write `run/shows.json` as `{id: {"shows": "<subject>", "tags": []}}` for every id (images that
share the same `shows` text are cross-referenced), then:

    python3 scripts/build_page.py examples/cc0-demo/run examples/cc0-demo/images \
      --title "Pick check" --intro "Your picks, numbered. Is each description right?" \
      --source-url-template "https://example.com/{id}"

`--source-url-template` is optional (it must contain `{id}`). Thumbnails are made with `sips`,
so this step needs macOS. The page is written to `run/page.html`.
