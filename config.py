import os

class Config:
    """
    Application configuration variables.
    Utilizes environment variables with safe development fallbacks.
    """
    # Secret key for session management and cryptographic operations
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-secret-key-do-not-use-in-prod')
    
    # Database Configuration - defaults to SQLite in the database/ directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'database', 'ocean_freight.db')
    
    # Ensure database directory exists to prevent I/O errors during initialization
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{DB_PATH}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False