---
name: sdk-release
description: Use when bumping the project-x-py version, writing release notes, tagging, or publishing to PyPI.
---

# SDK release

1. Confirm `./check_quality.sh` and `uv run pytest` pass.
2. Choose semver: PATCH (fix), MINOR (compatible feature), MAJOR (break / removed deprecation).
3. Update `CHANGELOG.md` under a version heading. User-facing behavior needs an entry.
4. Breaking changes get a note in `docs/migration/`.
5. Build: `uv build`. Check `dist/`.
6. Tag `vX.Y.Z` only after the user confirms.
7. Publish to PyPI only if the user explicitly asks.

Do not skip tests. Do not force-push tags.
