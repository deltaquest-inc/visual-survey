# Contributing

Issues and pull requests are welcome. This is a small set of plain scripts, so changes that
keep it that way (standard library only, no network access except through the review CLIs
you configure) are the easiest to accept.

- Open an issue first for anything larger than a bug fix.
- Run `python3 -m unittest discover -s tests` and `ruff check .` before opening a pull request.
- Do not add sample images, comments or data you do not have the right to publish. Examples
  use CC0 material only.
- The tool does not download images from Pinterest or any other site, and pull requests that
  add such a fetcher will not be merged.

## Licence of contributions

By submitting a contribution you agree that it is licensed under the project's MIT licence
(`LICENSE`), the same terms the project is published under. There is no CLA and no sign-off
requirement.

## Review

One maintainer reviews pull requests. Expect a first reply within two weeks.
