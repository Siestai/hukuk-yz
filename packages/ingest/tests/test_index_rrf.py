"""Rank fusion and the authority weights of the search (task 14); no database."""

from hukuk_ingest.index.rrf import Scored, authority_weight, group_by_record, rrf


def test_rrf_sums_the_reciprocal_ranks() -> None:
    scores = rrf([["a", "b", "c"], ["b", "a"]], k=60)
    assert scores["a"] == 1 / 61 + 1 / 62
    assert scores["b"] == 1 / 62 + 1 / 61
    assert scores["c"] == 1 / 63
    assert rrf([]) == {}


def test_an_item_in_both_lists_beats_one_in_a_single_list() -> None:
    scores = rrf([["x", "both"], ["both", "y"]])
    assert max(scores, key=lambda i: scores[i]) == "both"


def test_authority_weights_are_light_and_default_to_neutral() -> None:
    assert authority_weight("aym", "official_primary") > authority_weight("daire", "editorial")
    assert authority_weight("daire", "editorial") > authority_weight("ilk_derece", "academic")
    assert authority_weight(None, None) == 1.0
    assert authority_weight("unknown", "unknown") == 1.0
    assert authority_weight("aym", "official_primary") < 1.25  # a nudge, not a filter


def test_records_score_as_their_best_chunk_and_list_chunks_best_first() -> None:
    grouped = group_by_record(
        [
            Scored("c1", "rec-a", 0.020),
            Scored("c2", "rec-b", 0.030),
            Scored("c3", "rec-a", 0.025),
            Scored("c4", "rec-a", 0.010),
        ]
    )
    assert [(record, score) for record, score, _ in grouped] == [("rec-b", 0.030), ("rec-a", 0.025)]
    assert grouped[1][2] == ["c3", "c1", "c4"]
