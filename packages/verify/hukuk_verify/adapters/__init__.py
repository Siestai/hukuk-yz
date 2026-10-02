"""One adapter per official source (task 06 §3)."""

from hukuk_verify.adapters.aym import AymAdapter
from hukuk_verify.adapters.base import SourceAdapter
from hukuk_verify.adapters.danistay import DanistayAdapter
from hukuk_verify.adapters.uyap_emsal import UyapEmsalAdapter
from hukuk_verify.adapters.yargitay import YargitayAdapter

__all__ = ["AymAdapter", "DanistayAdapter", "SourceAdapter", "UyapEmsalAdapter", "YargitayAdapter"]
