import os

# Pydantic AI prints a banner when an agent is made; a service log has no use for it.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
