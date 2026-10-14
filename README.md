# visual-survey

Scripts for describing a set of reference images with several AI models and checking them
against each other. Typical use: a team picks images for a visual direction, each pick comes
with a comment ("like", "mixed", "dislike"), and you want to know what the images actually show
before drawing conclusions from the comments.

The method uses three readers:

1. You write a one-line first read of every image (`claude.json`) before any model runs.
2. Two independent model reviews tag every image: subject, palette, light, rendering, outline,
   saturation, composition, mood, marks, tags.
3. `compare.py` flags where the readers disagree, you adjudicate those, and `counts.py` counts
   outline and saturation per sentiment on the final labels.

`build_page.py` then builds a page where the person who picked the images can confirm or
correct each description.

| Script | Does |
|---|---|
| `scripts/review.py` | Runs the two model reviews on a folder of images |
| `scripts/compare.py` | Cross-checks the reviews and your first read, writes `disagreements.md` and `adjudication.json` |
| `scripts/counts.py` | Outline and saturation counts per sentiment |
| `scripts/build_page.py` | Builds the correction page (`page.html`) |

## Privacy notice

**The images you review are sent to third-party AI services.** `review.py` runs the command
line tools you configure: the OpenAI Codex CLI (`codex`), the Google CLI (`agy`) and, if you
choose it, the Anthropic Claude CLI (`claude`). Each image, the respondent's comments and the
context text you supply are passed to those tools and processed under the providers' own terms
and privacy policies, with whatever account and data settings you have on each. This project
does not send data anywhere else and has no server of its own. Only review images you have the
right to send to those providers: do not use images you do not own or hold a licence for, and
do not include personal data in comments or context. The bundled example uses CC0 images only.
Use `--dry-run` to see what would be run without sending anything.

## Why there is no Pinterest fetcher

This tool starts from a folder of images you already have. It does not download pins.
Pinterest's terms of service bar accessing content by automated means without its express
permission, and its API only returns pins the operating account owns. If your respondents use
Pinterest, ask them to save the images and send them to you.

## Install

Requirements: Python 3 (standard library only, no packages to install), and the CLI for each
reviewer you run, already signed in: `codex`, `agy`, `claude`. `build_page.py` uses `sips`, so
it runs on macOS only. The page it writes expects a host that provides a `claude.use` runtime
with `db` and `user` capabilities (see the docstring in `scripts/build_page.py`).

    git clone <this repository>
    cd visual-survey
    python3 -m unittest discover tests

## Choosing models

There are no default models. Pass one per reviewer you run, as an argument or an environment
variable; `review.py` stops with an error if it is missing.

| Reviewer | Argument | Environment variable |
|---|---|---|
| `codex` | `--codex-model` | `VS_CODEX_MODEL` |
| `gemini` | `--gemini-model` | `VS_GEMINI_MODEL` |
| `claude_second` | `--claude-model` | `VS_CLAUDE_MODEL` |

The default pair is `codex` and `gemini`. Choose another pair with `--reviewers codex claude_second`.
`build_page.py` also reads `VS_SOURCE_URL_TEMPLATE` (the same as `--source-url-template`, a link
per image that must contain `{id}`).

## Example

`examples/cc0-demo/` holds eight CC0 images, an invented respondent and every input file, with
a step-by-step walkthrough in `examples/cc0-demo/WALKTHROUGH.md`. Licence, creator and source
page of each image are in `examples/cc0-demo/SOURCES.md`.

## Contributing

Issues and pull requests are welcome, see `CONTRIBUTING.md`. Security reports: `SECURITY.md`.
Changes are listed in `CHANGELOG.md`.

## AI assistance

This code was written by Delta Quest with AI coding assistants. A human reviews it, and the tests and
linter run on every pull request.

## Licence

MIT, see `LICENSE`.
