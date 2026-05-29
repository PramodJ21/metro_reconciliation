import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Metro Ticket Booking Reconciliation API"
    
    # Read database connection parameters individually
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "metro_reconciliation")
    
    # Programmatically build the connection string
    @property
    def DATABASE_URL(self) -> str:
        # Handle passwordless postgres case cleanly
        if self.DB_PASSWORD:
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            return f"postgresql://{self.DB_USER}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    # Temporary folder inside the workspace to save uploaded files during processing
    UPLOAD_TEMP_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "temp_uploads"
    )

settings = Settings()

# Ensure the temp uploads directory exists
os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)
