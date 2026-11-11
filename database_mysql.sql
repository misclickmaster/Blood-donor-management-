-- ==============================================================
-- LifeStream Blood Donor Finder & Emergency Management Portal
-- Database Schema for MySQL 5.7 / 8.0 / MariaDB (XAMPP / WAMP)
-- Course: CSE 2nd Year Mini Project (DBMS & Web Technologies)
-- ==============================================================

CREATE DATABASE IF NOT EXISTS `blood_bank_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `blood_bank_db`;

-- --------------------------------------------------------------
-- 1. Table structure for table `users`
-- Stores authentication credentials, contact info, and roles
-- --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(150) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20) NOT NULL,
    `role` ENUM('donor', 'requester', 'admin') NOT NULL DEFAULT 'donor',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------
-- 2. Table structure for table `donors`
-- Stores medical details, location, and donation status of donors
-- --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `donors` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `blood_group` VARCHAR(5) NOT NULL,
    `age` INT NOT NULL,
    `gender` VARCHAR(10) NOT NULL,
    `weight_kg` DECIMAL(5,2),
    `city` VARCHAR(100) NOT NULL,
    `state` VARCHAR(100) NOT NULL,
    `pincode` VARCHAR(10),
    `address` TEXT,
    `last_donation_date` DATE NULL,
    `is_available` TINYINT(1) NOT NULL DEFAULT 1,
    `is_verified` TINYINT(1) NOT NULL DEFAULT 1,
    `total_donations` INT DEFAULT 0,
    `medical_notes` TEXT,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------
-- 3. Table structure for table `blood_requests`
-- Stores emergency requests from patients and hospitals
-- --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `blood_requests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `requester_id` INT NULL,
    `patient_name` VARCHAR(100) NOT NULL,
    `blood_group` VARCHAR(5) NOT NULL,
    `units_needed` INT NOT NULL DEFAULT 1,
    `hospital_name` VARCHAR(150) NOT NULL,
    `hospital_address` TEXT,
    `city` VARCHAR(100) NOT NULL,
    `state` VARCHAR(100) NOT NULL,
    `contact_person` VARCHAR(100) NOT NULL,
    `contact_phone` VARCHAR(20) NOT NULL,
    `urgency_level` ENUM('Normal', 'Urgent', 'Critical') NOT NULL DEFAULT 'Urgent',
    `reason` TEXT,
    `status` ENUM('Pending', 'Fulfilled', 'Cancelled') NOT NULL DEFAULT 'Pending',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`requester_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------
-- 4. Table structure for table `donation_responses`
-- Stores volunteer response pledges from donors to requests
-- --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `donation_responses` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `request_id` INT NOT NULL,
    `donor_id` INT NOT NULL,
    `message` TEXT,
    `status` VARCHAR(20) DEFAULT 'Accepted',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`request_id`) REFERENCES `blood_requests`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`donor_id`) REFERENCES `donors`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------
-- 5. Seed Initial Administrator Account
-- Email: admin@bloodfinder.com | Password: admin123
-- --------------------------------------------------------------
INSERT INTO `users` (`name`, `email`, `password_hash`, `phone`, `role`)
VALUES (
    'System Administrator', 
    'admin@bloodfinder.com', 
    'scrypt:32768:8:1$zD72M5zKSp5V0mQJ$7133f99e462c8a14ecbe567a5b3a4a161f3014aefbe2bcdeebcc22869400ad60a2b8e88ce9287cf4546bf7fa8c35336e4fba4fec649c0174ca2843bb3543d839', 
    '+91 9876543210', 
    'admin'
) ON DUPLICATE KEY UPDATE `email`=`email`;

-- --------------------------------------------------------------
-- 6. Seed Sample Voluntary Donors across India
-- Password for all sample donors: donor123
-- --------------------------------------------------------------
INSERT INTO `users` (`id`, `name`, `email`, `password_hash`, `phone`, `role`) VALUES
(2, 'Aarav Sharma', 'aarav.sharma@example.com', 'scrypt:32768:8:1$3n9g3jE7Y8l9eP1k$4337b58832a8f906ba0646c243644fcf6e9e4e6b189ff4c2813133cb611f7c02b1154865fc71ad1909fa8fe5757b4f59c869ba002db68652433e24bcf3c07657', '9811122233', 'donor'),
(3, 'Priya Patel', 'priya.patel@example.com', 'scrypt:32768:8:1$3n9g3jE7Y8l9eP1k$4337b58832a8f906ba0646c243644fcf6e9e4e6b189ff4c2813133cb611f7c02b1154865fc71ad1909fa8fe5757b4f59c869ba002db68652433e24bcf3c07657', '9822233344', 'donor'),
(4, 'Rahul Verma', 'rahul.verma@example.com', 'scrypt:32768:8:1$3n9g3jE7Y8l9eP1k$4337b58832a8f906ba0646c243644fcf6e9e4e6b189ff4c2813133cb611f7c02b1154865fc71ad1909fa8fe5757b4f59c869ba002db68652433e24bcf3c07657', '9833344455', 'donor'),
(5, 'Ananya Iyer', 'ananya.iyer@example.com', 'scrypt:32768:8:1$3n9g3jE7Y8l9eP1k$4337b58832a8f906ba0646c243644fcf6e9e4e6b189ff4c2813133cb611f7c02b1154865fc71ad1909fa8fe5757b4f59c869ba002db68652433e24bcf3c07657', '9844455566', 'donor'),
(6, 'Vikram Malhotra', 'vikram.m@example.com', 'scrypt:32768:8:1$3n9g3jE7Y8l9eP1k$4337b58832a8f906ba0646c243644fcf6e9e4e6b189ff4c2813133cb611f7c02b1154865fc71ad1909fa8fe5757b4f59c869ba002db68652433e24bcf3c07657', '9855566677', 'donor'),
(7, 'Sneha Kulkarni', 'sneha.k@example.com', 'scrypt:32768:8:1$3n9g3jE7Y8l9eP1k$4337b58832a8f906ba0646c243644fcf6e9e4e6b189ff4c2813133cb611f7c02b1154865fc71ad1909fa8fe5757b4f59c869ba002db68652433e24bcf3c07657', '9866677788', 'donor')
ON DUPLICATE KEY UPDATE `email`=`email`;

INSERT INTO `donors` (`user_id`, `blood_group`, `age`, `gender`, `weight_kg`, `city`, `state`, `pincode`, `address`, `last_donation_date`, `is_available`, `is_verified`, `total_donations`) VALUES
(2, 'O+', 24, 'Male', 68.5, 'New Delhi', 'Delhi', '110001', 'Connaught Place', '2024-08-15', 1, 1, 3),
(3, 'A+', 22, 'Female', 55.0, 'Mumbai', 'Maharashtra', '400001', 'Andheri West', '2024-09-01', 1, 1, 2),
(4, 'B+', 28, 'Male', 74.0, 'Bengaluru', 'Karnataka', '560001', 'Indiranagar', '2024-07-20', 1, 1, 5),
(5, 'AB+', 26, 'Female', 58.0, 'Chennai', 'Tamil Nadu', '600001', 'T. Nagar', '2024-05-10', 1, 1, 1),
(6, 'O-', 31, 'Male', 80.0, 'Hyderabad', 'Telangana', '500001', 'Banjara Hills', '2024-06-18', 1, 1, 6),
(7, 'A-', 23, 'Female', 52.0, 'Pune', 'Maharashtra', '411001', 'Kothrud', '2024-09-12', 1, 1, 2)
ON DUPLICATE KEY UPDATE `user_id`=`user_id`;

-- --------------------------------------------------------------
-- 7. Seed Sample Emergency Blood Requests
-- --------------------------------------------------------------
INSERT INTO `blood_requests` (`patient_name`, `blood_group`, `units_needed`, `hospital_name`, `hospital_address`, `city`, `state`, `contact_person`, `contact_phone`, `urgency_level`, `reason`, `status`) VALUES
('Ramesh Chandra', 'O-', 2, 'AIIMS Hospital', 'Ansari Nagar', 'New Delhi', 'Delhi', 'Dr. Alok Verma', '9811122299', 'Critical', 'Emergency open-heart surgery required urgently.', 'Pending'),
('Sunita Sen', 'B+', 3, 'Lilavati Hospital', 'Bandra West', 'Mumbai', 'Maharashtra', 'Dr. Maya Roy', '9822233388', 'Urgent', 'Severe Dengue with critically low platelet counts.', 'Pending'),
('Baby Aarohi (Age 4)', 'A+', 1, 'Rainbow Children Hospital', 'Marathahalli', 'Bengaluru', 'Karnataka', 'Dr. Srinivas', '9833344477', 'Critical', 'Pediatric Thalassemia major monthly transfusion.', 'Pending'),
('Mohammad Farooq', 'AB-', 2, 'Apollo Health City', 'Jubilee Hills', 'Hyderabad', 'Telangana', 'Tariq Farooq', '9855566600', 'Urgent', 'Emergency road accident multiple fractures trauma.', 'Pending');
