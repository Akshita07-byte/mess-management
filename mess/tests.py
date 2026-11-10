"""Automated tests:  python manage.py test mess"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from . import billing
from .models import Attendance, Booking, Complaint, Inventory, MealMenu, Payment, Staff, Student, User


def make_student(roll="T001", name="Test"):
    user = User.objects.create_user(roll, password="pass1234", first_name=name, role="STUDENT")
    return Student.objects.create(user=user, roll_no=roll)


def make_menu(hours_ahead=10, meal_type="LUNCH", price=60, **kw):
    """Menu whose booking deadline is `hours_ahead` hours from now."""
    when = timezone.now() + timedelta(hours=hours_ahead)
    return MealMenu.objects.create(
        date=timezone.localtime(when).date(), meal_type=meal_type, items="Rice, Dal", price=price,
        booking_deadline=when, **kw,
    )


class Base(APITestCase):
    def setUp(self):
        self.student = make_student()
        self.admin = User.objects.create_superuser("admin", "a@x.com", "pass1234")
        staff_user = User.objects.create_user("MS1", password="pass1234", first_name="Cook", role="STAFF")
        Staff.objects.create(user=staff_user, employee_id="MS1")

    def login(self, username, password="pass1234", portal=None):
        body = {"username": username, "password": password}
        if portal:
            body["portal"] = portal
        res = self.client.post("/api/auth/login/", body, format="json")
        if res.status_code == 200:
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res


class AuthTests(Base):
    def test_login_returns_role(self):
        res = self.login("T001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["role"], "STUDENT")

    def test_wrong_password_rejected(self):
        self.assertEqual(self.login("T001", "wrong").status_code, 401)

    def test_wrong_portal_rejected(self):
        res = self.login("T001", portal="admin")
        self.assertEqual(res.status_code, 400)

    def test_superuser_gets_admin_role(self):
        self.assertEqual(self.login("admin").data["user"]["role"], "ADMIN")

    def test_registration_creates_student(self):
        res = self.client.post("/api/auth/register/", {
            "roll_no": "NEW1", "first_name": "New", "password": "secret12", "branch": "CSE", "year": 1,
            "hostel": "Boys Hostel A",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(Student.objects.filter(roll_no="NEW1").exists())

    def test_protected_endpoint_needs_token(self):
        self.assertEqual(self.client.get("/api/menus/").status_code, 401)


class PermissionTests(Base):
    def test_student_cannot_list_students(self):
        self.login("T001")
        self.assertEqual(self.client.get("/api/students/").status_code, 403)

    def test_admin_can_list_students(self):
        self.login("admin")
        self.assertEqual(self.client.get("/api/students/").status_code, 200)

    def test_staff_cannot_create_menu(self):
        self.login("MS1")
        res = self.client.post("/api/menus/", {"date": "2030-01-01", "meal_type": "LUNCH", "items": "x", "price": 10}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_staff_can_update_prep_status_only(self):
        menu = make_menu()
        self.login("MS1")
        ok = self.client.patch(f"/api/menus/{menu.id}/", {"prep_status": "READY"}, format="json")
        self.assertEqual(ok.status_code, 200)
        bad = self.client.patch(f"/api/menus/{menu.id}/", {"price": 999}, format="json")
        self.assertEqual(bad.status_code, 403)
        menu.refresh_from_db()
        self.assertEqual(menu.prep_status, "READY")
        self.assertEqual(float(menu.price), 60.0)

    def test_student_sees_only_own_bookings(self):
        other = make_student("T002")
        menu = make_menu()
        Booking.objects.create(student=other, menu=menu)
        Booking.objects.create(student=self.student, menu=menu)
        self.login("T001")
        res = self.client.get("/api/bookings/")
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["roll_no"], "T001")


class BookingTests(Base):
    def test_book_and_duplicate(self):
        menu = make_menu()
        self.login("T001")
        self.assertEqual(self.client.post("/api/bookings/", {"menu": menu.id}, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/bookings/", {"menu": menu.id}, format="json").status_code, 400)

    def test_booking_after_deadline_rejected(self):
        menu = make_menu(hours_ahead=-1)
        self.login("T001")
        res = self.client.post("/api/bookings/", {"menu": menu.id}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("deadline", res.data["message"].lower())

    def test_unavailable_meal_rejected(self):
        menu = make_menu(is_available=False)
        self.login("T001")
        self.assertEqual(self.client.post("/api/bookings/", {"menu": menu.id}, format="json").status_code, 400)

    def test_cancel_before_deadline_and_rebook(self):
        menu = make_menu()
        self.login("T001")
        booking_id = self.client.post("/api/bookings/", {"menu": menu.id}, format="json").data["data"]["id"]
        self.assertEqual(self.client.post(f"/api/bookings/{booking_id}/cancel/").status_code, 200)
        self.assertEqual(Booking.objects.get(pk=booking_id).status, "CANCELLED")
        self.assertEqual(self.client.post("/api/bookings/", {"menu": menu.id}, format="json").status_code, 201)
        self.assertEqual(Booking.objects.get(pk=booking_id).status, "BOOKED")

    def test_cancel_after_deadline_rejected(self):
        menu = make_menu(hours_ahead=-1)
        booking = Booking.objects.create(student=self.student, menu=menu)
        self.login("T001")
        self.assertEqual(self.client.post(f"/api/bookings/{booking.id}/cancel/").status_code, 400)


class BillingTests(Base):
    def test_bill_counts_only_non_cancelled(self):
        m1 = make_menu(5, "LUNCH", 60)
        m2 = make_menu(6, "DINNER", 55)
        Booking.objects.create(student=self.student, menu=m1)
        Booking.objects.create(student=self.student, menu=m2, status="CANCELLED")
        month = m1.date.strftime("%Y-%m")
        bill = billing.compute_bill(self.student, month, fixed_charge=500)
        self.assertEqual(bill["meals_count"], 1)
        self.assertEqual(float(bill["total"]), 560.0)

    def test_generate_bills_and_paid_not_overwritten(self):
        menu = make_menu(5, "LUNCH", 60)
        Booking.objects.create(student=self.student, menu=menu)
        month = menu.date.strftime("%Y-%m")
        self.login("admin")
        self.assertEqual(self.client.post("/api/payments/generate/", {"month": month, "fixed_charge": 500}, format="json").status_code, 200)
        pay = Payment.objects.get(student=self.student, month=month)
        self.assertEqual(float(pay.amount), 560.0)
        pay.status = "PAID"
        pay.save()
        self.client.post("/api/payments/generate/", {"month": month, "fixed_charge": 900}, format="json")
        pay.refresh_from_db()
        self.assertEqual(float(pay.amount), 560.0)

    def test_student_pays_simulated(self):
        pay = Payment.objects.create(student=self.student, month="2030-01", amount=500, due_date=timezone.localdate())
        self.login("T001")
        res = self.client.post(f"/api/payments/{pay.id}/pay/")
        self.assertEqual(res.status_code, 200)
        pay.refresh_from_db()
        self.assertEqual(pay.status, "PAID")
        self.assertTrue(pay.txn_ref.startswith("SIM"))
        self.assertEqual(self.client.post(f"/api/payments/{pay.id}/pay/").status_code, 400)


class ComplaintTests(Base):
    def test_ticket_number_generated_and_admin_update(self):
        self.login("T001")
        res = self.client.post("/api/complaints/", {"category": "HYGIENE", "subject": "Dirty", "description": "Plates"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        ticket = res.data["ticket_no"]
        self.assertRegex(ticket, r"^TKT-\d{5}$")
        self.assertEqual(res.data["status"], "OPEN")
        # student cannot change status
        cid = res.data["id"]
        self.assertEqual(self.client.patch(f"/api/complaints/{cid}/", {"status": "RESOLVED"}, format="json").status_code, 403)
        self.login("admin")
        res = self.client.patch(f"/api/complaints/{cid}/", {"status": "RESOLVED", "admin_response": "Fixed"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Complaint.objects.get(pk=cid).status, "RESOLVED")


class AttendanceInventoryTests(Base):
    def test_scan_requires_booking_and_blocks_duplicates(self):
        menu = make_menu()
        self.login("MS1")
        res = self.client.post("/api/attendance/scan/", {"qr_code": self.student.qr_code, "menu": menu.id}, format="json")
        self.assertEqual(res.status_code, 400)  # no booking
        Booking.objects.create(student=self.student, menu=menu)
        res = self.client.post("/api/attendance/scan/", {"qr_code": self.student.qr_code, "menu": menu.id}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        res = self.client.post("/api/attendance/scan/", {"roll_no": "T001", "menu": menu.id}, format="json")
        self.assertEqual(res.status_code, 400)  # duplicate
        self.assertEqual(Attendance.objects.count(), 1)

    def test_invalid_qr(self):
        menu = make_menu()
        self.login("MS1")
        self.assertEqual(self.client.post("/api/attendance/scan/", {"qr_code": "NOPE", "menu": menu.id}, format="json").status_code, 404)

    def test_low_stock_report_and_staff_update(self):
        item = Inventory.objects.create(item_name="Rice", quantity=5, unit="kg", reorder_level=10)
        self.assertTrue(item.is_low)
        self.login("MS1")
        self.assertEqual(self.client.post(f"/api/inventory/{item.id}/report_low/").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/inventory/{item.id}/", {"quantity": 50}, format="json").status_code, 200)
        item.refresh_from_db()
        self.assertFalse(item.low_stock_reported)  # cleared after restock
        # staff cannot create / delete
        self.assertEqual(self.client.post("/api/inventory/", {"item_name": "X", "quantity": 1}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/inventory/{item.id}/").status_code, 403)


class DashboardTests(Base):
    def test_dashboards_per_role(self):
        self.login("admin")
        res = self.client.get("/api/dashboard/admin/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("bookings_trend", res.data)
        self.assertEqual(self.client.get("/api/reports/monthly/").status_code, 200)
        self.login("T001")
        self.assertEqual(self.client.get("/api/dashboard/student/").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/admin/").status_code, 403)
        self.login("MS1")
        self.assertEqual(self.client.get("/api/dashboard/staff/").status_code, 200)
