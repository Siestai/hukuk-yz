"""Künye strings of the topic templates: which knowledge base record each one names."""

import pytest

from agent.kunye import AdminActSection, StatuteArticle, admin_act_section, mapped, statute_article
from agent.topics import SourceRef, load_topics


def test_a_statute_kunye_names_the_statute_and_the_article() -> None:
    assert statute_article("4857 m.18") == StatuteArticle("4857", "18")
    assert statute_article("4857 m.18/A") == StatuteArticle("4857", "18/A")
    assert statute_article("5510 m.Geçici 4") == StatuteArticle("5510", "Geçici 4")
    assert statute_article("İş Kanunu 18") is None
    assert statute_article("4857") is None


def test_an_admin_act_kunye_names_the_act_and_its_section_if_any() -> None:
    assert admin_act_section("2020/8") == AdminActSection("2020/8", None)
    assert admin_act_section("2020/8 m.2.6.2.5") == AdminActSection("2020/8", "2.6.2.5")
    assert admin_act_section("İPC Genelgesi") is None
    assert admin_act_section("2020/8 bölüm iki") is None


@pytest.mark.parametrize(
    ("ref", "category", "expected"),
    [
        ("4857 m.18", "statute", True),
        ("4857 m.18/1", "statute", True),
        ("2020/8", "admin_act", True),
        ("2020/8 m.2.6.2.5", "admin_act", True),
        ("9. HD E.2016/28920 K.2017/17860", "decision", True),
        ("İş Kanunu'nun on sekizinci maddesi", "statute", False),
        ("2020/8", "statute", False),
        ("9. HD 2017 tarihli karar", "decision", False),
        ("SGK genelgesi", "admin_act", False),
        ("Süzek, İş Hukuku", "doctrine", False),
    ],
)
def test_a_kunye_maps_only_in_the_form_of_its_category(
    ref: str, category: str, expected: bool
) -> None:
    assert mapped(SourceRef.model_validate({"ref": ref, "category": category})) is expected


def test_every_kunye_of_the_templates_maps() -> None:
    refs = [
        ref
        for topic in load_topics().values()
        for ref in [
            *topic.must_read,
            *(b for f in topic.facts if f.question for b in f.question.basis),
        ]
    ]

    assert refs
    assert [r.ref for r in refs if not mapped(r)] == []
