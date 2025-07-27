import os

from env import env
from utils.logger import initialize_logger
from utils.request_context import RequestContext

# Initialize request context for logging
request_context = RequestContext()
logger = initialize_logger(
    context=request_context,
    level="INFO" if env.APP_ENVIRONMENT != "production" else "WARNING",
    enable_file_logging=env.APP_ENVIRONMENT == "local",
)
# Set up project root directory.
PROJECT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

logger.warning(f"Application environment: {env.APP_ENVIRONMENT}")
logger.warning(f"Project root directory: {PROJECT_ROOT_DIR}")
