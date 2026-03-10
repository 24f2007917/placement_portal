# Placement Portal - Flask Web Application

A comprehensive placement management system built with Flask, SQLite, Bootstrap, and Jinja2.

## Features

### Admin Features
- Dashboard with statistics (students, companies, drives, applications)
- Approve/reject company registrations
- Approve/reject placement drives
- Manage students (view, search, approve, blacklist, delete)
- Manage companies (view, search, approve, blacklist, delete)
- View all placement drives
- View complete application history

### Company Features
- Registration and profile management
- Login after admin approval
- Create placement drives (requires admin approval)
- Edit and close placement drives
- View applicants for each drive
- Update application status (Shortlisted/Selected/Rejected)
- Dashboard with drive statistics

### Student Features
- Registration and profile management
- Upload resume (PDF)
- View approved placement drives
- Apply for drives (with CGPA eligibility check)
- Prevent duplicate applications
- View application status and history
- Dashboard with application statistics

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Database**: SQLite (programmatically created)
- **Frontend**: Jinja2 templates, HTML, CSS, Bootstrap 5
- **Authentication**: Flask-Login
- **No JavaScript** for core functionality (as per requirements)

## Project Structure

```
placement_portal/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── placement_portal.db         # SQLite database (auto-created)
├── static/
│   └── uploads/               # Resume storage
└── templates/
    ├── base.html              # Base template
    ├── index.html             # Landing page
    ├── login.html             # Login page
    ├── register.html          # Registration page
    ├── admin/
    │   ├── dashboard.html
    │   ├── companies.html
    │   ├── students.html
    │   ├── drives.html
    │   └── applications.html
    ├── company/
    │   ├── dashboard.html
    │   ├── profile.html
    │   ├── drives.html
    │   ├── create_drive.html
    │   ├── edit_drive.html
    │   └── applicants.html
    └── student/
        ├── dashboard.html
        ├── profile.html
        ├── drives.html
        └── applications.html
```

## Database Schema

### Tables

1. **users** - Authentication for all roles
   - id, email, password (hashed), role, is_approved, is_blacklisted, created_at

2. **students** - Student profile information
   - id, user_id (FK), name, roll_number, department, cgpa, phone, resume_path

3. **companies** - Company profile information
   - id, user_id (FK), company_name, industry, website, contact_person, phone, address

4. **placement_drives** - Job postings
   - id, company_id (FK), job_title, description, eligibility_criteria, min_cgpa, salary_package, deadline, status, created_at

5. **applications** - Student applications
   - id, student_id (FK), drive_id (FK), application_date, status
   - UNIQUE constraint: (student_id, drive_id) - prevents duplicate applications

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Install Dependencies

```bash
cd placement_portal
pip install -r requirements.txt
```

### Step 2: Run the Application

```bash
python app.py
```

The application will:
1. Automatically create the SQLite database
2. Set up all required tables
3. Create the default admin user
4. Start the Flask development server on http://0.0.0.0:5000

### Step 3: Access the Application

Open your web browser and navigate to:
```
http://localhost:5000
```

## Default Admin Credentials

```
Email: admin@placement.com
Password: admin123
```

**Important**: Change the admin password in production!

## Usage Guide

### For Students

1. **Register**: Click "Register as Student" on the home page
   - Fill in personal details, CGPA, department
   - Wait for admin approval

2. **Login**: After approval, login with your email and password

3. **Update Profile**: 
   - Navigate to Profile
   - Upload your resume (PDF)
   - Update contact information

4. **Apply for Drives**:
   - Browse "Available Drives"
   - Check eligibility (CGPA requirement)
   - Click "Apply Now"

5. **Track Applications**:
   - View "My Applications"
   - Check status: Applied, Shortlisted, Selected, or Rejected

### For Companies

1. **Register**: Click "Register as Company" on the home page
   - Fill in company details
   - Wait for admin approval

2. **Login**: After approval, login with your credentials

3. **Create Placement Drive**:
   - Click "Create New Placement Drive"
   - Fill in job details, eligibility, salary, deadline
   - Submit for admin approval

4. **Manage Drives**:
   - View all your drives
   - Edit drives (if pending or approved)
   - Close drives when recruitment is complete

5. **Review Applicants**:
   - Click "Applicants" on any approved drive
   - View student profiles and resumes
   - Update application status (Shortlist/Select/Reject)

### For Admins

1. **Login**: Use admin credentials

2. **Manage Companies**:
   - View all registered companies
   - Approve/reject registrations
   - Blacklist or delete companies

3. **Manage Students**:
   - View all registered students
   - Approve registrations
   - Blacklist or delete students

4. **Manage Drives**:
   - Review placement drives
   - Approve or reject drives
   - View all drive details

5. **Monitor Applications**:
   - View complete application history
   - Track placement statistics

## Key Features Implementation

### Role-Based Access Control
- Custom decorators enforce role-specific access
- Automatic blacklist checking
- Approval status validation

### Data Integrity
- Unique constraints prevent duplicate applications
- Foreign key relationships maintain data consistency
- Cascading deletes handle related records

### Security
- Password hashing using Werkzeug
- Flask-Login session management
- CSRF protection via form methods

### User Experience
- Responsive Bootstrap design
- Color-coded badges for status
- Collapsible details sections
- Flash messages for feedback

## Raw SQLite Queries

The application uses raw SQLite queries (via sqlite3 module) for all database operations:

```python
# Example: Create application
conn.execute('''
    INSERT INTO applications (student_id, drive_id) VALUES (?, ?)
''', (student_id, drive_id))

# Example: Join query
applications = conn.execute('''
    SELECT a.*, s.name, pd.job_title, c.company_name
    FROM applications a
    JOIN students s ON a.student_id = s.id
    JOIN placement_drives pd ON a.drive_id = pd.id
    JOIN companies c ON pd.company_id = c.id
    WHERE a.student_id = ?
''', (student_id,)).fetchall()
```

## Configuration

### File Upload Settings
- Maximum file size: 16MB
- Allowed formats: PDF for resumes
- Storage location: `static/uploads/`

### Database Location
- File: `placement_portal.db` (auto-created in project root)

### Secret Key
- Change in production: Update `app.config['SECRET_KEY']` in app.py

## Troubleshooting

### Database Issues
If you need to reset the database:
```bash
rm placement_portal.db
python app.py  # Will recreate database
```

### Permission Errors
Ensure the application has write permissions for:
- Current directory (for database file)
- `static/uploads/` directory (for resume uploads)

### Port Already in Use
If port 5000 is occupied, modify the last line in app.py:
```python
app.run(debug=True, host='0.0.0.0', port=5001)  # Use different port
```

## Development Notes

- Debug mode is enabled by default (turn off in production)
- Database uses `row_factory = sqlite3.Row` for dict-like access
- All timestamps use SQLite's CURRENT_TIMESTAMP
- File uploads are saved with user_id prefix for uniqueness

## Future Enhancements

- Email notifications
- Password reset functionality
- Advanced search and filtering
- Export reports (CSV/PDF)
- Batch operations
- Analytics dashboard

## License

This project is for educational purposes.

## Contact

For issues or questions, please refer to the project documentation.
