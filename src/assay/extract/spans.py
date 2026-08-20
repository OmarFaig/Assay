"""Character spans for every scalar value in a JSON document.

Constrained decoding guarantees the model's output is well-formed JSON, so this
scanner needs no error handling and no recovery — it can assume every construct
it meets is complete and correctly delimited. That assumption is the whole
reason it fits in a page. The standard library is no help here: `json` parses to
values and discards positions, and `raw_decode` only reports where a top-level
document ended.

Paths use dotted keys and bracketed indices — `total_gross`,
`line_items[0].unit_price` — the notation eval and review both address fields
by, so it is worth keeping stable.

Spans cover the value *including* its quotes. The opening quote is not
punctuation to be trimmed: at that position the grammar admits both `"` and
`null`, so the token carries the model's decision to answer rather than abstain,
which is the single most informative signal per field.
"""

from __future__ import annotations

_WHITESPACE = " \t\n\r"
_LITERAL_END = ",}]" + _WHITESPACE


def value_spans(text: str) -> dict[str, tuple[int, int]]:
    """Map every scalar value's path to its `[start, end)` character span."""
    return _Scanner(text).run()


class _Scanner:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0
        self.out: dict[str, tuple[int, int]] = {}

    def run(self) -> dict[str, tuple[int, int]]:
        self._value("")
        return self.out

    def _skip_ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in _WHITESPACE:
            self.i += 1

    def _value(self, path: str) -> None:
        self._skip_ws()
        start = self.i
        char = self.s[self.i]
        if char == "{":
            self._object(path)
        elif char == "[":
            self._array(path)
        else:
            # Strings and literals alike: consume, then record. Containers are
            # not recorded — a field is a scalar, and `line_items` as a whole
            # has no single value to score.
            self._string() if char == '"' else self._literal()
            self.out[path] = (start, self.i)

    def _object(self, path: str) -> None:
        self.i += 1  # '{'
        self._skip_ws()
        if self.s[self.i] == "}":
            self.i += 1
            return
        while True:
            self._skip_ws()
            key_start = self.i
            self._string()
            key = self.s[key_start + 1 : self.i - 1]
            self._skip_ws()
            self.i += 1  # ':'
            self._value(f"{path}.{key}" if path else key)
            self._skip_ws()
            if self.s[self.i] == ",":
                self.i += 1
                continue
            self.i += 1  # '}'
            return

    def _array(self, path: str) -> None:
        self.i += 1  # '['
        self._skip_ws()
        if self.s[self.i] == "]":
            self.i += 1
            return
        index = 0
        while True:
            self._value(f"{path}[{index}]")
            self._skip_ws()
            if self.s[self.i] == ",":
                self.i += 1
                index += 1
                continue
            self.i += 1  # ']'
            return

    def _string(self) -> None:
        self.i += 1  # opening quote
        while self.s[self.i] != '"':
            self.i += 2 if self.s[self.i] == "\\" else 1
        self.i += 1  # closing quote

    def _literal(self) -> None:
        while self.i < len(self.s) and self.s[self.i] not in _LITERAL_END:
            self.i += 1
