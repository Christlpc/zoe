from django.db import models

class Agent(models.Model):
    """Agents NSIA pour attribution manuelle des polices (Version minimale)"""
    nom = models.CharField(max_length=60)
    prenom = models.CharField(max_length=60)
    telephone = models.CharField(max_length=25, unique=True)
    matricule = models.CharField(max_length=20, unique=True)
    
    class Meta:
        db_table = 'agents'
        managed = False  # On ne gère pas la table, on y accède seulement
        
    def __str__(self):
        return f"{self.matricule} - {self.prenom} {self.nom}"
    
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"
