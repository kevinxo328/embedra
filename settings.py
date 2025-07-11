import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LLM Provider Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")

PROJECT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
