# Repository Agent Notes

## Performance-first file access
- Never recurse through `.venv/` or `.git/`.
- Prefer targeted reads of known files over broad directory scans.
- Do not run `Get-ChildItem -Recurse` from repository root unless a strict path filter is provided.

## Search strategy for this repo
- `rg` is not guaranteed to be installed on this machine.
- Default search flow:
  1. Use `git ls-files` (and optionally `git ls-files --others --exclude-standard`) to get a controlled file list.
  2. Pipe that list to `Select-String` for content search.
- Keep excludes for heavy folders: `.venv`, `.git`, `__pycache__`, `.idea`, `.ruff_cache`, `.pytest_cache`, `node_modules`, `dist`, `build`.

## Read scope
- Read only files relevant to the user request.
- For quick repo inspection, prefer `git ls-files` instead of filesystem-wide recursion.
