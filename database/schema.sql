-- ==============================================================================
-- Surplus Food Distribution System
-- Database Schema for MySQL 8.0+
-- Engine: InnoDB | Character Set: utf8mb4 | Collation: utf8mb4_unicode_ci
-- ==============================================================================

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS `surplus_food_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `surplus_food_db`;

-- Disable foreign key checks during schema creation
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------------------------
-- 1. Table: users (Central Authentication & Identity)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(150) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('admin', 'donor', 'ngo', 'volunteer') NOT NULL,
    `phone` VARCHAR(15) NOT NULL,
    `status` ENUM('active', 'inactive', 'pending_approval', 'rejected') NOT NULL DEFAULT 'active',
    `last_login` TIMESTAMP NULL DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_email` (`email`),
    INDEX `idx_users_role_status` (`role`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 2. Table: donors (Extended Profile for Food Donors)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `donors`;
CREATE TABLE `donors` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `donor_type` ENUM('individual', 'restaurant', 'hotel', 'caterer', 'corporate', 'supermarket', 'other') NOT NULL DEFAULT 'individual',
    `organization_name` VARCHAR(150) NULL,
    `address` TEXT NOT NULL,
    `city` VARCHAR(100) NOT NULL,
    `area` VARCHAR(100) NOT NULL,
    `pincode` VARCHAR(10) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_donors_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_donors_city_area` (`city`, `area`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 3. Table: ngos (Extended Profile for Verified NGOs)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `ngos`;
CREATE TABLE `ngos` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `ngo_name` VARCHAR(150) NOT NULL,
    `registration_number` VARCHAR(100) NOT NULL UNIQUE,
    `contact_person` VARCHAR(100) NOT NULL,
    `address` TEXT NOT NULL,
    `city` VARCHAR(100) NOT NULL,
    `state` VARCHAR(100) NOT NULL,
    `pincode` VARCHAR(10) NOT NULL,
    `ngo_type` ENUM('shelter', 'orphanage', 'food_bank', 'charity', 'community_kitchen', 'old_age_home', 'other') NOT NULL,
    `verification_document` VARCHAR(255) NULL,
    `verification_status` ENUM('pending', 'verified', 'rejected') NOT NULL DEFAULT 'pending',
    `verified_at` TIMESTAMP NULL DEFAULT NULL,
    `verified_by` INT NULL,
    `rejection_reason` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_ngos_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ngos_verifier` FOREIGN KEY (`verified_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    INDEX `idx_ngos_verification` (`verification_status`),
    INDEX `idx_ngos_city` (`city`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 4. Table: volunteers (Extended Profile for Volunteers)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `volunteers`;
CREATE TABLE `volunteers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `address` TEXT NOT NULL,
    `city` VARCHAR(100) NOT NULL,
    `pincode` VARCHAR(10) NOT NULL,
    `vehicle_type` ENUM('two_wheeler', 'four_wheeler', 'van', 'bicycle', 'none') DEFAULT 'none',
    `availability_status` ENUM('available', 'busy', 'inactive') NOT NULL DEFAULT 'available',
    `verified_status` ENUM('pending', 'verified', 'rejected') NOT NULL DEFAULT 'verified',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_volunteers_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_volunteers_city_avail` (`city`, `availability_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 5. Table: beneficiaries (Needy Groups/Individuals Maintained by NGOs)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `beneficiaries`;
CREATE TABLE `beneficiaries` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `ngo_id` INT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `age` INT NULL,
    `gender` ENUM('male', 'female', 'other', 'prefer_not_to_say') NOT NULL,
    `contact_number` VARCHAR(15) NULL,
    `address` TEXT NOT NULL,
    `household_count` INT NOT NULL DEFAULT 1,
    `special_requirements` TEXT NULL,
    `status` ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_beneficiaries_ngo` FOREIGN KEY (`ngo_id`) REFERENCES `ngos` (`id`) ON DELETE CASCADE,
    INDEX `idx_beneficiaries_ngo_status` (`ngo_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 6. Table: food_donations (Core Surplus Food Postings)
-- ------------------------------------------------------------------------------
CREATE TABLE `food_donations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `donor_id` INT NOT NULL,
    `food_name` VARCHAR(150) NOT NULL,
    `food_category` ENUM('cooked_meals', 'raw_ingredients', 'bakery_items', 'packaged_foods', 'fruits_vegetables', 'dairy_products', 'beverages', 'other') NOT NULL,
    `quantity` DECIMAL(10, 2) NOT NULL,
    `unit` ENUM('kg', 'liters', 'packets', 'servings', 'boxes', 'trays') NOT NULL,
    `servings_estimate` INT NOT NULL,
    `food_type` ENUM('veg', 'non_veg') NOT NULL,
    `preparation_datetime` DATETIME NOT NULL,
    `best_before_datetime` DATETIME NOT NULL,
    `pickup_address` TEXT NOT NULL,
    `city` VARCHAR(100) NOT NULL,
    `area` VARCHAR(100) NOT NULL,
    `pincode` VARCHAR(10) NOT NULL,
    `contact_number` VARCHAR(15) NOT NULL,
    `special_instructions` TEXT NULL,
    `food_image` VARCHAR(255) NULL,
    `status` ENUM(
        'Pending',
        'Approved',
        'Rejected',
        'Pickup Assigned',
        'Pickup Accepted',
        'Picked Up',
        'Delivered',
        'Distributed',
        'Completed',
        'Cancelled',
        'Expired'
    ) NOT NULL DEFAULT 'Pending',
    `approved_by` INT NULL,
    `rejection_reason` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_donations_donor` FOREIGN KEY (`donor_id`) REFERENCES `donors` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_donations_approver` FOREIGN KEY (`approved_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    INDEX `idx_donations_status` (`status`),
    INDEX `idx_donations_category` (`food_category`),
    INDEX `idx_donations_city_area` (`city`, `area`),
    INDEX `idx_donations_best_before` (`best_before_datetime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 7. Table: food_requests (NGO Claims / Requests for Available Food)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `food_requests`;
CREATE TABLE `food_requests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `donation_id` INT NOT NULL,
    `ngo_id` INT NOT NULL,
    `requested_quantity` DECIMAL(10, 2) NOT NULL,
    `status` ENUM('pending', 'approved', 'rejected', 'fulfilled', 'cancelled') NOT NULL DEFAULT 'pending',
    `request_notes` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_requests_donation` FOREIGN KEY (`donation_id`) REFERENCES `food_donations` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_requests_ngo` FOREIGN KEY (`ngo_id`) REFERENCES `ngos` (`id`) ON DELETE CASCADE,
    INDEX `idx_requests_donation` (`donation_id`),
    INDEX `idx_requests_ngo_status` (`ngo_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 8. Table: pickup_assignments (Volunteer Food Pickup Tracking)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `pickup_assignments`;
CREATE TABLE `pickup_assignments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `donation_id` INT NOT NULL,
    `volunteer_id` INT NOT NULL,
    `assigned_by` INT NOT NULL,
    `status` ENUM('assigned', 'accepted', 'rejected', 'picked_up', 'delivered', 'cancelled') NOT NULL DEFAULT 'assigned',
    `assigned_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `accepted_at` TIMESTAMP NULL DEFAULT NULL,
    `picked_up_at` TIMESTAMP NULL DEFAULT NULL,
    `delivered_at` TIMESTAMP NULL DEFAULT NULL,
    `collected_quantity` DECIMAL(10, 2) NULL,
    `volunteer_notes` TEXT NULL,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_pickups_donation` FOREIGN KEY (`donation_id`) REFERENCES `food_donations` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pickups_volunteer` FOREIGN KEY (`volunteer_id`) REFERENCES `volunteers` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pickups_assigner` FOREIGN KEY (`assigned_by`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_pickups_volunteer_status` (`volunteer_id`, `status`),
    INDEX `idx_pickups_donation` (`donation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 9. Table: distribution_records (Final Distribution to Communities/Beneficiaries)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `distribution_records`;
CREATE TABLE `distribution_records` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `donation_id` INT NOT NULL,
    `ngo_id` INT NOT NULL,
    `beneficiary_id` INT NULL,
    `distributed_quantity` DECIMAL(10, 2) NOT NULL,
    `servings_distributed` INT NOT NULL,
    `distribution_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `distribution_location` TEXT NOT NULL,
    `notes` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_distributions_donation` FOREIGN KEY (`donation_id`) REFERENCES `food_donations` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_distributions_ngo` FOREIGN KEY (`ngo_id`) REFERENCES `ngos` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_distributions_beneficiary` FOREIGN KEY (`beneficiary_id`) REFERENCES `beneficiaries` (`id`) ON DELETE SET NULL,
    INDEX `idx_distributions_ngo` (`ngo_id`),
    INDEX `idx_distributions_donation` (`donation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 10. Table: notifications (In-app Notification Messages)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `title` VARCHAR(150) NOT NULL,
    `message` TEXT NOT NULL,
    `type` ENUM('info', 'success', 'warning', 'danger') NOT NULL DEFAULT 'info',
    `is_read` BOOLEAN NOT NULL DEFAULT FALSE,
    `related_link` VARCHAR(255) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_notifications_user_read` (`user_id`, `is_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 11. Table: contact_inquiries (Public Contact Form Messages)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `contact_inquiries`;
CREATE TABLE `contact_inquiries` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(150) NOT NULL,
    `subject` VARCHAR(200) NOT NULL,
    `message` TEXT NOT NULL,
    `status` ENUM('new', 'read', 'resolved') NOT NULL DEFAULT 'new',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_contact_inquiries_status` (`status`),
    INDEX `idx_contact_inquiries_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 12. Table: audit_logs (Complete System Activity & Security Logs)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NULL,
    `action` VARCHAR(100) NOT NULL,
    `entity_type` VARCHAR(50) NOT NULL,
    `entity_id` INT NULL,
    `details` TEXT NULL,
    `ip_address` VARCHAR(45) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    INDEX `idx_audit_action` (`action`),
    INDEX `idx_audit_entity` (`entity_type`, `entity_id`),
    INDEX `idx_audit_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;


SELECT id, name, email, role, status
FROM users
WHERE email = 'admin@surplusfood.org';
