import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LLM Provider Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")

#  App Configuration
ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "development")
if APP_ENVIRONMENT not in ALLOWED_ENVIRONMENTS:
    raise ValueError(
        f"APP_ENVIROMENT must be one of {ALLOWED_ENVIRONMENTS}, got '{APP_ENVIRONMENT}'"
    )

PROJECT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
