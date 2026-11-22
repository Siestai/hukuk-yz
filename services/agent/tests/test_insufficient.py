"""The "kaynak yetersiz" content (task 19, B4): the topic, the must-read sources that were not
read, what the user told and the next step; nothing made up."""

from agent.insufficient import source_gap
from agent.topics import get_topic
from hukuk_models.chat import CaseFacts, Fact
from hukuk_models.formal_turkish import progressive_forms

TOPIC = get_topic("ise_iade")
FACTS = CaseFacts(
    title="İşe iade",
    facts=[
        Fact(key="kidem", label="Kıdem: 5 ay", value="5 ay", status="known"),
        Fact(key="isci_sayisi", label="İşyerindeki işçi sayısı", status="unknown"),
        Fact(key="yer_alti", label="Yer altı işi değil", value="hayır", status="assumed_never"),
    ],
)


def test_the_gap_names_the_topic_the_unread_sources_and_the_given_facts() -> None:
    gap = source_gap(
        TOPIC,
        FACTS,
        [
            {"ref": "4857 m.18", "reason": "not_found"},
            {"ref": "4857 m.18", "reason": "truncated"},
            {"ref": "2020/8 m.2.6.2.5", "reason": "gap"},
        ],
    )

    assert gap.topic == TOPIC.title
    # One line per künye, with the first reason it was not read for.
    assert [(m.ref, m.reason) for m in gap.missing_sources] == [
        ("4857 m.18", "not_found"),
        ("2020/8 m.2.6.2.5", "gap"),
    ]
    # What the user said, never what is still unknown.
    assert [f.key for f in gap.given_facts] == ["kidem", "yer_alti"]
    assert gap.next_step == (
        "Bu soru, şu kaynaklar bilgi tabanına eklendiğinde cevaplanabilir: "
        "4857 m.18, 2020/8 m.2.6.2.5."
    )
    assert not progressive_forms([gap.next_step])


def test_with_every_source_read_the_next_step_names_no_source() -> None:
    gap = source_gap(TOPIC, FACTS, [])

    assert gap.missing_sources == []
    assert "m." not in gap.next_step
    assert "elle incelenmesi" in gap.next_step
    assert not progressive_forms([gap.next_step])
