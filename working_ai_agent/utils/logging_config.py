import logging
from pathlib import Path
from config import LOG_LEVEL

def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler("logs/agent.log", encoding="utf-8"),
            logging.StreamHandler()
        ],
        force=True
    )
