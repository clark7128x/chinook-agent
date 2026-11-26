from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_START = re.compile(r"[A-Za-z_\u0080-\uffff]")
_WORD = re.compile(r"[A-Za-z0-9_$\u0080-\uffff]+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_READ_STARTS = {"SELECT", "WITH"}
# Ключові слова, якими може починатися основний запит після визначень CTE.
_MAIN_STATEMENTS = {"SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE", "VALUES"}


class SqlRejected(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    depth: int
    start: int
    end: int


def tokenize(sql: str) -> list[Token]:
    """Розбирає SQL на токени, пропускаючи коментарі й вміст лапок."""
    tokens: list[Token] = []
    depth = 0
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index)
            index = length if newline < 0 else newline + 1
            continue
        if sql.startswith("/*", index):
            closing = sql.find("*/", index + 2)
            if closing < 0:
                raise SqlRejected("незакритий коментар /* */")
            index = closing + 2
            continue
        if char in "'\"`[":
            closing_char = "]" if char == "[" else char
            position = index + 1
            while position < length:
                if sql[position] == closing_char:
                    if closing_char != "]" and position + 1 < length and sql[position + 1] == closing_char:
                        position += 2
                        continue
                    break
                position += 1
            if position >= length:
                raise SqlRejected("незакриті лапки в запиті")
            kind = "string" if char == "'" else "ident"
            tokens.append(Token(kind, sql[index : position + 1], depth, index, position + 1))
            index = position + 1
            continue
        if char == "(":
            tokens.append(Token("punct", char, depth, index, index + 1))
            depth += 1
            index += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            tokens.append(Token("punct", char, depth, index, index + 1))
            index += 1
            continue
        if char == ";":
            tokens.append(Token("semi", char, depth, index, index + 1))
            index += 1
            continue
        if char.isdigit():
            match = _NUMBER.match(sql, index)
            tokens.append(Token("number", match.group(), depth, index, match.end()))
            index = match.end()
            continue
        if _WORD_START.match(char):
            match = _WORD.match(sql, index)
            tokens.append(Token("word", match.group(), depth, index, match.end()))
            index = match.end()
            continue
        tokens.append(Token("punct", char, depth, index, index + 1))
        index += 1

    return tokens


def check_select(sql: str) -> list[Token]:
    if not isinstance(sql, str) or not sql.strip():
        raise SqlRejected("порожній запит")
    tokens = tokenize(sql)
    if not tokens:
        raise SqlRejected("запит не містить SQL")

    semicolons = [token for token in tokens if token.kind == "semi"]
    if semicolons and (len(semicolons) > 1 or semicolons[0] is not tokens[-1]):
        raise SqlRejected("дозволено один запит; кілька запитів через ';' відхилено")

    first = tokens[0]
    if first.kind != "word" or first.value.upper() not in _READ_STARTS:
        raise SqlRejected("дозволено лише SELECT")
    if first.value.upper() == "WITH":
        # Основний запит після CTE стоїть на верхньому рівні дужок.
        main = next(
            (
                token
                for token in tokens
                if token.kind == "word" and token.depth == 0
                and token.value.upper() in _MAIN_STATEMENTS
            ),
            None,
        )
        if main is None or main.value.upper() != "SELECT":
            raise SqlRejected("після WITH дозволено лише SELECT")
    return tokens


def ensure_limit(sql: str, max_rows: int) -> tuple[str, bool]:
    tokens = check_select(sql)
    body = sql[: tokens[-1].start] if tokens[-1].kind == "semi" else sql
    body = body.rstrip()
    has_limit = any(
        token.kind == "word" and token.value.upper() == "LIMIT" and token.depth == 0
        for token in tokens
    )
    if has_limit:
        return body, False
    return f"{body}\nLIMIT {max_rows}", True
