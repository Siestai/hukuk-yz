"""robots.txt handling (task 06 §8). A missing robots.txt is no rule, and no permission either."""

from urllib.robotparser import RobotFileParser

USER_AGENT_TOKEN = "hukuk-yz-verify"


class Robots:
    def __init__(self, rules: str | None) -> None:
        self._parser = RobotFileParser()
        self._parser.parse((rules or "").splitlines())

    def allows(self, url: str) -> bool:
        return self._parser.can_fetch(USER_AGENT_TOKEN, url)


def parse_robots(status: int, content_type: str, body: str) -> Robots:
    """Rules only from a 200 `text/plain` answer: the BİGM apps answer `/robots.txt` with a JSON
    error, nginx with a 404 page; neither carries rules."""
    if status == 200 and content_type.lower().startswith("text/plain"):
        return Robots(body)
    return Robots(None)
