import os

from dotenv import load_dotenv

from utils.vector_store import PostgresVectorStore

# Load environment variables from .env file
load_dotenv()

# LLM and Embedding Provider Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not GOOGLE_API_KEY and not AZURE_OPENAI_API_KEY and not OPENAI_API_KEY:
    raise ValueError(
        "At least one of GOOGLE_API_KEY, AZURE_OPENAI_API_KEY, or OPENAI_API_KEY must be set in the environment variables"
    )

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in the environment variables")


#  App Configuration
ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "development")
if APP_ENVIRONMENT not in ALLOWED_ENVIRONMENTS:
    raise ValueError(
        f"APP_ENVIROMENT must be one of {ALLOWED_ENVIRONMENTS}, got '{APP_ENVIRONMENT}'"
    )

PROJECT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

VectorStore = PostgresVectorStore()
