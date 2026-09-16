import re

def _tokenize(a: str) -> list[str]:
    return re.findall(r"\w+", (a or "").casefold(), flags=re.UNICODE)

def match_exact(a, b) -> bool:
    return a is None or a == b

def match_eq(a: str, b: str) -> bool:
    return a is None or a.casefold() == (b or "").casefold()

def match_in(a: str, b: list[str]) -> bool:
    return any(match_eq(a, x) for x in (b or []))

def match_fuzzy(a: str, b: str) -> bool:
    search_tokens = _tokenize(a)
    value_tokens = _tokenize(b)

    if not search_tokens:
        return True

    return all(
        any(value_token.startswith(search_token) for value_token in value_tokens)
        for search_token in search_tokens
    )

def build_query(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).strip()

