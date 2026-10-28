"""Reciprocal rank fusion and the light authority weights of the search (task 14,
data-model.md §7). Pure: the database and the embedding call stay at the edge."""

from collections import defaultdict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

RRF_K = 60

# A slight preference, not a filter (md. 15-16, md. 26): at most a few per cent of a score.
COURT_LEVEL_WEIGHT = {
    "aym": 1.10,
    "ibk": 1.08,
    "hgk_iddk": 1.06,
    "daire": 1.03,
    "bam_bim": 1.0,
    "ilk_derece": 0.97,
    "international": 1.0,
}
SOURCE_RANK_WEIGHT = {
    "official_primary": 1.05,
    "official_secondary": 1.02,
    "editorial": 1.0,
    "academic": 0.98,
}


def rrf(rankings: Sequence[Sequence[Hashable]], k: int = RRF_K) -> dict[Hashable, float]:
    """Score of every item that appears in any ranking (best first): the sum of 1 / (k + rank)
    over the rankings it is in."""
    scores: dict[Hashable, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] += 1.0 / (k + rank)
    return dict(scores)


def authority_weight(court_level: str | None, source_rank: str | None) -> float:
    return COURT_LEVEL_WEIGHT.get(court_level or "", 1.0) * SOURCE_RANK_WEIGHT.get(
        source_rank or "", 1.0
    )


@dataclass(frozen=True)
class Scored[K: Hashable]:
    chunk_id: str
    record: K
    score: float


def group_by_record[K: Hashable](scored: Sequence[Scored[K]]) -> list[tuple[K, float, list[str]]]:
    """Records best first, as (record, score, chunk ids best first): a record scores as its best
    chunk (data-model.md §8)."""
    chunks: dict[K, list[Scored[K]]] = defaultdict(list)
    for item in scored:
        chunks[item.record].append(item)
    grouped = [
        (record, items[0].score, [i.chunk_id for i in items])
        for record, items in (
            (r, sorted(items, key=lambda i: (-i.score, i.chunk_id))) for r, items in chunks.items()
        )
    ]
    grouped.sort(key=lambda g: -g[1])
    return grouped
