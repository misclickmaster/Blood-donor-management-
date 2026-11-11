"""
MySQL Database Setup Utility for LifeStream Blood Donor Finder
Course: CSE 2nd Year Mini Project
"""

import sys
import pymysql
import config
from werkzeug.security import generate_password_hash

def setup_mysql():
    print("=" * 60)
    print(" LifeStream MySQL Database Setup & Seeder")
    print("=" * 60)
    print(f"Target Host    : {config.MYSQL_HOST}:{config.MYSQL_PORT}")
    print(f"Target User    : {config.MYSQL_USER}")
    print(f"Target Database: {config.MYSQL_DB}")
    print("-" * 60)

    try:
        # Step 1: Connect to MySQL Server (without selecting database yet)
        print("1. Connecting to MySQL Server...")
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        print("   [SUCCESS] Connected to MySQL Server successfully!")

        cursor = conn.cursor()

        # Step 2: Create Database if not exists
        print(f"2. Creating Database `{config.MYSQL_DB}` if not exists...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print("   [SUCCESS] Database ready!")

        cursor.execute(f"USE `{config.MYSQL_DB}`;")

        # Step 3: Create Tables
        print("3. Creating tables: users, donors, blood_requests, donation_responses...")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            role ENUM('donor', 'requester', 'admin') NOT NULL DEFAULT 'donor',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
        """)

        cursor.execute("""
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
        """)
        print("   [SUCCESS] Tables created successfully!")

        # Step 4: Seed Initial Records
        print("4. Checking and seeding initial sample data...")
        cursor.execute("SELECT id FROM users WHERE email = %s", ('admin@bloodfinder.com',))
        if cursor.fetchone():
            print("   [INFO] Admin user already exists. Seeding skipped.")
        else:
            admin_pwd = generate_password_hash('admin123')
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, phone, role)
                VALUES (%s, %s, %s, %s, 'admin')
            """, ('System Administrator', 'admin@bloodfinder.com', admin_pwd, '+91 9876543210'))

            sample_donors = [
                ('Aarav Sharma', 'aarav.sharma@example.com', '9811122233', 'O+', 24, 'Male', 68.5, 'New Delhi', 'Delhi', '110001', 'Connaught Place', '2024-08-15', 1, 3),
                ('Priya Patel', 'priya.patel@example.com', '9822233344', 'A+', 22, 'Female', 55.0, 'Mumbai', 'Maharashtra', '400001', 'Andheri West', '2024-09-01', 1, 2),
                ('Rahul Verma', 'rahul.verma@example.com', '9833344455', 'B+', 28, 'Male', 74.0, 'Bengaluru', 'Karnataka', '560001', 'Indiranagar', '2024-07-20', 1, 5),
                ('Ananya Iyer', 'ananya.iyer@example.com', '9844455566', 'AB+', 26, 'Female', 58.0, 'Chennai', 'Tamil Nadu', '600001', 'T. Nagar', '2024-05-10', 1, 1),
                ('Vikram Malhotra', 'vikram.m@example.com', '9855566677', 'O-', 31, 'Male', 80.0, 'Hyderabad', 'Telangana', '500001', 'Banjara Hills', '2024-06-18', 1, 6),
                ('Sneha Kulkarni', 'sneha.k@example.com', '9866677788', 'A-', 23, 'Female', 52.0, 'Pune', 'Maharashtra', '411001', 'Kothrud', '2024-09-12', 1, 2)
            ]
            donor_pwd = generate_password_hash('donor123')

            for d in sample_donors:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, phone, role)
                    VALUES (%s, %s, %s, %s, 'donor')
                """, (d[0], d[1], donor_pwd, d[2]))
                uid = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO donors (user_id, blood_group, age, gender, weight_kg, city, state, pincode, address, last_donation_date, is_available, is_verified, total_donations)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (uid, d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12], 1, d[13]))

            sample_requests = [
                ('Ramesh Chandra', 'O-', 2, 'AIIMS Hospital', 'Ansari Nagar', 'New Delhi', 'Delhi', 'Dr. Alok Verma', '9811122299', 'Critical', 'Emergency open-heart surgery required urgently.', 'Pending'),
                ('Sunita Sen', 'B+', 3, 'Lilavati Hospital', 'Bandra West', 'Mumbai', 'Maharashtra', 'Dr. Maya Roy', '9822233388', 'Urgent', 'Severe Dengue with critically low platelet counts.', 'Pending'),
                ('Baby Aarohi (Age 4)', 'A+', 1, 'Rainbow Children Hospital', 'Marathahalli', 'Bengaluru', 'Karnataka', 'Dr. Srinivas', '9833344477', 'Critical', 'Pediatric Thalassemia major monthly transfusion.', 'Pending')
            ]
            for req in sample_requests:
                cursor.execute("""
                    INSERT INTO blood_requests (patient_name, blood_group, units_needed, hospital_name, hospital_address, city, state, contact_person, contact_phone, urgency_level, reason, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, req)
            print("   [SUCCESS] Seeded administrator, 6 donors, and emergency requests!")

        conn.commit()
        conn.close()
        print("-" * 60)
        print(" [ALL COMPLETE] MySQL database is 100% configured and ready!")
        print("=" * 60)
        return True

    except pymysql.MySQLError as err:
        print("\n[ERROR] Could not connect to MySQL server:")
        print(f"Details: {err}")
        print("\nTroubleshooting tips for Windows:")
        print(" 1. If using XAMPP: Open XAMPP Control Panel and start the 'MySQL' module.")
        print(" 2. If using MySQL Workbench/Server: Ensure the 'MySQL80' Windows service is running.")
        print(" 3. Check config.py if your MySQL user/password differs from root / empty.")
        print("=" * 60)
        return False

if __name__ == '__main__':
    setup_mysql()
