
from rest_framework.permissions import BasePermission, SAFE_METHODS


class BillingRolePermission(BasePermission):
    """
    Admin: Full access
    Billing Manager: Read, create, update
    Viewer: Read-only
    """

    def has_permission(self, request, view):

        # Superusers have unrestricted access
        if request.user.is_superuser:
            return True

        # User must be authenticated
        if not request.user.is_authenticated:
            return False

        # Read operations: GET, HEAD, OPTIONS
        if request.method in SAFE_METHODS:
            return (
                request.user.groups.filter(
                    name__in=["Admin", "Billing Manager", "Viewer"]
                ).exists()
            )

        # Admin: Full access
        if request.user.groups.filter(name="Admin").exists():
            return True

        # Billing Manager: Create and update, but not delete
        if request.method in ["POST", "PUT", "PATCH"]:
            return request.user.groups.filter(
                name="Billing Manager"
            ).exists()

        # Everyone else is denied
        return False
