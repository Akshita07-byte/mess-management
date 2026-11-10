from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

MEAL_TYPES = [
    ("BREAKFAST", "Breakfast"),
    ("LUNCH", "Lunch"),
    ("SNACKS", "Snacks"),
    ("DINNER", "Dinner"),
]
MEAL_START = {
    "BREAKFAST": time(7, 30),
    "LUNCH": time(12, 30),
    "SNACKS": time(17, 0),
    "DINNER": time(20, 0),
}


class User(AbstractUser):
    """Single user table with a role field (Student / Admin / Mess Staff)."""

    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        ADMIN = "ADMIN", "Admin"
        STAFF = "STAFF", "Mess Staff"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=15, blank=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.get_full_name() or self.username


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student")
    roll_no = models.CharField(max_length=20, unique=True)
    branch = models.CharField(max_length=60, default="CSE")
    year = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    hostel = models.CharField(max_length=60, default="Boys Hostel A")
    room_no = models.CharField(max_length=10, blank=True)
    qr_code = models.CharField(max_length=60, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["roll_no"]

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = f"IIITBBS-MESS-{self.roll_no}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.roll_no} - {self.user.full_name}"


class Staff(models.Model):
    SHIFTS = [("MORNING", "Morning"), ("EVENING", "Evening"), ("FULL", "Full Day")]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    employee_id = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=60, default="Cook")
    shift = models.CharField(max_length=10, choices=SHIFTS, default="FULL")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_id"]
        verbose_name_plural = "staff"

    def __str__(self):
        return f"{self.employee_id} - {self.user.full_name}"


class MealMenu(models.Model):
    PREP_STATUS = [
        ("PLANNED", "Planned"),
        ("PREPARING", "Preparing"),
        ("READY", "Ready"),
        ("SERVED", "Served"),
    ]
    date = models.DateField()
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPES)
    items = models.TextField(help_text="Comma separated menu items")
    price = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    booking_deadline = models.DateTimeField(blank=True)
    prep_status = models.CharField(max_length=10, choices=PREP_STATUS, default="PLANNED")
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "id"]
        constraints = [models.UniqueConstraint(fields=["date", "meal_type"], name="unique_menu_per_meal_per_day")]

    def save(self, *args, **kwargs):
        if not self.booking_deadline:
            start = timezone.make_aware(datetime.combine(self.date, MEAL_START[self.meal_type]))
            self.booking_deadline = start - timedelta(hours=settings.BOOKING_DEADLINE_HOURS)
        super().save(*args, **kwargs)

    @property
    def is_open_for_booking(self):
        return self.is_available and timezone.now() < self.booking_deadline

    def __str__(self):
        return f"{self.date} {self.get_meal_type_display()}"


class Booking(models.Model):
    STATUS = [("BOOKED", "Booked"), ("CANCELLED", "Cancelled")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="bookings")
    menu = models.ForeignKey(MealMenu, on_delete=models.CASCADE, related_name="bookings")
    status = models.CharField(max_length=10, choices=STATUS, default="BOOKED")
    booked_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-menu__date", "menu__id"]
        constraints = [models.UniqueConstraint(fields=["student", "menu"], name="unique_booking_per_student_meal")]

    def __str__(self):
        return f"{self.student.roll_no} -> {self.menu} ({self.status})"


class Payment(models.Model):
    STATUS = [("PENDING", "Pending"), ("PAID", "Paid")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="payments")
    month = models.CharField(max_length=7, help_text="YYYY-MM")
    meals_count = models.PositiveIntegerField(default=0)
    meal_charges = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    fixed_charge = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=STATUS, default="PENDING")
    due_date = models.DateField()
    paid_on = models.DateTimeField(null=True, blank=True)
    txn_ref = models.CharField(max_length=30, blank=True, help_text="Simulated transaction reference")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month", "student__roll_no"]
        constraints = [models.UniqueConstraint(fields=["student", "month"], name="unique_bill_per_student_month")]

    def __str__(self):
        return f"{self.student.roll_no} {self.month} {self.amount} ({self.status})"


class Complaint(models.Model):
    CATEGORY = [
        ("FOOD_QUALITY", "Food Quality"),
        ("HYGIENE", "Hygiene"),
        ("SERVICE", "Service"),
        ("BILLING", "Billing"),
        ("OTHER", "Other"),
    ]
    STATUS = [("OPEN", "Open"), ("IN_PROGRESS", "In Progress"), ("RESOLVED", "Resolved")]
    ticket_no = models.CharField(max_length=15, unique=True, null=True, blank=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="complaints")
    category = models.CharField(max_length=15, choices=CATEGORY, default="FOOD_QUALITY")
    subject = models.CharField(max_length=150)
    description = models.TextField()
    rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    status = models.CharField(max_length=12, choices=STATUS, default="OPEN")
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.ticket_no:
            self.ticket_no = f"TKT-{self.pk:05d}"
            super().save(update_fields=["ticket_no"])

    def __str__(self):
        return f"{self.ticket_no} {self.subject}"


class Inventory(models.Model):
    CATEGORY = [
        ("GRAINS", "Grains & Pulses"),
        ("VEGETABLES", "Vegetables"),
        ("DAIRY", "Dairy"),
        ("SPICES", "Spices & Oil"),
        ("OTHER", "Other"),
    ]
    item_name = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=12, choices=CATEGORY, default="OTHER")
    quantity = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=10, default="kg")
    reorder_level = models.DecimalField(max_digits=9, decimal_places=2, default=10, validators=[MinValueValidator(0)])
    low_stock_reported = models.BooleanField(default=False)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "item_name"]
        verbose_name_plural = "inventory"

    @property
    def is_low(self):
        return self.quantity <= self.reorder_level

    def __str__(self):
        return f"{self.item_name} ({self.quantity} {self.unit})"


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance")
    menu = models.ForeignKey(MealMenu, on_delete=models.CASCADE, related_name="attendance")
    scanned_at = models.DateTimeField(default=timezone.now)
    marked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-scanned_at"]
        constraints = [models.UniqueConstraint(fields=["student", "menu"], name="unique_attendance_per_student_meal")]

    def __str__(self):
        return f"{self.student.roll_no} attended {self.menu}"


class Announcement(models.Model):
    PRIORITY = [("INFO", "Info"), ("IMPORTANT", "Important"), ("URGENT", "Urgent")]
    title = models.CharField(max_length=150)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY, default="INFO")
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="announcements")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Wastage(models.Model):
    """Food wastage record per meal (kg of cooked food discarded)."""

    menu = models.ForeignKey(MealMenu, on_delete=models.CASCADE, related_name="wastage")
    quantity_kg = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    reason = models.CharField(max_length=150, blank=True)
    recorded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name_plural = "wastage"

    def __str__(self):
        return f"{self.menu} - {self.quantity_kg} kg"
