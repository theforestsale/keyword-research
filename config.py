import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "keyword_research.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "")

    if AI_PROVIDER == "groq":
        AI_API_KEY = os.environ.get(
            "GROQ_API_KEY",
            os.environ.get("OPENAI_API_KEY", ""),
        )
        if not AI_BASE_URL:
            AI_BASE_URL = "https://api.groq.com/openai/v1"
        if AI_MODEL == "gpt-4o-mini":
            AI_MODEL = "llama-3.3-70b-versatile"
    else:
        AI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    MAX_KEYWORDS = int(os.environ.get("MAX_KEYWORDS", "20"))
    MAX_SEED_LENGTH = 100
    REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "30"))
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
