# notebooks

Exploration. Nothing here is imported by `src/assay` — if something in a
notebook becomes load-bearing, move it into the package and import it back.

Clear outputs before committing. The pre-commit hook rejects files over 512 KB,
which a notebook with a rendered page image will exceed, and a notebook that
has touched `data/docile` may have invoice contents in its output cells.
