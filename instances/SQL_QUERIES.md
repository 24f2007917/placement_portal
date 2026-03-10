# Raw SQLite Queries - Placement Portal

This document contains all the raw SQL queries used in the Placement Portal application.

## Database Schema Creation

### Users Table
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'company', 'student')),
    is_approved INTEGER DEFAULT 0,
    is_blacklisted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Students Table
```sql
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    roll_number TEXT UNIQUE NOT NULL,
    department TEXT NOT NULL,
    cgpa REAL,
    phone TEXT,
    resume_path TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
```

### Companies Table
```sql
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT,
    website TEXT,
    contact_person TEXT,
    phone TEXT,
    address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
```

### Placement Drives Table
```sql
CREATE TABLE IF NOT EXISTS placement_drives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    job_title TEXT NOT NULL,
    description TEXT,
    eligibility_criteria TEXT,
    min_cgpa REAL,
    salary_package TEXT,
    deadline DATE NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
)
```

### Applications Table
```sql
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    drive_id INTEGER NOT NULL,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'applied' CHECK(status IN ('applied', 'shortlisted', 'selected', 'rejected')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (drive_id) REFERENCES placement_drives(id) ON DELETE CASCADE,
    UNIQUE(student_id, drive_id)
)
```

## Authentication Queries

### Create Admin User
```sql
INSERT OR IGNORE INTO users (email, password, role, is_approved)
VALUES (?, ?, 'admin', 1)
```

### User Login - Fetch User by Email
```sql
SELECT * FROM users WHERE email = ?
```

### Check User Session
```sql
SELECT * FROM users WHERE id = ?
```

## Registration Queries

### Student Registration
```sql
-- Create user account
INSERT INTO users (email, password, role, is_approved) 
VALUES (?, ?, 'student', 0)

-- Create student profile
INSERT INTO students (user_id, name, roll_number, department, cgpa, phone)
VALUES (?, ?, ?, ?, ?, ?)
```

### Company Registration
```sql
-- Create user account
INSERT INTO users (email, password, role, is_approved) 
VALUES (?, ?, 'company', 0)

-- Create company profile
INSERT INTO companies (user_id, company_name, industry, website, contact_person, phone, address)
VALUES (?, ?, ?, ?, ?, ?, ?)
```

### Check Existing User
```sql
SELECT * FROM users WHERE email = ?
```

## Admin Queries

### Dashboard Statistics
```sql
-- Total students
SELECT COUNT(*) as count FROM students

-- Total companies
SELECT COUNT(*) as count FROM companies

-- Total drives
SELECT COUNT(*) as count FROM placement_drives

-- Total applications
SELECT COUNT(*) as count FROM applications

-- Pending companies
SELECT COUNT(*) as count FROM users WHERE role = 'company' AND is_approved = 0

-- Pending drives
SELECT COUNT(*) as count FROM placement_drives WHERE status = 'pending'
```

### Company Management
```sql
-- Get all companies
SELECT c.*, u.email, u.is_approved, u.is_blacklisted
FROM companies c
JOIN users u ON c.user_id = u.id
ORDER BY c.id DESC

-- Search companies
SELECT c.*, u.email, u.is_approved, u.is_blacklisted
FROM companies c
JOIN users u ON c.user_id = u.id
WHERE c.company_name LIKE ? OR c.industry LIKE ?
ORDER BY c.id DESC

-- Approve company
UPDATE users SET is_approved = 1 WHERE id = ?

-- Reject company
UPDATE users SET is_approved = 0 WHERE id = ?

-- Blacklist/Unblacklist company
UPDATE users SET is_blacklisted = ? WHERE id = ?

-- Delete company (cascades to user)
DELETE FROM users WHERE id = ?
```

### Student Management
```sql
-- Get all students
SELECT s.*, u.email, u.is_approved, u.is_blacklisted
FROM students s
JOIN users u ON s.user_id = u.id
ORDER BY s.id DESC

-- Search students
SELECT s.*, u.email, u.is_approved, u.is_blacklisted
FROM students s
JOIN users u ON s.user_id = u.id
WHERE s.name LIKE ? OR s.roll_number LIKE ? OR s.department LIKE ?
ORDER BY s.id DESC

-- Approve student
UPDATE users SET is_approved = 1 WHERE id = ?

-- Blacklist/Unblacklist student
UPDATE users SET is_blacklisted = ? WHERE id = ?

-- Delete student
DELETE FROM users WHERE id = ?
```

### Drive Management
```sql
-- Get all drives
SELECT pd.*, c.company_name
FROM placement_drives pd
JOIN companies c ON pd.company_id = c.id
ORDER BY pd.created_at DESC

-- Approve drive
UPDATE placement_drives SET status = "approved" WHERE id = ?

-- Reject drive
UPDATE placement_drives SET status = "rejected" WHERE id = ?
```

### Application Management
```sql
-- Get all applications
SELECT a.*, s.name as student_name, s.roll_number, 
       pd.job_title, c.company_name
FROM applications a
JOIN students s ON a.student_id = s.id
JOIN placement_drives pd ON a.drive_id = pd.id
JOIN companies c ON pd.company_id = c.id
ORDER BY a.application_date DESC
```

## Company Queries

### Dashboard Statistics
```sql
-- Get company profile
SELECT c.* FROM companies c
JOIN users u ON c.user_id = u.id
WHERE u.id = ?

-- Total drives
SELECT COUNT(*) as count FROM placement_drives WHERE company_id = ?

-- Approved drives
SELECT COUNT(*) as count FROM placement_drives 
WHERE company_id = ? AND status = 'approved'

-- Total applicants
SELECT COUNT(*) as count FROM applications a
JOIN placement_drives pd ON a.drive_id = pd.id
WHERE pd.company_id = ?
```

### Profile Management
```sql
-- Get company profile
SELECT * FROM companies WHERE user_id = ?

-- Update company profile
UPDATE companies SET company_name = ?, industry = ?, website = ?,
contact_person = ?, phone = ?, address = ?
WHERE user_id = ?
```

### Drive Management
```sql
-- Get company ID
SELECT id FROM companies WHERE user_id = ?

-- Get all company drives
SELECT * FROM placement_drives WHERE company_id = ? 
ORDER BY created_at DESC

-- Create drive
INSERT INTO placement_drives 
(company_id, job_title, description, eligibility_criteria, min_cgpa, salary_package, deadline)
VALUES (?, ?, ?, ?, ?, ?, ?)

-- Get drive for editing
SELECT * FROM placement_drives WHERE id = ? AND company_id = ?

-- Update drive
UPDATE placement_drives 
SET job_title = ?, description = ?, eligibility_criteria = ?, 
    min_cgpa = ?, salary_package = ?, deadline = ?
WHERE id = ?

-- Close drive
UPDATE placement_drives SET status = "closed" WHERE id = ? AND company_id = ?
```

### Applicant Management
```sql
-- Get applicants for a drive
SELECT a.*, s.name, s.roll_number, s.department, s.cgpa, s.phone, s.resume_path
FROM applications a
JOIN students s ON a.student_id = s.id
WHERE a.drive_id = ?
ORDER BY a.application_date DESC

-- Update application status
UPDATE applications SET status = ? WHERE id = ?
```

## Student Queries

### Dashboard Statistics
```sql
-- Get student profile
SELECT * FROM students WHERE user_id = ?

-- Total applications
SELECT COUNT(*) as count FROM applications WHERE student_id = ?

-- Selected count
SELECT COUNT(*) as count FROM applications 
WHERE student_id = ? AND status = 'selected'

-- Shortlisted count
SELECT COUNT(*) as count FROM applications 
WHERE student_id = ? AND status = 'shortlisted'
```

### Profile Management
```sql
-- Get student profile
SELECT * FROM students WHERE user_id = ?

-- Update student profile (with resume)
UPDATE students SET name = ?, department = ?, cgpa = ?, phone = ?, resume_path = ?
WHERE user_id = ?

-- Update student profile (without resume)
UPDATE students SET name = ?, department = ?, cgpa = ?, phone = ?
WHERE user_id = ?
```

### Drive Browsing
```sql
-- Get available drives with application status
SELECT pd.*, c.company_name,
       CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_applied
FROM placement_drives pd
JOIN companies c ON pd.company_id = c.id
LEFT JOIN applications a ON pd.id = a.drive_id AND a.student_id = ?
WHERE pd.status = 'approved' AND pd.deadline >= date('now')
ORDER BY pd.deadline ASC
```

### Application Management
```sql
-- Check if already applied
SELECT * FROM applications WHERE student_id = ? AND drive_id = ?

-- Get drive details for eligibility check
SELECT * FROM placement_drives WHERE id = ?

-- Create application
INSERT INTO applications (student_id, drive_id) VALUES (?, ?)

-- Get student applications
SELECT a.*, pd.job_title, pd.salary_package, c.company_name
FROM applications a
JOIN placement_drives pd ON a.drive_id = pd.id
JOIN companies c ON pd.company_id = c.id
WHERE a.student_id = ?
ORDER BY a.application_date DESC
```

## Key Query Features

### JOIN Operations
The application extensively uses JOIN operations to combine data from multiple tables:
- INNER JOIN: To get related data that must exist
- LEFT JOIN: To include optional relationships (e.g., checking if student has applied)

### Parameterized Queries
All queries use parameterized statements (?) to prevent SQL injection:
```python
cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
```

### Aggregate Functions
Statistics use COUNT() for dashboard metrics:
```sql
SELECT COUNT(*) as count FROM applications WHERE student_id = ?
```

### CASE Expressions
Dynamic columns based on conditions:
```sql
CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_applied
```

### Date Functions
Using SQLite date functions for filtering:
```sql
WHERE pd.deadline >= date('now')
```

### Constraints Enforcement
- UNIQUE constraints prevent duplicate applications
- CHECK constraints validate enum values
- FOREIGN KEY constraints maintain referential integrity
- ON DELETE CASCADE ensures data consistency

## Transaction Management

All write operations are committed:
```python
cursor.execute(query, params)
conn.commit()
conn.close()
```

Read operations don't require commits:
```python
result = conn.execute(query, params).fetchone()
conn.close()
```
