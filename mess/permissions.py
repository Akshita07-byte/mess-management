from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.roles)


class IsAdminRole(RolePermission):
    roles = ("ADMIN",)


class IsStudentRole(RolePermission):
    roles = ("STUDENT",)


class IsStaffRole(RolePermission):
    roles = ("STAFF",)


class IsAdminOrStaff(RolePermission):
    roles = ("ADMIN", "STAFF")


class IsAdminOrStudent(RolePermission):
    roles = ("ADMIN", "STUDENT")


class IsAnyRole(RolePermission):
    roles = ("ADMIN", "STAFF", "STUDENT")
