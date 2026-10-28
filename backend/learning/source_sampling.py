"""Small, varied source selections that retain verifiable page quotations."""
import random
import re
from collections import Counter

from .bank_sources import page_sources


def assessment_source(text, *, count=5, used_pages=(), seed=None, budget=5500):
    """Spread a batch across the document, preferring pages not assessed yet.

    Content length and learning-objective headings are only sampling hints; the
    examiner still decides what the excerpts support. Never fabricate citations.
    """
    pages = page_sources(text) or {1: text.strip()}
    pages = [(number, body) for number, body in pages.items() if len(body.strip()) >= 20]
    if not pages or count <= 0:
        return ''
    rng = random.Random(seed)
    coverage = Counter(used_pages)
    substantive = [(number, body) for number, body in pages
                   if len(body.split()) >= 25 and not re.match(
                       r'^\s*(references|bibliography|thank you)\b', body, re.I)]
    pool = substantive or pages
    least_used = min(coverage[number] for number, _ in pool)
    # Fill from the least represented pages before revisiting covered material.
    fresh = [(number, body) for number, body in pool if coverage[number] == least_used]
    if len(fresh) >= min(count, len(pool)):
        pool = fresh
    pool = sorted(pool)
    size = min(count, 5, len(pool))
    selected = []
    for index in range(size):
        section = pool[index * len(pool) // size:(index + 1) * len(pool) // size]
        min_coverage = min(coverage[number] for number, _ in section)
        section = [(number, body) for number, body in section if coverage[number] == min_coverage]
        weights = [1 + min(len(body.split()), 400) / 200 + bool(re.search(
            r'learning objectives?|key (?:points|concepts)|clinical|summary|function|mechanism', body, re.I))
            for _, body in section]
        selected.append(rng.choices(section, weights=weights, k=1)[0])
    allowance = max(1, (budget - sum(len(f'[Page {number}]\n') + 2 for number, _ in selected)) // size)
    excerpts = []
    for number, body in selected:
        # Vary long-page passages too; slicing preserves exact source evidence.
        start = rng.randrange(max(1, len(body) - allowance + 1)) if len(body) > allowance else 0
        excerpts.append(f'[Page {number}]\n{body[start:start + allowance]}')
    return '\n\n'.join(excerpts)
