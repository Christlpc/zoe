import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Service d'envoi de messages WhatsApp via Wassenger"""
    
    def __init__(self):
        self.api_url = "https://api.wassenger.com/v1/messages"
        self.api_key = settings.WASSENGER_API_KEY
        self.device_id = settings.WASSENGER_DEVICE_ID
    
    def send_text_message(self, to_phone, text):
        """Envoie un message texte simple"""
        payload = {
            "phone": to_phone,
            "message": text,
            "device": self.device_id
        }
        return self._send_request(payload)
    
    def send_interactive_buttons(self, to_phone, body_text, buttons):
        """
        Envoie un message avec boutons interactifs
        
        buttons = [
            {"id": "btn_1", "title": "Option 1"},
            {"id": "btn_2", "title": "Option 2"},
        ]
        """
        payload = {
            "phone": to_phone,
            "message": body_text,
            "device": self.device_id,
            "buttons": [
                {
                    "text": btn["title"]
                }
                for btn in buttons[:3]
            ]
        }
        return self._send_request(payload)
    
    def send_interactive_list(self, to_phone, body_text, button_text, sections):
        """
        Envoie une liste interactive
        """
        payload = {
            "phone": to_phone,
            "message": body_text,
            "device": self.device_id,
            "list": {
                "button": button_text,
                "sections": sections
            }
        }
        return self._send_request(payload)
    
    def _send_request(self, payload):
        """Envoie la requête à l'API Wassenger"""
        try:
            headers = {
                "Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            # Wassenger renvoie une liste de messages créés
            msg_id = result[0].get('id') if isinstance(result, list) and result else result.get('id')
            
            logger.info(f"✅ Message Wassenger envoyé: {result}")
            return {
                'success': True,
                'message_id': msg_id,
                'data': result
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_msg = f"{e.response.status_code}: {e.response.json()}"
                except:
                    error_msg = f"{e.response.status_code}: {e.response.text}"
            
            logger.error(f"❌ Erreur envoi Wassenger: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }