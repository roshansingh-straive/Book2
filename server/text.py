"""Text-only normalization; never sees images, answer keys or inventory."""
import re
import unicodedata
from difflib import SequenceMatcher

def normalize(text):
    text = unicodedata.normalize("NFKD", (text or "").casefold()).replace("&", " and ")
    out, prev = [], ""
    for ch in text:
        cat = unicodedata.category(ch)
        if cat == "Mn" and prev and ord(prev) < 0x250:
            continue
        if cat[0] in "LNM":
            out.append(ch)
            prev = ch
        else:
            out.append(" ")
            prev = ""
    return " ".join("".join(out).split())


def title_key(title):
    return re.sub(r"^(the|a|an) ", "", normalize(title))


_METADATA = re.compile(r"\s*:\s*(?:the autobiography|an autobiography|autobiography|a novel|a memoir|the memoir)\s*$", re.I)


def clean_title(title, author=None):
    """Remove only an explicitly read author affix and generic format labels.

    Original transcriptions remain in raw evidence. Distinctive subtitles,
    editions and volume numbers are never discarded by this cleanup.
    """
    title = _METADATA.sub("", title.strip())
    if not author or title_key(title) == title_key(author):
        return title
    # Match the author's actual words, allowing the punctuation used on spines.
    words = re.findall(r"[^\W_]+", author, re.UNICODE)
    if words:
        pattern = r"[\W_]*".join(re.escape(word) for word in words)
        title = re.sub(r"^\s*" + pattern + r"(?:[\W_]+)(?=\w)", "", title, flags=re.I).strip()
        title = re.sub(r"(?:[\W_]+)" + pattern + r"\s*$", "", title, flags=re.I).strip()
    return title


def author_aliases(author):
    if not normalize(author):
        return set()
    # Parentheses can contain a transliteration; with/and separates coauthors.
    parts = [author, *re.findall(r"\(([^)]+)\)", author)]
    primary = re.sub(r"\([^)]*\)", " ", author)
    parts.extend(re.split(r"\bwith\b|\band\b|&|;", primary, flags=re.I))
    return {normalize(part) for part in parts if normalize(part)}


def authors_compatible(read, catalogue):
    if not normalize(read) or not normalize(catalogue):
        return True
    for a in author_aliases(read):
        for b in author_aliases(catalogue):
            if a == b or SequenceMatcher(None, a, b).ratio() >= .70:
                return True
            # Preserve the existing surname/initial tolerance for visible names.
            if len(a.split()[-1]) > 2 and a.split()[-1] == b.split()[-1]:
                return True
    return False
