from django.contrib import admin
from .models import Invalidation


@admin.register(Invalidation)
class InvalidationAdmin(admin.ModelAdmin):
    list_display = ('user', 'pattern')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('user', 'pattern', 'created')
        return ('user', 'created')

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super().save_model(request, obj, form, change)
