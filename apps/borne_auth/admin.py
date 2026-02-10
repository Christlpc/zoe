from django.contrib import admin
from .models import Agent

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['matricule', 'nom', 'prenom', 'telephone']
    search_fields = ['matricule', 'nom', 'prenom', 'telephone']
    
    def has_add_permission(self, request):
        return False  # Lecture seule car gérée par l'API principale
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
