"""Failures of a lookup. None of them means "not in the source": a decision is `not_in_source`
only when a valid query came back without a matching row."""


class VerifyError(Exception):
    pass


class RecordError(VerifyError):
    """This lookup failed; the decision stays `unverified` and is retried on a later run."""


class SourceUnavailable(RecordError):
    """Network error, timeout or a 5xx / non-JSON answer."""


class UnexpectedResponse(RecordError):
    """The site answered, but with an error envelope (`metadata.FMTY == "ERROR"`), an HTTP status
    other than 200 / 429 / 5xx (404, say) or a shape the adapter does not know."""


class SourceStopped(VerifyError):
    """No more requests go to this source in this run."""


class RateLimitExhausted(SourceStopped):
    """Three consecutive 429 answers."""


class SourceUnreachable(SourceStopped):
    """Three consecutive network errors or timeouts: the source is treated as down."""


class CaptchaRequired(SourceStopped):
    """The site asks for a captcha; it is never solved or bypassed (task 06 §8)."""


class RobotsDisallowed(SourceStopped):
    pass


class RequestBudgetExceeded(SourceStopped):
    pass
