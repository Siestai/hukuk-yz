from hukuk_verify.robots import parse_robots

URL = "https://emsal.uyap.gov.tr/aramadetaylist"


def test_a_disallow_rule_is_applied() -> None:
    robots = parse_robots(200, "text/plain", "User-agent: *\nDisallow: /aramadetaylist\n")
    assert not robots.allows(URL)
    assert robots.allows("https://emsal.uyap.gov.tr/getDokuman?id=1")


def test_a_rule_for_our_agent_is_applied() -> None:
    robots = parse_robots(200, "text/plain", "User-agent: hukuk-yz-verify\nDisallow: /\n")
    assert not robots.allows(URL)


def test_an_empty_disallow_allows_everything() -> None:
    assert parse_robots(200, "text/plain", "User-agent: *\nDisallow:\n").allows(URL)


def test_json_error_and_404_carry_no_rules() -> None:
    assert parse_robots(200, "application/json", '{"error": "No static resource"}').allows(URL)
    assert parse_robots(404, "text/html", "Disallow: /").allows(URL)
