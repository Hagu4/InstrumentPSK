from django.contrib import admin
from .error_models import ErrorEvent
from .price_sync import admin as price_sync_admin  # noqa: F401


@admin.register(ErrorEvent)
class ErrorEventAdmin(admin.ModelAdmin):
    list_display = ('last_seen', 'exception_type', 'route', 'method', 'occurrences', 'resolved')
    list_filter = ('resolved', 'exception_type', 'method', 'last_seen')
    search_fields = ('route', 'exception_type', 'stack')
    readonly_fields = ('fingerprint', 'first_seen', 'last_seen', 'exception_type', 'route', 'method', 'stack', 'occurrences')
    actions = None

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
