# Prompt Versioning

Use semantic versioning for prompt files to keep runs reproducible.

## Version Format
- `MAJOR.MINOR.PATCH`
- `MAJOR`: incompatible prompt behavior/structure changes.
- `MINOR`: backward-compatible additions/clarifications.
- `PATCH`: typo/fix-only updates with no workflow impact.

## Required Metadata (per prompt file)
Add a short header block:
- `Prompt-Version:`
- `Last-Updated:`
- `Owner:`
- `Depends-On:` (optional)

## Update Process
1. Change prompt.
2. Bump version according to change type.
3. Record change in changelog table below.
4. Notify team which versions should be used for new runs.

## Changelog
| Date | File | Old | New | Change Type | Summary |
|------|------|-----|-----|-------------|---------|
| YYYY-MM-DD | <file> | x.y.z | x.y.z | major/minor/patch | <summary> |
