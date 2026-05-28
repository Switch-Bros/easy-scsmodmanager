"""Parser for plaintext SiiNunit files (manifest.sii and similar).

SCS uses a custom property-list format. A typical file looks like:

    SiiNunit
    {
    mod_package: .package
    {
        package_version: "1.0.0"
        display_name: "Some Name"
        category[]: "sound"
        category[]: "ui"
        compatible_versions[]: "1.59.*"
    }
    }

Encrypted SiiB / ScsC files need decryption first (see integrations.sii.crypto).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class SiiParseError(ValueError):
    pass


@dataclass(frozen=True)
class SiiUnit:
    unit_class: str
    unit_name: str
    properties: dict[str, Any] = field(default_factory=dict)


_INT_RE = re.compile(r"^-?\d+$")
_HEX_RE = re.compile(r"^-?0x[0-9a-fA-F]+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+(?:[eE][+-]?\d+)?$")


@dataclass
class _Token:
    kind: str  # IDENT | STRING | LBRACE | RBRACE | LBRACK | RBRACK | COLON
    value: str
    line: int


_STRUCTURAL = {"{": "LBRACE", "}": "RBRACE", "[": "LBRACK", "]": "RBRACK", ":": "COLON"}


def _decode_byte_string(s: str) -> str:
    # \xNN escapes produce individual code points 0-255. When the byte
    # sequence is valid UTF-8 (multi-byte non-ASCII chars), recombine
    # it. Otherwise leave the latin-1 view intact.
    if not any(ord(c) > 127 for c in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    line = 1
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue
        if ch == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == '"':
            start_line = line
            i += 1
            chars: list[str] = []
            terminated = False
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    if nxt == "x" and i + 3 < n:
                        try:
                            byte_val = int(text[i + 2 : i + 4], 16)
                            chars.append(chr(byte_val))
                            i += 4
                            continue
                        except ValueError:
                            pass
                    if nxt == "n":
                        chars.append("\n")
                    elif nxt == "t":
                        chars.append("\t")
                    elif nxt == "r":
                        chars.append("\r")
                    else:
                        chars.append(nxt)
                    i += 2
                    continue
                if c == '"':
                    i += 1
                    terminated = True
                    break
                if c == "\n":
                    break
                chars.append(c)
                i += 1
            if not terminated:
                raise SiiParseError(f"Unterminated string at line {start_line}")
            tokens.append(_Token("STRING", _decode_byte_string("".join(chars)), start_line))
            continue
        if ch in _STRUCTURAL:
            tokens.append(_Token(_STRUCTURAL[ch], ch, line))
            i += 1
            continue
        # Identifier-ish: read until whitespace or structural/comment start
        start = i
        while i < n and text[i] not in " \t\r\n{}[]:#":
            if text[i] == "/" and i + 1 < n and text[i + 1] == "/":
                break
            i += 1
        tokens.append(_Token("IDENT", text[start:i], line))
    return tokens


def _coerce_value(token: _Token) -> Any:
    if token.kind == "STRING":
        return token.value
    raw = token.value
    if raw == "true":
        return True
    if raw == "false":
        return False
    if _HEX_RE.match(raw):
        return int(raw, 16)
    if _INT_RE.match(raw):
        return int(raw)
    if _FLOAT_RE.match(raw):
        return float(raw)
    # Fall back to raw identifier (links between units, enum-like values, etc.)
    return raw


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> list[SiiUnit]:
        self._consume_ident_value("SiiNunit", "Expected 'SiiNunit' header")
        self._consume("LBRACE", "Expected '{' after SiiNunit")

        units: list[SiiUnit] = []
        while not self._match("RBRACE"):
            units.append(self._parse_unit())
        return units

    def _parse_unit(self) -> SiiUnit:
        unit_class = self._consume("IDENT", "Expected unit class name").value
        self._consume("COLON", f"Expected ':' after unit class '{unit_class}'")
        unit_name = self._consume("IDENT", "Expected unit name").value
        self._consume("LBRACE", f"Expected '{{' after unit name '{unit_name}'")

        properties: dict[str, Any] = {}
        # Indexed arrays may arrive out of order; collect them separately and
        # merge once the unit closes so we can sort by index.
        indexed: dict[str, dict[int, Any]] = {}
        for_append: dict[str, list[Any]] = {}

        while not self._match("RBRACE"):
            key, index, value = self._parse_property()
            if index == "append":
                for_append.setdefault(key, []).append(value)
            elif isinstance(index, int):
                indexed.setdefault(key, {})[index] = value
            else:
                properties[key] = value

        for key, items in for_append.items():
            properties[key] = items
        for key, by_index in indexed.items():
            ordered = [by_index[i] for i in sorted(by_index)]
            # Indexed arrays override a same-named scalar (e.g. the count
            # property "active_mods: 5" precedes the indexed entries).
            properties[key] = ordered

        return SiiUnit(unit_class=unit_class, unit_name=unit_name, properties=properties)

    def _parse_property(self) -> tuple[str, int | str | None, Any]:
        key_token = self._consume("IDENT", "Expected property name")
        key = key_token.value
        index: int | str | None = None
        if self._peek_is("LBRACK"):
            self._advance()
            if self._peek_is("RBRACK"):
                self._advance()
                index = "append"
            else:
                idx_token = self._consume("IDENT", "Expected index inside '[]'")
                try:
                    index = int(idx_token.value)
                except ValueError as exc:
                    raise SiiParseError(
                        f"Array index must be an integer (got '{idx_token.value}' "
                        f"at line {idx_token.line})"
                    ) from exc
                self._consume("RBRACK", "Expected ']' after index")
        self._consume("COLON", f"Expected ':' after property '{key}'")
        value_token = self._consume_any(("IDENT", "STRING"), "Expected property value")
        return key, index, _coerce_value(value_token)

    def _consume(self, kind: str, message: str) -> _Token:
        if self._pos >= len(self._tokens):
            raise SiiParseError(f"{message} (reached end of input)")
        token = self._tokens[self._pos]
        if token.kind != kind:
            raise SiiParseError(f"{message} (got '{token.value}' at line {token.line})")
        self._pos += 1
        return token

    def _consume_any(self, kinds: tuple[str, ...], message: str) -> _Token:
        if self._pos >= len(self._tokens):
            raise SiiParseError(f"{message} (reached end of input)")
        token = self._tokens[self._pos]
        if token.kind not in kinds:
            raise SiiParseError(f"{message} (got '{token.value}' at line {token.line})")
        self._pos += 1
        return token

    def _consume_ident_value(self, expected: str, message: str) -> _Token:
        token = self._consume("IDENT", message)
        if token.value != expected:
            raise SiiParseError(f"{message} (got '{token.value}' at line {token.line})")
        return token

    def _match(self, kind: str) -> bool:
        if self._peek_is(kind):
            self._advance()
            return True
        return False

    def _peek_is(self, kind: str) -> bool:
        return self._pos < len(self._tokens) and self._tokens[self._pos].kind == kind

    def _advance(self) -> None:
        self._pos += 1


def parse_sii(text: str) -> list[SiiUnit]:
    # SCS mod authors on Windows often save manifest.sii with a UTF-8 BOM.
    if text.startswith("﻿"):
        text = text[1:]
    tokens = _tokenize(text)
    return _Parser(tokens).parse()
