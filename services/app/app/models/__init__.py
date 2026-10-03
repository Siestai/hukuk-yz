"""ORM models of the knowledge base (data owner: app). Importing registers all tables."""

from app.models.admin_act import AdminAct, AdminActVersion
from app.models.chunk import Chunk
from app.models.common import (
    Base,
    Extraction,
    IngestFile,
    IngestJob,
    Review,
    Source,
)
from app.models.decision import Decision, DecisionVerification
from app.models.misc import (
    CaArticleVersion,
    CalcMethod,
    CalcParameterVersion,
    CollectiveAgreement,
    Doctrine,
    Treaty,
    TreatyArticleVersion,
)
from app.models.statute import Statute, StatuteArticle, StatuteArticleVersion
from app.models.user import AppUser, LoginAttempt, UserSession

__all__ = [
    "AdminAct",
    "AdminActVersion",
    "AppUser",
    "Base",
    "CaArticleVersion",
    "CalcMethod",
    "CalcParameterVersion",
    "Chunk",
    "CollectiveAgreement",
    "Decision",
    "DecisionVerification",
    "Doctrine",
    "Extraction",
    "IngestFile",
    "IngestJob",
    "LoginAttempt",
    "Review",
    "Source",
    "Statute",
    "StatuteArticle",
    "StatuteArticleVersion",
    "Treaty",
    "TreatyArticleVersion",
    "UserSession",
]
