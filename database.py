import os
import sqlite3
import pymysql
import pymysql.cursors
from datetime import datetime, date
from werkzeug.security import generate_password_hash
import config

DB_PATH = os.path.join(os.path.dirname(__file__), config.SQLITE_DB_NAME)

# Compatibility charts
COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM = {
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'A-': ['A-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],  # Universal recipient
    'AB-': ['AB-', 'A-', 'B-', 'O-'],
    'O+': ['O+', 'O-'],
    'O-': ['O-']  # Universal donor gives to all, only receives O-
}

COMPATIBILITY_DONOR_CAN_GIVE_TO = {
    'A+': ['A+', 'AB+'],
    'A-': ['A+', 'A-', 'AB+', 'AB-'],
    'B+': ['B+', 'AB+'],
    'B-': ['B+', 'B-', 'AB+', 'AB-'],
    'AB+': ['AB+'],
    'AB-': ['AB+', 'AB-'],
    'O+': ['A+', 'B+', 'AB+', 'O+'],
    'O-': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']  # Universal donor
}

CURRENT_DB_ENGINE = None

class DBWrapper:
    """
    Unified database interface for both MySQL and SQLite.
    Provides identical cursor behavior (dict/named access) and query execution.
    """
    def __init__(self, engine_type, connection):
        self.engine_type = engine_type  # 'mysql' or 'sqlite'
        self.connection = connection

    def cursor(self):
        return self.connection.cursor()

    def execute(self, query, params=None):
        if params is None:
            params = []
        
        cur = self.connection.cursor()
        if self.engine_type == 'mysql':
            # In MySQL, replace '?' with '%s'
            mysql_query = query.replace('?', '%s')
            cur.execute(mysql_query, tuple(params))
        else:
            cur.execute(query, tuple(params))
        return cur

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def get_mysql_connection():
    """Attempt connection to MySQL server using settings from config.py"""
    try:
        # First ensure database exists
        init_conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        with init_conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DB}` CHARACTER SET utf8mb4;")
        init_conn.commit()
        init_conn.close()

        # Connect to specific database
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        return conn
    except Exception as e:
        return None


def get_sqlite_connection():
    """Fallback connection to SQLite file database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """
    Factory function returning a unified DBWrapper.
    Prefers MySQL if enabled & reachable; falls back to SQLite smoothly.
    """
    global CURRENT_DB_ENGINE
    
    if config.DB_TYPE.lower() == 'mysql':
        mysql_conn = get_mysql_connection()
        if mysql_conn:
            CURRENT_DB_ENGINE = 'mysql'
            return DBWrapper('mysql', mysql_conn)
        else:
            CURRENT_DB_ENGINE = 'sqlite'
            return DBWrapper('sqlite', get_sqlite_connection())
    else:
        CURRENT_DB_ENGINE = 'sqlite'
        return DBWrapper('sqlite', get_sqlite_connection())


def init_db():
    """Initialize schema on active database engine."""
    db = get_db()
    
    if db.engine_type == 'mysql':
        # Create MySQL tables
        db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            role ENUM('donor', 'requester', 'admin') NOT NULL DEFAULT 'donor',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')

        db.execute('''
        CREATE TABLE IF NOT EXISTS donors (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            blood_group VARCHAR(5) NOT NULL,
            age INT NOT NULL,
            gender VARCHAR(10) NOT NULL,
            weight_kg DECIMAL(5,2),
            city VARCHAR(100) NOT NULL,
            state VARCHAR(100) NOT NULL,
            pincode VARCHAR(10),
            address TEXT,
            last_donation_date DATE NULL,
            is_available TINYINT(1) NOT NULL DEFAULT 1,
            is_verified TINYINT(1) NOT NULL DEFAULT 1,
            total_donations INT DEFAULT 0,
            medical_notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')

        db.execute('''
        CREATE TABLE IF NOT EXISTS blood_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            requester_id INT NULL,
            patient_name VARCHAR(100) NOT NULL,
            blood_group VARCHAR(5) NOT NULL,
            units_needed INT NOT NULL DEFAULT 1,
            hospital_name VARCHAR(150) NOT NULL,
            hospital_address TEXT,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(100) NOT NULL,
            contact_person VARCHAR(100) NOT NULL,
            contact_phone VARCHAR(20) NOT NULL,
            urgency_level ENUM('Normal', 'Urgent', 'Critical') NOT NULL DEFAULT 'Urgent',
            reason TEXT,
            status ENUM('Pending', 'Fulfilled', 'Cancelled') NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')

        db.execute('''
        CREATE TABLE IF NOT EXISTS donation_responses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            request_id INT NOT NULL,
            donor_id INT NOT NULL,
            message TEXT,
            status VARCHAR(20) DEFAULT 'Accepted',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
            FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        db.commit()
        db.close()
    else:
        # Create SQLite tables
        db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'donor',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        db.execute('''
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            blood_group TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            weight_kg REAL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            pincode TEXT,
            address TEXT,
            last_donation_date DATE,
            is_available INTEGER NOT NULL DEFAULT 1,
            is_verified INTEGER NOT NULL DEFAULT 1,
            total_donations INTEGER DEFAULT 0,
            medical_notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        ''')

        db.execute('''
        CREATE TABLE IF NOT EXISTS blood_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER,
            patient_name TEXT NOT NULL,
            blood_group TEXT NOT NULL,
            units_needed INTEGER NOT NULL DEFAULT 1,
            hospital_name TEXT NOT NULL,
            hospital_address TEXT,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            contact_person TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            urgency_level TEXT NOT NULL DEFAULT 'Urgent',
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE SET NULL
        )
        ''')

        db.execute('''
        CREATE TABLE IF NOT EXISTS donation_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            donor_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Accepted',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
            FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE
        )
        ''')
        db.commit()
        db.close()


def seed_sample_data():
    """Populate initial admin, voluntary donors, and emergency requests."""
    db = get_db()
    
    # Check if admin already exists
    cur = db.execute("SELECT id FROM users WHERE email = ?", ('admin@bloodfinder.com',))
    existing = cur.fetchone()
    if existing:
        db.close()
        return

    admin_pwd = generate_password_hash('admin123')
    db.execute('''
    INSERT INTO users (name, email, password_hash, phone, role)
    VALUES (?, ?, ?, ?, ?)
    ''', ('System Administrator', 'admin@bloodfinder.com', admin_pwd, '+91 9876543210', 'admin'))

    # Sample Donors
    sample_donors = [
        ('Aarav Sharma', 'aarav.sharma@example.com', '9811122233', 'O+', 24, 'Male', 68.5, 'New Delhi', 'Delhi', '110001', 'Connaught Place', '2024-08-15', 1, 3),
        ('Priya Patel', 'priya.patel@example.com', '9822233344', 'A+', 22, 'Female', 55.0, 'Mumbai', 'Maharashtra', '400001', 'Andheri West', '2024-09-01', 1, 2),
        ('Rahul Verma', 'rahul.verma@example.com', '9833344455', 'B+', 28, 'Male', 74.0, 'Bengaluru', 'Karnataka', '560001', 'Indiranagar', '2024-07-20', 1, 5),
        ('Ananya Iyer', 'ananya.iyer@example.com', '9844455566', 'AB+', 26, 'Female', 58.0, 'Chennai', 'Tamil Nadu', '600001', 'T. Nagar', '2024-05-10', 1, 1),
        ('Vikram Malhotra', 'vikram.m@example.com', '9855566677', 'O-', 31, 'Male', 80.0, 'Hyderabad', 'Telangana', '500001', 'Banjara Hills', '2024-06-18', 1, 6),
        ('Sneha Kulkarni', 'sneha.k@example.com', '9866677788', 'A-', 23, 'Female', 52.0, 'Pune', 'Maharashtra', '411001', 'Kothrud', '2024-09-12', 1, 2),
        ('Rohan Das', 'rohan.das@example.com', '9877788899', 'B-', 29, 'Male', 70.0, 'Kolkata', 'West Bengal', '700001', 'Salt Lake City', '2024-04-22', 1, 4),
        ('Neha Gupta', 'neha.gupta@example.com', '9888899900', 'AB-', 27, 'Female', 60.0, 'Jaipur', 'Rajasthan', '302001', 'Malviya Nagar', '2024-08-30', 0, 1),
        ('Amitabh Singh', 'amitabh.s@example.com', '9899900011', 'O+', 35, 'Male', 76.0, 'Lucknow', 'Uttar Pradesh', '226001', 'Hazratganj', '2024-02-14', 1, 8),
        ('Deepika Nair', 'deepika.n@example.com', '9800011122', 'O-', 25, 'Female', 54.0, 'Kochi', 'Kerala', '682001', 'MG Road', '2024-09-15', 1, 3),
        ('Karan Mehta', 'karan.mehta@example.com', '9812345678', 'A+', 30, 'Male', 72.0, 'Chandigarh', 'Punjab', '160001', 'Sector 17', '2024-08-01', 1, 4),
        ('Tanvi Joshi', 'tanvi.joshi@example.com', '9823456789', 'B+', 21, 'Female', 51.0, 'Ahmedabad', 'Gujarat', '380001', 'Navrangpura', '2024-09-25', 1, 1),
    ]

    donor_pwd = generate_password_hash('donor123')

    for d in sample_donors:
        cur = db.execute('''
        INSERT INTO users (name, email, password_hash, phone, role)
        VALUES (?, ?, ?, ?, 'donor')
        ''', (d[0], d[1], donor_pwd, d[2]))
        
        user_id = cur.lastrowid

        db.execute('''
        INSERT INTO donors (user_id, blood_group, age, gender, weight_kg, city, state, pincode, address, last_donation_date, is_available, is_verified, total_donations)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12], 1, d[13]))

    # Sample Blood Requests
    sample_requests = [
        ('Ramesh Chandra', 'O-', 2, 'AIIMS Hospital', 'Ansari Nagar', 'New Delhi', 'Delhi', 'Dr. Alok Verma', '9811122299', 'Critical', 'Emergency open-heart surgery required urgently.', 'Pending'),
        ('Sunita Sen', 'B+', 3, 'Lilavati Hospital', 'Bandra West', 'Mumbai', 'Maharashtra', 'Dr. Maya Roy', '9822233388', 'Urgent', 'Severe Dengue with critically low platelet counts.', 'Pending'),
        ('Baby Aarohi (Age 4)', 'A+', 1, 'Rainbow Children Hospital', 'Marathahalli', 'Bengaluru', 'Karnataka', 'Dr. Srinivas', '9833344477', 'Critical', 'Pediatric Thalassemia major monthly transfusion.', 'Pending'),
        ('Mohammad Farooq', 'AB-', 2, 'Apollo Health City', 'Jubilee Hills', 'Hyderabad', 'Telangana', 'Tariq Farooq', '9855566600', 'Urgent', 'Emergency road accident multiple fractures trauma.', 'Pending'),
        ('Meenakshi Sundaram', 'O+', 1, 'Fortis Hospital', 'Mulund', 'Mumbai', 'Maharashtra', 'K. Sundaram', '9866677711', 'Normal', 'Planned orthopedic hip replacement surgery.', 'Fulfilled')
    ]

    for req in sample_requests:
        db.execute('''
        INSERT INTO blood_requests (patient_name, blood_group, units_needed, hospital_name, hospital_address, city, state, contact_person, contact_phone, urgency_level, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', req)

    db.commit()
    db.close()


if __name__ == '__main__':
    init_db()
    seed_sample_data()
    engine_name = "MySQL" if CURRENT_DB_ENGINE == 'mysql' else "SQLite (Fallback/Local)"
    print(f"Database initialized and seeded successfully using: {engine_name}")
