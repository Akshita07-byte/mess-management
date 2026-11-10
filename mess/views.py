import csv
import random
import string
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import billing
from .models import (
    MEAL_TYPES,
    Announcement,
    Attendance,
    Booking,
    Complaint,
    Inventory,
    MealMenu,
    Payment,
    Staff,
    Student,
    Wastage,
)
from .permissions import (
    IsAdminOrStaff,
    IsAdminOrStudent,
    IsAdminRole,
    IsAnyRole,
    IsStaffRole,
    IsStudentRole,
)
from .serializers import (
    AnnouncementSerializer,
    AttendanceSerializer,
    BookingSerializer,
    ComplaintAdminSerializer,
    ComplaintSerializer,
    InventorySerializer,
    LoginSerializer,
    MealMenuSerializer,
    PaymentSerializer,
    RegisterSerializer,
    StaffSerializer,
    StudentSerializer,
    WastageSerializer,
)

MEAL_LABEL = dict(MEAL_TYPES)


def ok(message, data=None, http_status=status.HTTP_200_OK):
    return Response({"success": True, "message": message, "data": data}, status=http_status)


def fail(message, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "message": message}, status=http_status)


def f(value):
    """Decimal/None -> float for JSON charts."""
    return float(value or 0)


class PermissionsByAction:
    """Mixin: set `permission_map = {'action': PermClass, ...}` and `default_permission`."""

    permission_map = {}
    default_permission = IsAdminRole

    def get_permissions(self):
        perm = self.permission_map.get(self.action, self.default_permission)
        return [perm()]


# =========================================================================== AUTH
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        return ok(
            "Registration successful. You can now log in.",
            {"roll_no": student.roll_no, "qr_code": student.qr_code},
            status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [IsAnyRole]

    def get(self, request):
        user = request.user
        data = {
            "id": user.id,
            "username": user.username,
            "name": user.full_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "profile": None,
        }
        if user.role == "STUDENT" and hasattr(user, "student"):
            data["profile"] = StudentSerializer(user.student).data
        elif user.role == "STAFF" and hasattr(user, "staff_profile"):
            data["profile"] = StaffSerializer(user.staff_profile).data
        return Response(data)


# =========================================================================== STUDENTS / STAFF
class StudentViewSet(PermissionsByAction, viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    queryset = Student.objects.select_related("user").all()
    search_fields = ["roll_no", "user__first_name", "user__last_name", "hostel", "branch", "room_no"]
    ordering_fields = ["roll_no", "year", "hostel", "branch", "created_at"]
    permission_map = {"me": IsStudentRole}

    def get_queryset(self):
        qs = super().get_queryset()
        hostel = self.request.query_params.get("hostel")
        year = self.request.query_params.get("year")
        if hostel:
            qs = qs.filter(hostel=hostel)
        if year:
            qs = qs.filter(year=year)
        return qs

    def perform_destroy(self, instance):
        instance.user.delete()  # cascades to the Student row

    @action(detail=False, methods=["get"])
    def me(self, request):
        return Response(self.get_serializer(request.user.student).data)


class StaffViewSet(PermissionsByAction, viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    queryset = Staff.objects.select_related("user").all()
    search_fields = ["employee_id", "user__first_name", "user__last_name", "designation"]
    ordering_fields = ["employee_id", "designation", "shift"]

    def perform_destroy(self, instance):
        instance.user.delete()


# =========================================================================== MENU
class MealMenuViewSet(PermissionsByAction, viewsets.ModelViewSet):
    serializer_class = MealMenuSerializer
    search_fields = ["items"]
    ordering_fields = ["date", "meal_type", "price", "prep_status"]
    default_permission = IsAdminRole
    permission_map = {
        "list": IsAnyRole,
        "retrieve": IsAnyRole,
        "partial_update": IsAdminOrStaff,
        "update": IsAdminOrStaff,
    }
    STAFF_FIELDS = {"prep_status", "is_available"}

    def get_queryset(self):
        qs = MealMenu.objects.annotate(
            booked_total=Count("bookings", filter=Q(bookings__status="BOOKED"), distinct=True),
            attended_total=Count("attendance", distinct=True),
        )
        p = self.request.query_params
        if p.get("date"):
            qs = qs.filter(date=p["date"])
        if p.get("from"):
            qs = qs.filter(date__gte=p["from"])
        if p.get("to"):
            qs = qs.filter(date__lte=p["to"])
        if p.get("meal_type"):
            qs = qs.filter(meal_type=p["meal_type"])
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated and user.role == "STUDENT":
            ctx["my_bookings"] = {
                b.menu_id: {"id": b.id, "status": b.status}
                for b in Booking.objects.filter(student__user=user)
            }
        return ctx

    def update(self, request, *args, **kwargs):
        # Mess staff may only change preparation status / availability.
        if request.user.role == "STAFF":
            allowed = {k: v for k, v in request.data.items() if k in self.STAFF_FIELDS}
            if not allowed:
                return fail("Mess staff can only update preparation status and availability.", 403)
            kwargs["partial"] = True
            serializer = self.get_serializer(self.get_object(), data=allowed, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return super().update(request, *args, **kwargs)


# =========================================================================== BOOKINGS
class BookingViewSet(
    PermissionsByAction,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BookingSerializer
    search_fields = ["student__roll_no", "student__user__first_name", "student__user__last_name"]
    ordering_fields = ["booked_at", "status", "menu__date"]
    default_permission = IsAnyRole
    permission_map = {"create": IsStudentRole, "cancel": IsStudentRole}

    def get_queryset(self):
        qs = Booking.objects.select_related("student__user", "menu")
        user = self.request.user
        if user.role == "STUDENT":
            qs = qs.filter(student__user=user)
        p = self.request.query_params
        if p.get("date"):
            qs = qs.filter(menu__date=p["date"])
        if p.get("menu"):
            qs = qs.filter(menu_id=p["menu"])
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        menu_id = request.data.get("menu")
        try:
            menu = MealMenu.objects.get(pk=menu_id)
        except (MealMenu.DoesNotExist, ValueError, TypeError):
            return fail("Meal not found.", 404)
        if not menu.is_available:
            return fail("This meal is currently not available for booking.")
        if timezone.now() >= menu.booking_deadline:
            return fail("Booking deadline for this meal has passed.")
        student = request.user.student
        booking, created = Booking.objects.get_or_create(student=student, menu=menu)
        if not created:
            if booking.status == "BOOKED":
                return fail("You have already booked this meal.")
            booking.status = "BOOKED"
            booking.cancelled_at = None
            booking.save()
        return ok("Meal booked successfully.", BookingSerializer(booking).data, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status == "CANCELLED":
            return fail("This booking is already cancelled.")
        if timezone.now() >= booking.menu.booking_deadline:
            return fail("Cancellation is not allowed after the booking deadline.")
        booking.status = "CANCELLED"
        booking.cancelled_at = timezone.now()
        booking.save()
        return ok("Booking cancelled.", BookingSerializer(booking).data)


# =========================================================================== ATTENDANCE (simulated QR)
class AttendanceViewSet(
    PermissionsByAction, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = AttendanceSerializer
    search_fields = ["student__roll_no", "student__user__first_name", "student__user__last_name"]
    ordering_fields = ["scanned_at", "menu__date"]
    default_permission = IsAnyRole
    permission_map = {"scan": IsAdminOrStaff}

    def get_queryset(self):
        qs = Attendance.objects.select_related("student__user", "menu")
        if self.request.user.role == "STUDENT":
            qs = qs.filter(student__user=self.request.user)
        p = self.request.query_params
        if p.get("date"):
            qs = qs.filter(menu__date=p["date"])
        if p.get("menu"):
            qs = qs.filter(menu_id=p["menu"])
        return qs

    @action(detail=False, methods=["post"])
    def scan(self, request):
        """Simulated QR scan: body {qr_code | roll_no, menu}. Student must hold a BOOKED meal."""
        code = (request.data.get("qr_code") or request.data.get("roll_no") or "").strip()
        menu_id = request.data.get("menu")
        if not code or not menu_id:
            return fail("Both QR code (or roll number) and meal are required.")
        student = Student.objects.filter(Q(qr_code=code) | Q(roll_no=code)).select_related("user").first()
        if not student:
            return fail("Invalid QR code - student not found.", 404)
        try:
            menu = MealMenu.objects.get(pk=menu_id)
        except (MealMenu.DoesNotExist, ValueError, TypeError):
            return fail("Meal not found.", 404)
        if not Booking.objects.filter(student=student, menu=menu, status="BOOKED").exists():
            return fail(f"{student.user.full_name} has no booking for this meal.", 400)
        attendance, created = Attendance.objects.get_or_create(
            student=student, menu=menu, defaults={"marked_by": request.user}
        )
        if not created:
            return fail(f"{student.user.full_name} is already marked present for this meal.")
        return ok(
            f"Attendance marked for {student.user.full_name} ({student.roll_no}).",
            AttendanceSerializer(attendance).data,
            status.HTTP_201_CREATED,
        )


# =========================================================================== PAYMENTS / BILLING
class PaymentViewSet(PermissionsByAction, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentSerializer
    search_fields = ["student__roll_no", "student__user__first_name", "student__user__last_name", "txn_ref"]
    ordering_fields = ["month", "amount", "status", "due_date", "paid_on"]
    default_permission = IsAdminOrStudent
    permission_map = {
        "current": IsStudentRole,
        "pay": IsStudentRole,
        "mark_paid": IsAdminRole,
        "generate": IsAdminRole,
    }

    def get_queryset(self):
        qs = Payment.objects.select_related("student__user")
        if self.request.user.role == "STUDENT":
            qs = qs.filter(student__user=self.request.user)
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("month"):
            qs = qs.filter(month=p["month"])
        return qs

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Live bill for the running month, calculated from bookings."""
        month = timezone.localdate().strftime("%Y-%m")
        bill = billing.compute_bill(request.user.student, month)
        for key in ("meal_charges", "fixed_charge", "total"):
            bill[key] = f(bill[key])
        for row in bill["breakdown"]:
            row["amount"] = f(row["amount"])
        return Response(bill)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        """Simulated online payment (no real gateway)."""
        payment = self.get_object()
        if payment.status == "PAID":
            return fail("This bill is already paid.")
        payment.status = "PAID"
        payment.paid_on = timezone.now()
        payment.txn_ref = "SIM" + "".join(random.choices(string.digits, k=10))
        payment.save()
        return ok("Payment successful (simulated).", PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        payment = self.get_object()
        if payment.status == "PAID":
            return fail("This bill is already paid.")
        payment.status = "PAID"
        payment.paid_on = timezone.now()
        payment.txn_ref = payment.txn_ref or "CASH" + "".join(random.choices(string.digits, k=8))
        payment.save()
        return ok("Payment marked as paid.", PaymentSerializer(payment).data)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Admin: generate/refresh bills for a month. Body {month: 'YYYY-MM', fixed_charge?}"""
        month = request.data.get("month") or timezone.localdate().strftime("%Y-%m")
        try:
            billing.parse_month(month)
        except ValueError:
            return fail("Month must be in YYYY-MM format.")
        fixed = request.data.get("fixed_charge")
        try:
            fixed = Decimal(str(fixed)) if fixed not in (None, "") else None
        except Exception:
            return fail("Fixed charge must be a number.")
        result = billing.generate_bills(month, fixed)
        return ok(f"Bills generated for {month}: {result['created']} new, {result['updated']} updated.", result)


# =========================================================================== COMPLAINTS
class ComplaintViewSet(PermissionsByAction, viewsets.ModelViewSet):
    search_fields = ["ticket_no", "subject", "description", "student__roll_no", "student__user__first_name"]
    ordering_fields = ["created_at", "status", "category", "rating"]
    default_permission = IsAdminRole
    permission_map = {
        "list": IsAdminOrStudent,
        "retrieve": IsAdminOrStudent,
        "create": IsStudentRole,
    }
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.user.is_authenticated and self.request.user.role == "ADMIN":
            return ComplaintAdminSerializer
        return ComplaintSerializer

    def get_queryset(self):
        qs = Complaint.objects.select_related("student__user")
        if self.request.user.role == "STUDENT":
            qs = qs.filter(student__user=self.request.user)
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("category"):
            qs = qs.filter(category=p["category"])
        return qs

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.student)


# =========================================================================== INVENTORY
class InventoryViewSet(PermissionsByAction, viewsets.ModelViewSet):
    serializer_class = InventorySerializer
    search_fields = ["item_name", "category"]
    ordering_fields = ["item_name", "category", "quantity", "updated_at"]
    default_permission = IsAdminRole
    permission_map = {
        "list": IsAdminOrStaff,
        "retrieve": IsAdminOrStaff,
        "partial_update": IsAdminOrStaff,
        "update": IsAdminOrStaff,
        "report_low": IsAdminOrStaff,
    }

    def get_queryset(self):
        qs = Inventory.objects.select_related("updated_by")
        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(category=p["category"])
        return qs

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        # Clear the low-stock flag automatically once the item is restocked.
        if instance.low_stock_reported and not instance.is_low:
            instance.low_stock_reported = False
            instance.save(update_fields=["low_stock_reported"])

    @action(detail=True, methods=["post"])
    def report_low(self, request, pk=None):
        item = self.get_object()
        item.low_stock_reported = True
        item.updated_by = request.user
        item.save()
        return ok(f"{item.item_name} reported as low stock.", InventorySerializer(item).data)


# =========================================================================== WASTAGE
class WastageViewSet(PermissionsByAction, viewsets.ModelViewSet):
    serializer_class = WastageSerializer
    search_fields = ["reason"]
    ordering_fields = ["recorded_at", "quantity_kg"]
    default_permission = IsAdminOrStaff

    def get_queryset(self):
        qs = Wastage.objects.select_related("menu", "recorded_by")
        if self.request.query_params.get("date"):
            qs = qs.filter(menu__date=self.request.query_params["date"])
        return qs

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


# =========================================================================== ANNOUNCEMENTS
class AnnouncementViewSet(PermissionsByAction, viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.select_related("created_by")
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "priority"]
    default_permission = IsAdminRole
    permission_map = {"list": IsAnyRole, "retrieve": IsAnyRole}

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# =========================================================================== DASHBOARD ANALYTICS
def _last_days(n=7):
    today = timezone.localdate()
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


class StudentDashboardView(APIView):
    permission_classes = [IsStudentRole]

    def get(self, request):
        student = request.user.student
        today = timezone.localdate()
        month = today.strftime("%Y-%m")
        bill = billing.compute_bill(student, month)
        upcoming = (
            Booking.objects.filter(student=student, status="BOOKED", menu__date__gte=today)
            .select_related("menu")
            .order_by("menu__date", "menu__id")[:5]
        )
        pending = Payment.objects.filter(student=student, status="PENDING")
        data = {
            "student": {"name": request.user.full_name, "roll_no": student.roll_no, "hostel": student.hostel},
            "stats": {
                "meals_this_month": bill["meals_count"],
                "current_bill": f(bill["total"]),
                "pending_dues": f(pending.aggregate(t=Sum("amount"))["t"]),
                "pending_bills": pending.count(),
                "open_complaints": Complaint.objects.filter(student=student).exclude(status="RESOLVED").count(),
                "attended_this_month": Attendance.objects.filter(
                    student=student, menu__date__year=today.year, menu__date__month=today.month
                ).count(),
            },
            "upcoming": [
                {
                    "id": b.id,
                    "date": b.menu.date,
                    "meal_type": b.menu.meal_type,
                    "meal_label": b.menu.get_meal_type_display(),
                    "items": b.menu.items,
                }
                for b in upcoming
            ],
            "meal_mix": [
                {"name": MEAL_LABEL[r["menu__meal_type"]], "value": r["c"]}
                for r in Booking.objects.filter(
                    student=student, status="BOOKED", menu__date__year=today.year, menu__date__month=today.month
                )
                .values("menu__meal_type")
                .annotate(c=Count("id"))
            ],
            "announcements": AnnouncementSerializer(Announcement.objects.all()[:3], many=True).data,
        }
        return Response(data)


class StaffDashboardView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        today = timezone.localdate()
        menus = MealMenu.objects.filter(date=today).annotate(
            booked_total=Count("bookings", filter=Q(bookings__status="BOOKED"), distinct=True),
            attended_total=Count("attendance", distinct=True),
        )
        meals = [
            {
                "id": m.id,
                "meal_type": m.meal_type,
                "meal_label": m.get_meal_type_display(),
                "items": m.items,
                "prep_status": m.prep_status,
                "is_available": m.is_available,
                "booked": m.booked_total,
                "attended": m.attended_total,
            }
            for m in menus
        ]
        low = Inventory.objects.all()
        low_items = [i for i in low if i.is_low or i.low_stock_reported]
        return Response(
            {
                "date": today,
                "stats": {
                    "meals_today": len(meals),
                    "total_booked": sum(m["booked"] for m in meals),
                    "total_attended": sum(m["attended"] for m in meals),
                    "low_stock_items": len(low_items),
                },
                "meals": meals,
                "low_stock": InventorySerializer(low_items, many=True).data,
                "chart": [{"name": m["meal_label"], "Booked": m["booked"], "Attended": m["attended"]} for m in meals],
            }
        )


class AdminDashboardView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        today = timezone.localdate()
        days = _last_days(7)
        start = days[0]

        total_students = Student.objects.filter(user__is_active=True).count()
        today_bookings = Booking.objects.filter(menu__date=today, status="BOOKED").count()
        today_attendance = Attendance.objects.filter(menu__date=today).count()
        pay = Payment.objects.aggregate(
            pending=Sum("amount", filter=Q(status="PENDING")),
            collected=Sum("amount", filter=Q(status="PAID")),
            pending_n=Count("id", filter=Q(status="PENDING")),
            paid_n=Count("id", filter=Q(status="PAID")),
        )
        open_complaints = Complaint.objects.exclude(status="RESOLVED").count()
        low_stock = sum(1 for i in Inventory.objects.all() if i.is_low or i.low_stock_reported)

        # bookings per day per meal type (last 7 days)
        rows = (
            Booking.objects.filter(menu__date__range=(start, today), status="BOOKED")
            .values("menu__date", "menu__meal_type")
            .annotate(c=Count("id"))
        )
        by_day = {d: {"date": d.strftime("%d %b")} for d in days}
        for d in days:
            for key, _ in MEAL_TYPES:
                by_day[d][MEAL_LABEL[key]] = 0
        for r in rows:
            by_day[r["menu__date"]][MEAL_LABEL[r["menu__meal_type"]]] = r["c"]
        bookings_trend = [by_day[d] for d in days]

        # consumption: booked vs attended per meal type (last 7 days)
        booked_by_meal = {
            r["menu__meal_type"]: r["c"]
            for r in Booking.objects.filter(menu__date__range=(start, today), status="BOOKED")
            .values("menu__meal_type")
            .annotate(c=Count("id"))
        }
        attended_by_meal = {
            r["menu__meal_type"]: r["c"]
            for r in Attendance.objects.filter(menu__date__range=(start, today))
            .values("menu__meal_type")
            .annotate(c=Count("id"))
        }
        consumption = [
            {"name": label, "Booked": booked_by_meal.get(key, 0), "Attended": attended_by_meal.get(key, 0)}
            for key, label in MEAL_TYPES
        ]

        # wastage per day (last 7 days)
        waste = {
            r["menu__date"]: f(r["kg"])
            for r in Wastage.objects.filter(menu__date__range=(start, today))
            .values("menu__date")
            .annotate(kg=Sum("quantity_kg"))
        }
        wastage_trend = [{"date": d.strftime("%d %b"), "kg": waste.get(d, 0)} for d in days]

        # revenue by month
        revenue = [
            {"month": r["month"], "Collected": f(r["collected"]), "Pending": f(r["pending"])}
            for r in Payment.objects.values("month")
            .annotate(
                collected=Sum("amount", filter=Q(status="PAID")),
                pending=Sum("amount", filter=Q(status="PENDING")),
            )
            .order_by("month")
        ]

        complaint_status = [
            {"name": dict(Complaint.STATUS)[r["status"]], "value": r["c"]}
            for r in Complaint.objects.values("status").annotate(c=Count("id"))
        ]

        return Response(
            {
                "stats": {
                    "total_students": total_students,
                    "today_bookings": today_bookings,
                    "today_attendance": today_attendance,
                    "pending_amount": f(pay["pending"]),
                    "collected_amount": f(pay["collected"]),
                    "pending_bills": pay["pending_n"],
                    "paid_bills": pay["paid_n"],
                    "open_complaints": open_complaints,
                    "low_stock_items": low_stock,
                    "wastage_week_kg": round(sum(w["kg"] for w in wastage_trend), 1),
                },
                "bookings_trend": bookings_trend,
                "consumption": consumption,
                "wastage_trend": wastage_trend,
                "revenue": revenue,
                "payment_split": [
                    {"name": "Paid", "value": pay["paid_n"]},
                    {"name": "Pending", "value": pay["pending_n"]},
                ],
                "complaint_status": complaint_status,
                "recent_complaints": ComplaintSerializer(Complaint.objects.select_related("student__user")[:5], many=True).data,
            }
        )


class MonthlyReportView(APIView):
    """Admin monthly report. ?month=YYYY-MM  (&export=csv for a CSV download)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        month = request.query_params.get("month") or timezone.localdate().strftime("%Y-%m")
        try:
            year, mon = billing.parse_month(month)
        except ValueError:
            return fail("Month must be in YYYY-MM format.")

        bookings = Booking.objects.filter(menu__date__year=year, menu__date__month=mon, status="BOOKED")
        attendance = Attendance.objects.filter(menu__date__year=year, menu__date__month=mon)
        wastage = Wastage.objects.filter(menu__date__year=year, menu__date__month=mon)
        payments = Payment.objects.filter(month=month)
        complaints = Complaint.objects.filter(created_at__year=year, created_at__month=mon)

        booked_n = bookings.count()
        attended_n = attendance.count()
        pay = payments.aggregate(
            billed=Sum("amount"),
            collected=Sum("amount", filter=Q(status="PAID")),
            pending=Sum("amount", filter=Q(status="PENDING")),
        )

        per_meal = []
        for key, label in MEAL_TYPES:
            b = bookings.filter(menu__meal_type=key).count()
            a = attendance.filter(menu__meal_type=key).count()
            w = wastage.filter(menu__meal_type=key).aggregate(t=Sum("quantity_kg"))["t"]
            per_meal.append({"meal_type": label, "booked": b, "attended": a, "wastage_kg": f(w)})

        daily_b = {r["menu__date"]: r["c"] for r in bookings.values("menu__date").annotate(c=Count("id"))}
        daily_a = {r["menu__date"]: r["c"] for r in attendance.values("menu__date").annotate(c=Count("id"))}
        daily_w = {r["menu__date"]: f(r["t"]) for r in wastage.values("menu__date").annotate(t=Sum("quantity_kg"))}
        dates = sorted(set(daily_b) | set(daily_a) | set(daily_w))
        daily = [
            {"date": d.isoformat(), "booked": daily_b.get(d, 0), "attended": daily_a.get(d, 0), "wastage_kg": daily_w.get(d, 0)}
            for d in dates
        ]

        report = {
            "month": month,
            "summary": {
                "meals_booked": booked_n,
                "meals_attended": attended_n,
                "attendance_rate": round(attended_n * 100 / booked_n, 1) if booked_n else 0,
                "amount_billed": f(pay["billed"]),
                "amount_collected": f(pay["collected"]),
                "amount_pending": f(pay["pending"]),
                "complaints_raised": complaints.count(),
                "complaints_resolved": complaints.filter(status="RESOLVED").count(),
                "wastage_kg": f(wastage.aggregate(t=Sum("quantity_kg"))["t"]),
            },
            "per_meal": per_meal,
            "daily": daily,
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="mess_report_{month}.csv"'
            writer = csv.writer(response)
            writer.writerow(["IIIT Bhubaneswar Mess - Monthly Report (DEMO DATA)", month])
            writer.writerow([])
            writer.writerow(["Summary"])
            for k, v in report["summary"].items():
                writer.writerow([k.replace("_", " ").title(), v])
            writer.writerow([])
            writer.writerow(["Meal", "Booked", "Attended", "Wastage (kg)"])
            for r in per_meal:
                writer.writerow([r["meal_type"], r["booked"], r["attended"], r["wastage_kg"]])
            writer.writerow([])
            writer.writerow(["Date", "Booked", "Attended", "Wastage (kg)"])
            for r in daily:
                writer.writerow([r["date"], r["booked"], r["attended"], r["wastage_kg"]])
            return response
        return Response(report)
