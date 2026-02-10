from django.db import models
from apps.borne_auth.models import Agent
import uuid

class WhatsAppSession(models.Model):
    """Session conversationnelle agent WhatsApp"""
    
    ETATS = [
        ('ATTENTE_LOGIN', 'Attente connexion'),
        ('MENU_PRINCIPAL', 'Menu principal'),
        ('PASS_CHOIX_PRODUIT', 'Choix produit PASS'),
        ('PASS_CHOIX_RECURRENCE', 'Choix récurrence'),
        ('PASS_COLLECTE_NOM', 'Collecte nom'),
        ('PASS_COLLECTE_PRENOM', 'Collecte prénom'),
        ('PASS_COLLECTE_TELEPHONE', 'Collecte téléphone'),
        ('PASS_COLLECTE_NAISSANCE', 'Collecte date naissance'),
        ('PASS_AJOUT_BENEFICIAIRE', 'Ajout bénéficiaire'),
        ('PASS_CONFIRMATION', 'Confirmation'),
        ('COMMISSIONS_MENU', 'Menu commissions'),
        ('SIMULATEUR_CHOIX', 'Choix produit simulateur'),
        ('SIMULATEUR_COLLECTE', 'Collecte infos prospect'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='whatsapp_sessions'
    )
    phone_number = models.CharField(max_length=20, unique=True)
    current_state = models.CharField(max_length=50, choices=ETATS, default='ATTENTE_LOGIN')
    context = models.JSONField(default=dict, help_text="Données temporaires conversation")
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_sessions'
        ordering = ['-last_activity']
    
    def __str__(self):
        agent_info = f"Agent {self.agent.matricule}" if self.agent else "Non connecté"
        return f"{self.phone_number} - {agent_info} - {self.current_state}"
    
    def reset_context(self):
        """Réinitialise le contexte"""
        self.context = {}
        self.save()
    
    def update_context(self, key, value):
        """Met à jour une clé du contexte"""
        self.context[key] = value
        self.save()
    
    def get_context(self, key, default=None):
        """Récupère une valeur du contexte"""
        return self.context.get(key, default)


class WhatsAppMessage(models.Model):
    """Historique messages WhatsApp"""
    
    DIRECTIONS = [
        ('incoming', 'Reçu'),
        ('outgoing', 'Envoyé'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(WhatsAppSession, on_delete=models.CASCADE, related_name='messages')
    whatsapp_message_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    direction = models.CharField(max_length=10, choices=DIRECTIONS)
    message_type = models.CharField(max_length=20)  # text, interactive, button, etc.
    content = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_messages'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.direction} - {self.message_type} - {self.timestamp}"