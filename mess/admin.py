from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

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


@admin.register(User)
class MessUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Mess", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Mess", {"fields": ("role", "phone")}),)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("roll_no", "user", "branch", "year", "hostel", "room_no")
    search_fields = ("roll_no", "user__first_name", "user__last_name")
    list_filter = ("hostel", "year", "branch")


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "user", "designation", "shift")


@admin.register(MealMenu)
class MealMenuAdmin(admin.ModelAdmin):
    list_display = ("date", "meal_type", "price", "prep_status", "is_available", "booking_deadline")
    list_filter = ("meal_type", "prep_status", "is_available")
    date_hierarchy = "date"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("student", "menu", "status", "booked_at")
    list_filter = ("status", "menu__meal_type")
    search_fields = ("student__roll_no",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("student", "month", "amount", "status", "due_date", "paid_on")
    list_filter = ("status", "month")
    search_fields = ("student__roll_no",)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("ticket_no", "student", "category", "subject", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("ticket_no", "subject")


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("item_name", "category", "quantity", "unit", "reorder_level", "low_stock_reported")
    list_filter = ("category",)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "menu", "scanned_at", "marked_by")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "priority", "created_by", "created_at")


@admin.register(Wastage)
class WastageAdmin(admin.ModelAdmin):
    list_display = ("menu", "quantity_kg", "reason", "recorded_at")
