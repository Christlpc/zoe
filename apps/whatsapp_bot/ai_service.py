import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class AIService:
    """Service d'intelligence artificielle pour le chatbot NSIA"""
    
    def __init__(self):
        # On s'attend à ces clés dans settings.py (ou via .env)
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
    
    def detect_intent(self, text):
        """
        Analyse le texte pour détecter l'intention et les entités.
        """
        if not self.api_key:
            logger.warning("⚠️ GEMINI_API_KEY non configurée. Détection IA désactivée.")
            return None
            
        system_prompt = """
        Tu es un assistant expert pour NSIA Vie Assurances. Ton rôle est d'analyser les messages des agents commerciaux sur WhatsApp.
        Analyse le message et retourne UNQUEMENT un objet JSON avec les clés suivantes :
        - intent : L'intention détectée parmi [SUBSCRIBE_PASS, CHECK_COMMISSIONS, RUN_SIMULATION, UNKNOWN]
        - product : Le produit mentionné (ex: BATELA, KIMIA, SALISA, RETRAITE, ETUDES) ou null
        - client_name : Le nom du client mentionné ou null
        - amount : Le montant ou la prime mentionnée ou null
        - confidence : Ton score de confiance (0 à 1)

        Guide de mapping :
        - "Je veux inscrire", "Souscription", "Pass", "Prendre un contrat" -> SUBSCRIBE_PASS
        - "Combien j'ai en commission", "Mes gains", "Chiffre d'affaires", "Mon solde" -> CHECK_COMMISSIONS
        - "Faire une simulation", "Calculer", "Projet retraite", "Simulation étude" -> RUN_SIMULATION
        """

        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{system_prompt}\n\nMessage de l'agent : \"{text}\""
                }]
            }],
            "generationConfig": {
                "response_mime_type": "application/json",
            }
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            # Extraction du contenu JSON généré par Gemini
            content_text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(content_text)
            
        except Exception as e:
            logger.error(f"❌ Erreur AI Intent Detection: {e}")
            return None

    def is_available(self):
        return self.api_key is not None
