# NSS Emergency Blood System 🩸

A premium, modern, and highly secure Django-powered Emergency Blood Network Web Application. This platform bridges the gap between emergency blood requesters and volunteer blood donors under the National Service Scheme (NSS), featuring intelligent donor matching, dynamic hospital integrations, automated audit logs, and certificate generation.

---

## 🚀 Key Features

### 1. Donor & Request Workflow
* **Find a Donor:** Search and filter verified volunteer donors by district/city and blood group.
* **Smart Pre-filling & Redirects:** Automatically passes selected search parameters to the blood request form. Direct access is protected, prompting users to search first.
* **Emergency Blood Requests:** Dynamic forms filtered by district. Requesters can only choose from active hospitals configured for their selected district.
* **OTP Verification:** Guest requests are verified securely via 6-digit OTP codes with rate-limiting protection.
* **90-Day Cooldown Protection:** Restricts donor assignment and markings if the volunteer donated in the last 90 days.

### 2. Admin Command Center
* **Light-Themed Sidebar UI:** Completely redesigned with premium, theme-consistent styling, rounded corners, active link markers, and zero page refreshes.
* **Intelligent Request Verification:** Auto-assigns the longest-standing available donor matching the required blood group and district.
* **Donation Audits & Certificates:** Verify volunteer donations and generate unique serial certificates (e.g., `NSS-YYYY-XXXX`).
* **Directories Management:** Admin-only tools to Add, Edit, and Toggle active status for **Hospitals** and **Blood Banks**.
* **Camps Planner:** Organize donation camps and manage donor registrations.
* **Mass Messages:** Publish broadcast alerts to volunteers.

### 3. System Activity History (Audit Logs)
* Track, search, and filter all critical events inside the dashboard:
  * New Blood Requests (verified requests only)
  * Completed Donations & NSS Verifications
  * New Donor Registrations
  * Admin Login History
  * Hospital & Blood Bank modifications (Add/Edit/Delete)
  * Blood Camp Scheduling
  * Request approvals and rejection reasons

---

## 🛠 Tech Stack

* **Backend Framework:** Django 5.0.6 (Python)
* **Task Queue & Scheduler:** Celery 5.4.0 + Redis 5.0.8 (for asynchronous SMS alerts and status updates)
* **Security & Audits:** 
  * `django-axes` (for login rate-limiting and brute-force lockouts)
  * `django-csp` (Content Security Policy compliance)
* **Database:** PostgreSQL (Production) / SQLite (Development)
* **Frontend:** Tailwind CSS, Vanilla JS, FontAwesome Icons

---

## ⚙️ Project Setup

### 1. Clone the repository and navigate to root
```bash
git clone https://github.com/yourusername/nss_blood_system.git
cd nss_blood_system
```

### 2. Set up virtual environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables (`.env`)
Create a `.env` file in the root directory:
```env
DEBUG=True
SECRET_KEY=your-django-secret-key
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://127.0.0.1:6379/0
```

### 5. Run Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Run Background Task Worker (Celery)
In a separate terminal:
```bash
celery -A nss_blood_system worker --loglevel=info
```

### 7. Run Server
```bash
python manage.py runserver
```

---

## 🧪 Testing Suite

Run the full automated test suite containing 40 unit tests verifying cooldown filters, dynamic queryset prefilling, dashboard endpoints, and the Activity History logging framework:
```bash
python manage.py test
```

---

## 📂 Directory Structure

```text
├── nss_blood_system/     # Core project settings and configuration
├── core/                 # Shared utilities, tasks, and middlewares
├── accounts/             # User authentication forms and logic
├── donors/               # Donor profiles, camps, and Activity Logs
├── requests/             # Emergency request handling, hospitals, and blood banks
├── dashboard/            # Admin panel dashboards and analytics
├── requirements.txt      # Project dependencies
└── manage.py             # Django project manager CLI
```

---
*Developed with ❤️ for NSS Blood Networks.*
