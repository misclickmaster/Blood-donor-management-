import os

# ==========================================
# LifeStream Configuration Settings
# ==========================================

# Database Type: 'mysql' (Default) or 'sqlite'
DB_TYPE = os.environ.get('DB_TYPE', 'mysql')

# MySQL Server Configuration (Standard XAMPP / WAMP / MySQL 8.0 defaults)
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')  # Default in XAMPP is empty
MYSQL_DB = os.environ.get('MYSQL_DB', 'blood_bank_db')

# SQLite Fallback Configuration (if MySQL server is stopped)
SQLITE_DB_NAME = 'blood_bank.db'

# Flask Secret Key
SECRET_KEY = os.environ.get('SECRET_KEY', 'lifestream_cse_mini_project_key_2026')
