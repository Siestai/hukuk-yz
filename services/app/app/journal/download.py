"""The PDF of a decision page (task 20): what comes back is checked before anything is stored."""

from app.journal.client import Fetcher, FetchError

PDF_MAGIC = b"%PDF"


async def download_pdf(fetcher: Fetcher, url: str, max_bytes: int) -> bytes:
    """The body of `url` when it is a PDF within `max_bytes`. An HTML page or an error page that
    answers 200 is `not_a_pdf`; neither it nor an oversized body is stored."""
    content = (await fetcher.get(url)).content
    if len(content) > max_bytes:
        raise FetchError(url, "too_large")
    if not content.startswith(PDF_MAGIC):
        raise FetchError(url, "not_a_pdf")
    return content
