from agent.api import create_app
from agent.settings import get_settings

app = create_app(get_settings())
