import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_IMAGE_MODEL = os.getenv("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-2-klein-9b")
CLOUDFLARE_IMAGE_TIMEOUT = int(os.getenv("CLOUDFLARE_IMAGE_TIMEOUT", "300"))
IMAGE_LIMIT = int(os.getenv("IMAGE_LIMIT", "25"))
COMPETITOR_LIMIT = int(os.getenv("COMPETITOR_LIMIT", "25"))
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "3"))
ENABLE_COMPETITOR_RESEARCH = os.getenv("ENABLE_COMPETITOR_RESEARCH", "false").lower() == "true"
ENABLE_IMAGE_GENERATION = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
