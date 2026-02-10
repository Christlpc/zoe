from django.contrib import admin
from .models import WhatsAppSession, WhatsAppMessage

@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'agent', 'current_state', 'is_active', 'last_activity']
    list_filter = ['current_state', 'is_active', 'created_at']
    search_fields = ['phone_number', 'agent__matricule', 'agent__nom', 'agent__prenom']
    readonly_fields = ['created_at', 'last_activity']
    
    fieldsets = (
        ('Session', {
            'fields': ('phone_number', 'agent', 'current_state', 'is_active')
        }),
        ('Contexte', {
            'fields': ('context',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'last_activity')
        }),
    )

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'direction', 'message_type', 'timestamp']
    list_filter = ['direction', 'message_type', 'timestamp']
    search_fields = ['session__phone_number', 'whatsapp_message_id']
    readonly_fields = ['timestamp']
    
    def has_add_permission(self, request):
        return False  # Pas de création manuelle