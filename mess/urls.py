from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("students", views.StudentViewSet, basename="student")
router.register("staff", views.StaffViewSet, basename="staff")
router.register("menus", views.MealMenuViewSet, basename="menu")
router.register("bookings", views.BookingViewSet, basename="booking")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("complaints", views.ComplaintViewSet, basename="complaint")
router.register("inventory", views.InventoryViewSet, basename="inventory")
router.register("attendance", views.AttendanceViewSet, basename="attendance")
router.register("wastage", views.WastageViewSet, basename="wastage")
router.register("announcements", views.AnnouncementViewSet, basename="announcement")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("dashboard/student/", views.StudentDashboardView.as_view()),
    path("dashboard/staff/", views.StaffDashboardView.as_view()),
    path("dashboard/admin/", views.AdminDashboardView.as_view()),
    path("reports/monthly/", views.MonthlyReportView.as_view()),
    path("", include(router.urls)),
]
