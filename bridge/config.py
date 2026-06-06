import os
from dotenv import load_dotenv

load_dotenv()

MM_URL: str = os.getenv("MM_URL", "http://localhost:8065")
MM_BOT_TOKEN: str = os.environ["MM_BOT_TOKEN"]
MM_BOT_USER_ID: str = os.environ["MM_BOT_USER_ID"]
MM_DEMO_CHANNEL_ID: str = os.environ["MM_DEMO_CHANNEL_ID"]
GRAPHN_GATEWAY_URL: str = os.environ["GRAPHN_GATEWAY_URL"]
GRAPHN_API_KEY: str = os.environ["GRAPHN_API_KEY"]
GRAPHN_WORKSPACE_ID: str = os.environ["GRAPHN_WORKSPACE_ID"]
GRAPHN_WF_PUBLIC: str = os.environ["GRAPHN_WF_PUBLIC"]
GRAPHN_WF_PRIVATE: str = os.environ["GRAPHN_WF_PRIVATE"]
CONF_MIN: float = float(os.getenv("CONF_MIN", "0.65"))
BRIDGE_HOST: str = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT: int = int(os.getenv("BRIDGE_PORT", "8080"))
BRIDGE_BASE_URL: str = os.getenv("BRIDGE_BASE_URL", "http://localhost:8080")
BRIDGE_STATE_DIR: str = os.getenv("BRIDGE_STATE_DIR", "bridge/state")
GRAPHN_URL: str = os.getenv("GRAPHN_URL", "https://cp.graphn.ai")
GRAPHN_KB_PUBLIC: str = os.getenv("GRAPHN_KB_PUBLIC", "")
GRAPHN_KB_PRIVATE: str = os.getenv("GRAPHN_KB_PRIVATE", "")
