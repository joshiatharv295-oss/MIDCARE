# 📋 PENDING APPOINTMENTS PANEL - SETUP GUIDE

## ✅ What Has Been Added:

### 1. **Database Updates**
   - The `Appointment` model already has a `status` field with values:
     - `Pending` - New appointments waiting for confirmation
     - `Confirmed` - Approved by doctor/admin
     - `Completed` - Appointment completed
     - `Cancelled` - Cancelled appointments

### 2. **New Views Created**
   - `pending_appointments` - HTML page showing pending appointments (admin/staff only)
   - `api_pending_appointments` - API endpoint for fetching and updating appointment statuses

### 3. **New URL Routes**
   - `/appointments/pending/` - Main pending appointments panel (admin-only)
   - `/api/pending-appointments/` - API endpoint for data management

### 4. **Admin Interface**
   - Already configured in Django admin: `/admin/`
   - Can view and filter appointments by status

## 🚀 Setup Instructions:

### Step 1: Run Migrations (if not already done)
```bash
cd server
python manage.py migrate
```

### Step 2: Create Admin and User Accounts
```bash
python manage.py setup_users
```

This will create:
- **Admin Account:**
  - Username: `admin`
  - Password: `admin@123`
  - Email: `admin@medicare.com`
  - Access: Full admin panel + pending appointments

- **Regular User Account:**
  - Username: `user`
  - Password: `user@123`
  - Email: `user@medicare.com`
  - Access: Can book appointments

### Step 3: Start the Django Server
```bash
python manage.py runserver
```

## 📍 Access Pending Appointments Panel:

### For Admin/Staff Users:
1. Go to: `http://localhost:8000/appointments/pending/`
2. Login with admin credentials if prompted
3. View all pending appointments
4. Update appointment statuses:
   - Click "Update" to open a modal and select new status
   - Click "✓ Confirm" for quick confirmation
5. Search and filter by doctor name, patient name, or status

### For Django Admin Panel:
1. Go to: `http://localhost:8000/admin/`
2. Login with admin credentials
3. Navigate to "Appointments" section
4. Filter by Status = "Pending"
5. Update appointments directly from the list

## 🔐 Security Features:

✅ **Admin-Only Access:**
- Only users with `is_staff` or `is_superuser` can access the pending appointments panel
- Unauthorized users get a 403 error
- API endpoints also check user permissions

✅ **CSRF Protection:**
- API endpoints are exempt for testing (marked with `@csrf_exempt`)
- In production, enable CSRF tokens for POST requests

## 🎯 Features:

### Pending Appointments Panel Features:
- ✅ Real-time appointment listing
- ✅ Search by doctor or patient name
- ✅ Filter by appointment status
- ✅ Update single or multiple appointments
- ✅ Auto-refresh every 30 seconds
- ✅ Display: Doctor name, Patient name, Date, Time
- ✅ Color-coded status badges
- ✅ Mobile responsive design

### API Endpoints:

**GET `/api/pending-appointments/`**
- Returns all appointments with their details
- Response: JSON with list of appointments
- Auth: Required (admin/staff only)

**POST `/api/pending-appointments/`**
- Updates appointment status
- Request: `{ "appointment_id": 1, "status": "Confirmed" }`
- Response: Updated appointment details
- Auth: Required (admin/staff only)

## 📊 Current Appointment Statuses:

The system recognizes these statuses:
- `Pending` - Yellow badge ⚠️
- `Confirmed` - Blue badge ✓
- `Completed` - Green badge ✅
- `Cancelled` - Red badge ✗

## 🔄 Managing Appointments:

### Via Pending Appointments Panel:
1. Click "Update" on any appointment
2. Select new status from dropdown
3. Click "Update" in modal
4. Status updates instantly

### Via API (cURL):
```bash
# Get all pending appointments
curl -X GET http://localhost:8000/api/pending-appointments/

# Update appointment status
curl -X POST http://localhost:8000/api/pending-appointments/ \
  -H "Content-Type: application/json" \
  -d '{"appointment_id": 1, "status": "Confirmed"}'
```

### Via Django Admin:
1. Go to `/admin/core/appointment/`
2. Find the appointment
3. Change status dropdown
4. Click "Save"

## ❓ Troubleshooting:

**Q: I get "Page not found" when accessing `/appointments/pending/`**
- A: Make sure you're logged in as admin/staff user
- A: Restart Django server after running migrations

**Q: Appointments don't show up**
- A: Make sure appointments exist in the database
- A: Check that they have the correct status fields

**Q: Getting 403 Forbidden error**
- A: Login with admin account (admin/admin@123)
- A: Make sure user is marked as staff or superuser

**Q: Management command doesn't work**
- A: Make sure you're in the server directory: `cd server`
- A: Verify migrations are run first

## 📝 Next Steps:

After setup, you can:
1. Create test appointments to see them in the pending panel
2. Update statuses and see real-time updates
3. Add email notifications when status changes (optional)
4. Add appointment notes for staff (optional)
5. Export pending appointments as PDF/CSV (optional)

---

**Questions or issues?** Check that Django is running and all migrations are applied!
