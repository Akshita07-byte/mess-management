from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    Announcement,
    Attendance,
    Booking,
    Complaint,
    Inventory,
    MealMenu,
    Payment,
    Staff,
    Student,
    User,
    Wastage,
)


# --------------------------------------------------------------------------- auth
class LoginSerializer(TokenObtainPairSerializer):
    """JWT login. Optional `portal` (student/admin/staff) must match the account role."""

    portal = serializers.CharField(required=False, write_only=True, allow_blank=True)

    def validate(self, attrs):
        portal = (attrs.get("portal") or "").upper()
        data = super().validate(attrs)
        user = self.user
        if portal and portal != user.role:
            raise serializers.ValidationError(
                f"This account is not a {portal.title()} account. Please use the correct portal."
            )
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "name": user.full_name,
            "role": user.role,
        }
        return data


class _UserFieldsMixin(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)
    email = serializers.EmailField(source="user.email", required=False, allow_blank=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=6)

    id_field = "roll_no"
    default_password = "Student@123"
    role = "STUDENT"

    def _check_username_free(self, value):
        qs = User.objects.filter(username=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("This ID is already used by another account.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", None) or self.default_password
        user = User.objects.create_user(
            username=validated_data[self.id_field], password=password, role=self.role, **user_data
        )
        return self.Meta.model.objects.create(user=user, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", None)
        user = instance.user
        for key, value in user_data.items():
            setattr(user, key, value)
        if password:
            user.set_password(password)
        user.save()
        return super().update(instance, validated_data)


class StudentSerializer(_UserFieldsMixin):
    def validate_roll_no(self, value):
        return self._check_username_free(value)

    class Meta:
        model = Student
        fields = [
            "id", "username", "roll_no", "first_name", "last_name", "full_name", "email", "phone",
            "branch", "year", "hostel", "room_no", "qr_code", "is_active", "password", "created_at",
        ]
        read_only_fields = ["qr_code", "created_at"]


class RegisterSerializer(StudentSerializer):
    """Public student self-registration (password required, cannot set is_active)."""

    password = serializers.CharField(write_only=True, min_length=6)

    class Meta(StudentSerializer.Meta):
        fields = [
            "roll_no", "first_name", "last_name", "email", "phone", "branch", "year",
            "hostel", "room_no", "password",
        ]


class StaffSerializer(_UserFieldsMixin):
    id_field = "employee_id"
    default_password = "Staff@123"
    role = "STAFF"

    def validate_employee_id(self, value):
        return self._check_username_free(value)

    class Meta:
        model = Staff
        fields = [
            "id", "username", "employee_id", "first_name", "last_name", "full_name", "email", "phone",
            "designation", "shift", "is_active", "password", "created_at",
        ]
        read_only_fields = ["created_at"]


# --------------------------------------------------------------------------- menu
class MealMenuSerializer(serializers.ModelSerializer):
    meal_type_label = serializers.CharField(source="get_meal_type_display", read_only=True)
    prep_status_label = serializers.CharField(source="get_prep_status_display", read_only=True)
    is_open_for_booking = serializers.BooleanField(read_only=True)
    booking_deadline = serializers.DateTimeField(required=False)
    booked_count = serializers.SerializerMethodField()
    attended_count = serializers.SerializerMethodField()
    my_booking = serializers.SerializerMethodField()

    class Meta:
        model = MealMenu
        fields = [
            "id", "date", "meal_type", "meal_type_label", "items", "price", "booking_deadline",
            "is_open_for_booking", "prep_status", "prep_status_label", "is_available",
            "booked_count", "attended_count", "my_booking",
        ]

    def get_booked_count(self, obj):
        value = getattr(obj, "booked_total", None)
        return value if value is not None else obj.bookings.filter(status="BOOKED").count()

    def get_attended_count(self, obj):
        value = getattr(obj, "attended_total", None)
        return value if value is not None else obj.attendance.count()

    def get_my_booking(self, obj):
        mapping = self.context.get("my_bookings")
        if mapping is None:
            return None
        return mapping.get(obj.id)

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value


class MenuBriefSerializer(serializers.ModelSerializer):
    meal_type_label = serializers.CharField(source="get_meal_type_display", read_only=True)
    is_open_for_booking = serializers.BooleanField(read_only=True)

    class Meta:
        model = MealMenu
        fields = ["id", "date", "meal_type", "meal_type_label", "items", "price", "booking_deadline", "is_open_for_booking"]


# --------------------------------------------------------------------------- bookings / attendance
class BookingSerializer(serializers.ModelSerializer):
    menu_detail = MenuBriefSerializer(source="menu", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    roll_no = serializers.CharField(source="student.roll_no", read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "menu", "menu_detail", "student_name", "roll_no", "status", "booked_at", "cancelled_at"]
        read_only_fields = ["status", "booked_at", "cancelled_at"]


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    roll_no = serializers.CharField(source="student.roll_no", read_only=True)
    date = serializers.DateField(source="menu.date", read_only=True)
    meal_type = serializers.CharField(source="menu.meal_type", read_only=True)

    class Meta:
        model = Attendance
        fields = ["id", "student", "student_name", "roll_no", "menu", "date", "meal_type", "scanned_at"]
        read_only_fields = ["scanned_at"]


# --------------------------------------------------------------------------- payments
class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    roll_no = serializers.CharField(source="student.roll_no", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "student", "student_name", "roll_no", "month", "meals_count", "meal_charges",
            "fixed_charge", "amount", "status", "due_date", "paid_on", "txn_ref",
        ]


# --------------------------------------------------------------------------- complaints
class ComplaintSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    roll_no = serializers.CharField(source="student.roll_no", read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Complaint
        fields = [
            "id", "ticket_no", "student_name", "roll_no", "category", "category_label", "subject",
            "description", "rating", "status", "admin_response", "created_at", "updated_at",
        ]
        read_only_fields = ["ticket_no", "status", "admin_response"]


class ComplaintAdminSerializer(ComplaintSerializer):
    class Meta(ComplaintSerializer.Meta):
        read_only_fields = ["ticket_no", "category", "subject", "description", "rating"]


# --------------------------------------------------------------------------- inventory / wastage / announcements
class InventorySerializer(serializers.ModelSerializer):
    is_low = serializers.BooleanField(read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.full_name", read_only=True, default="")

    class Meta:
        model = Inventory
        fields = [
            "id", "item_name", "category", "category_label", "quantity", "unit", "reorder_level",
            "is_low", "low_stock_reported", "updated_by_name", "updated_at",
        ]
        read_only_fields = ["low_stock_reported"]


class WastageSerializer(serializers.ModelSerializer):
    meal_label = serializers.SerializerMethodField()
    date = serializers.DateField(source="menu.date", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True, default="")

    class Meta:
        model = Wastage
        fields = ["id", "menu", "meal_label", "date", "quantity_kg", "reason", "recorded_by_name", "recorded_at"]
        read_only_fields = ["recorded_at"]

    def get_meal_label(self, obj):
        return f"{obj.menu.date:%d %b} - {obj.menu.get_meal_type_display()}"


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = Announcement
        fields = ["id", "title", "message", "priority", "created_by_name", "created_at"]
        read_only_fields = ["created_at"]
