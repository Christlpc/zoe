import re
import logging
from .services import WhatsAppService
from .ai_service import AIService
from .models import WhatsAppSession
from apps.borne_auth.models import Agent
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class ConversationHandler:
    """Gestionnaire principal de conversation"""
    
    def __init__(self, session: WhatsAppSession, message_text: str):
        self.session = session
        self.message_text = message_text.strip()
        self.wa_service = WhatsAppService()
        self.ai_service = AIService()

    def _normalize_choice(self, text=None):
        """
        Normalise l'entrée utilisateur pour gérer les boutons/listes interactifs.

        Gère les cas :
        - Texte simple : "1" → "1"
        - Bouton avec emoji : "1️⃣ Souscrire PASS" → "1"
        - ID de liste : "batela" → "batela"
        - Texte avec espaces : "  2  " → "2"
        """
        if text is None:
            text = self.message_text
        text = text.strip()

        # Si c'est déjà un chiffre seul, retourner tel quel
        if text.isdigit():
            return text

        # Extraire le premier chiffre (gère "1️⃣ Souscrire PASS" → "1")
        match = re.match(r'(\d)', text)
        if match:
            return match.group(1)

        # Retourner en minuscules pour le matching par mots-clés / IDs de liste
        return text.lower()

    def handle(self):
        """Route vers le bon handler selon l'état"""
        state = self.session.current_state
        
        handlers = {
            'ATTENTE_LOGIN': self.handle_login,
            'MENU_PRINCIPAL': self.handle_menu_principal,
            'PASS_CHOIX_PRODUIT': self.handle_pass_choix_produit,
            'PASS_CHOIX_RECURRENCE': self.handle_pass_choix_recurrence,
            'PASS_COLLECTE_NOM': self.handle_pass_collecte_nom,
            'PASS_COLLECTE_PRENOM': self.handle_pass_collecte_prenom,
            'PASS_COLLECTE_TELEPHONE': self.handle_pass_collecte_telephone,
            'PASS_COLLECTE_NAISSANCE': self.handle_pass_collecte_naissance,
            'PASS_CONFIRMATION': self.handle_pass_confirmation,
            'COMMISSIONS_MENU': self.handle_commissions,
            'SIMULATEUR_CHOIX': self.handle_simulateur_choix,
            'SIMULATEUR_COLLECTE': self.handle_simulateur_collecte,
        }
        
        handler = handlers.get(state)
        if handler:
            handler()
        else:
            self.send_error("État inconnu. Tapez 0 pour revenir au menu.")
    
    """def handle(self):
        #Route vers le bon handler selon l'état
        state = self.session.current_state
        
        # Analyse IA si on est au menu principal et que le message est complexe
        if state == 'MENU_PRINCIPAL' and len(self.message_text) > 1 and self.message_text not in ['0', '1', '2', '3']:
            if self.handle_ai_intent():
                return
                
        handlers = {
            'ATTENTE_LOGIN': self.handle_login,
            'MENU_PRINCIPAL': self.handle_menu_principal,
            'PASS_CHOIX_PRODUIT': self.handle_pass_choix_produit,
            'PASS_CHOIX_RECURRENCE': self.handle_pass_choix_recurrence,
            'PASS_COLLECTE_NOM': self.handle_pass_collecte_nom,
            'PASS_COLLECTE_PRENOM': self.handle_pass_collecte_prenom,
            'PASS_COLLECTE_TELEPHONE': self.handle_pass_collecte_telephone,
            'PASS_COLLECTE_NAISSANCE': self.handle_pass_collecte_naissance,
            'PASS_CONFIRMATION': self.handle_pass_confirmation,
            'COMMISSIONS_MENU': self.handle_commissions,
            'SIMULATEUR_CHOIX': self.handle_simulateur_choix,
            'SIMULATEUR_COLLECTE': self.handle_simulateur_collecte,
        }
        
        handler = handlers.get(state)
        if handler:
            handler()
        else:
            self.send_error("État inconnu. Tapez 0 pour revenir au menu.")"""
    
    """def handle_ai_intent(self):
        #Détecte l'intention via l'IA et route vers le bon flux
        if not self.ai_service.is_available():
            return False
            
        intent_data = self.ai_service.detect_intent(self.message_text)
        if not intent_data or intent_data.get('confidence', 0) < 0.7:
            return False
            
        intent = intent_data.get('intent')
        logger.info(f"🤖 IA Intent détectée : {intent} ({intent_data.get('confidence')})")
        
        if intent == 'SUBSCRIBE_PASS':
            self.session.current_state = 'PASS_CHOIX_PRODUIT'
            self.session.reset_context()
            self.session.save()
            self.show_pass_produits()
            return True
            
        elif intent == 'CHECK_COMMISSIONS':
            self.session.current_state = 'COMMISSIONS_MENU'
            self.session.save()
            self.show_commissions()
            return True
            
        elif intent == 'RUN_SIMULATION':
            self.session.current_state = 'SIMULATEUR_CHOIX'
            self.session.save()
            self.show_simulateur_produits()
            return True
            
        return False"""

    # ========================================
    # LOGIN AGENT
    # ========================================
    
    def handle_login(self):
        """Gère la connexion de l'agent via l'API uniquement"""
        if self._normalize_choice() == "0":
            self.send_welcome()
            return
    
        # Vérifier format: matricule:motdepasse
        if ":" not in self.message_text:
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Format incorrect.\n\nUtilisez: MATRICULE:MOTDEPASSE\n\nExemple: AG-2025-001:monmotdepasse\n\n0 - Aide"
            )
            return
    
        parts = self.message_text.split(":", 1)  # maxsplit=1 pour les mots de passe contenant ":"
        if len(parts) != 2:
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Format incorrect.\n\nUtilisez: MATRICULE:MOTDEPASSE"
            )
            return
    
        matricule, password = parts[0].strip(), parts[1].strip()
    
        try:
            response = requests.post(
                f"{settings.API_BASE_URL}/api/v1/auth/agent/login/",
                json={"matricule": matricule, "telephone": password},
                timeout=10
            )
    
            if response.status_code == 200:
                data = response.json().get('data', {})
                tokens = data.get('tokens', {})
                agent_data = data.get('agent', {})
                stats = data.get('statistiques', {})
                session_info = data.get('session', {})

                # Stocker toutes les infos en une seule écriture DB
                self.session.context.update({
                    'access_token': tokens.get('access'),
                    'refresh_token': tokens.get('refresh'),
                    'token_expires_in': session_info.get('expires_in', 86400),
                    'session_type': session_info.get('type'),
                    'agent_id': agent_data.get('id'),
                    'agent_name': agent_data.get('nom_complet'),
                    'agent_matricule': agent_data.get('matricule'),
                    'agent_agence': agent_data.get('agence'),
                    'agent_telephone': agent_data.get('telephone'),
                    'agent_poste': agent_data.get('poste'),
                    'agent_taux_commission': agent_data.get('taux_commission'),
                    'stats_total_souscriptions': stats.get('total_souscriptions', 0),
                    'stats_souscriptions_actives': stats.get('souscriptions_actives', 0),
                    'stats_souscriptions_ce_mois': stats.get('souscriptions_ce_mois', 0),
                })
                self.session.current_state = 'MENU_PRINCIPAL'
                self.session.save()
    
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    f"✅ Connexion réussie !\n\n"
                    f"👤 {agent_data.get('nom_complet')}\n"
                    f"📍 {agent_data.get('agence')}\n"
                    f"🆔 {agent_data.get('matricule')}\n"
                    f"💼 {agent_data.get('poste')}"
                )
    
                self.show_menu_principal()
    
            elif response.status_code == 401:
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Identifiants incorrects.\n\nVérifiez votre matricule et mot de passe.\n\nRéessayez: MATRICULE:MOTDEPASSE\n\n0 - Aide"
                )
    
            else:
                logger.warning(f"⚠️ Login échoué - status {response.status_code}: {response.text}")
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Connexion impossible. Réessayez plus tard.\n\n0 - Aide"
                )
    
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout lors du login API")
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Le serveur met trop de temps à répondre. Réessayez dans quelques instants."
            )
    
        except requests.exceptions.ConnectionError:
            logger.error("❌ Impossible de joindre l'API de connexion")
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Service temporairement indisponible. Réessayez plus tard."
            )
    
        except Exception as e:
            logger.error(f"❌ Erreur inattendue lors du login: {e}", exc_info=True)
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Une erreur est survenue. Réessayez plus tard."
            )
        
    # ========================================
    # MENU PRINCIPAL
    # ========================================
    
    def handle_menu_principal(self):
        """Gère le menu principal"""
        choix = self._normalize_choice()

        if choix == "1" or "souscrire" in choix or choix == "menu_1":
            # Souscription PASS
            self.session.current_state = 'PASS_CHOIX_PRODUIT'
            self.session.context = {
                k: v for k, v in self.session.context.items()
                if k.startswith('agent_') or k.startswith('access_') or k.startswith('refresh_') or k.startswith('stats_') or k.startswith('token_') or k.startswith('session_')
            }
            self.session.save()
            self.show_pass_produits()

        elif choix == "2" or "commission" in choix or choix == "menu_2":
            # Commissions
            self.session.current_state = 'COMMISSIONS_MENU'
            self.session.save()
            self.show_commissions()

        elif choix == "3" or "simulateur" in choix or "simulation" in choix or choix == "menu_3":
            # Simulateur
            self.session.current_state = 'SIMULATEUR_CHOIX'
            self.session.save()
            self.show_simulateur_produits()

        elif choix == "0":
            self.show_menu_principal()

        else:
            self.send_error("Option invalide. Choisissez 1, 2, 3 ou 0.")
    
    def show_menu_principal(self):
        """Affiche le menu principal"""
        self.wa_service.send_interactive_buttons(
            self.session.phone_number,
            f"🏠 MENU PRINCIPAL - NSIA VIE\n\n"
            f"Agent: {self.session.get_context('agent_name')}\n\n"
            f"Que souhaitez-vous faire ?",
            [
                {"id": "menu_1", "title": "1️⃣ Souscrire PASS"},
                {"id": "menu_2", "title": "2️⃣ Mes commissions"},
                {"id": "menu_3", "title": "3️⃣ Simulateur"},
            ]
        )
    
    # ========================================
    # FLOW PASS NSIA
    # ========================================
    
    def show_pass_produits(self):
        """Affiche les produits PASS"""
        self.wa_service.send_interactive_list(
            self.session.phone_number,
            "📦 PRODUITS PASS NSIA\n\nChoisissez le produit à souscrire :",
            "Voir les produits",
            [
                {
                    "title": "Produits PASS",
                    "rows": [
                        {
                            "id": "batela",
                            "title": "BATELA",
                            "description": "Épargne Retraite + Funéraire"
                        },
                        {
                            "id": "kimia",
                            "title": "KIMIA",
                            "description": "Accident + Funéraire"
                        },
                        {
                            "id": "salisa",
                            "title": "SALISA",
                            "description": "Hospitalisation + Funéraire"
                        }
                    ]
                }
            ]
        )
    
    def handle_pass_choix_produit(self):
        """Gère le choix du produit PASS"""
        produits = {
            "1": {"code": "batela", "nom": "BATELA", "id": 1},
            "2": {"code": "kimia", "nom": "KIMIA", "id": 2},
            "3": {"code": "salisa", "nom": "SALISA", "id": 3},
            "batela": {"code": "batela", "nom": "BATELA", "id": 1},
            "kimia": {"code": "kimia", "nom": "KIMIA", "id": 2},
            "salisa": {"code": "salisa", "nom": "SALISA", "id": 3},
        }

        choix = self._normalize_choice()
        
        if choix == "0":
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
            return
        
        if choix not in produits:
            self.send_error("Produit invalide. Choisissez 1, 2, 3 ou 0.")
            return
        
        produit = produits[choix]
        self.session.update_context('produit_pass_id', produit['id'])
        self.session.update_context('produit_nom', produit['nom'])
        self.session.current_state = 'PASS_CHOIX_RECURRENCE'
        self.session.save()
        
        # Afficher récurrences
        if produit['code'] == 'batela':
            message = (
                f"✅ PASS {produit['nom']} sélectionné\n\n"
                f"📅 Choisissez la récurrence :\n\n"
                f"1️⃣ Quotidien - 200 FCFA/jour\n"
                f"2️⃣ Mensuel - 6 000 FCFA/mois\n"
                f"3️⃣ Unique - 72 200 FCFA\n\n"
                f"Plafond total : 72 200 FCFA\n\n"
                f"0️⃣ Retour"
            )
        else:  # KIMIA ou SALISA
            message = (
                f"✅ PASS {produit['nom']} sélectionné\n\n"
                f"📅 Choisissez la récurrence :\n\n"
                f"1️⃣ Quotidien - 100 FCFA/jour\n"
                f"2️⃣ Mensuel - 3 000 FCFA/mois\n"
                f"3️⃣ Unique - 22 205 FCFA\n\n"
                f"Plafond total : 22 205 FCFA\n\n"
                f"0️⃣ Retour"
            )
        
        self.wa_service.send_text_message(self.session.phone_number, message)
    
    def handle_pass_choix_recurrence(self):
        """Gère le choix de récurrence"""
        recurrences = {
            "1": "quotidien",
            "2": "mensuel",
            "3": "unique",
            "quotidien": "quotidien",
            "mensuel": "mensuel",
            "unique": "unique",
        }

        choix = self._normalize_choice()

        if choix == "0":
            self.session.current_state = 'PASS_CHOIX_PRODUIT'
            self.session.save()
            self.show_pass_produits()
            return

        if choix not in recurrences:
            self.send_error("Récurrence invalide. Choisissez 1, 2, 3 ou 0.")
            return

        recurrence = recurrences[choix]
        self.session.update_context('type_recurrence', recurrence)
        self.session.current_state = 'PASS_COLLECTE_NOM'
        self.session.save()
        
        self.wa_service.send_text_message(
            self.session.phone_number,
            f"✅ Récurrence: {recurrence}\n\n📝 Nom du client ?\n\n0️⃣ Retour"
        )
    
    def handle_pass_collecte_nom(self):
        """Collecte le nom du client"""
        if self._normalize_choice() == "0":
            self.session.current_state = 'PASS_CHOIX_RECURRENCE'
            self.session.save()
            # Renvoyer les options de récurrence
            produit_nom = self.session.get_context('produit_nom', '')
            if produit_nom == 'BATELA':
                msg = (
                    f"📅 Choisissez la récurrence :\n\n"
                    f"1️⃣ Quotidien - 200 FCFA/jour\n"
                    f"2️⃣ Mensuel - 6 000 FCFA/mois\n"
                    f"3️⃣ Unique - 72 200 FCFA\n\n0️⃣ Retour"
                )
            else:
                msg = (
                    f"📅 Choisissez la récurrence :\n\n"
                    f"1️⃣ Quotidien - 100 FCFA/jour\n"
                    f"2️⃣ Mensuel - 3 000 FCFA/mois\n"
                    f"3️⃣ Unique - 22 205 FCFA\n\n0️⃣ Retour"
                )
            self.wa_service.send_text_message(self.session.phone_number, msg)
            return
        
        self.session.update_context('client_nom', self.message_text.upper())
        self.session.current_state = 'PASS_COLLECTE_PRENOM'
        self.session.save()
        
        self.wa_service.send_text_message(
            self.session.phone_number,
            f"✅ Nom: {self.message_text.upper()}\n\n📝 Prénom du client ?\n\n0️⃣ Retour"
        )
    
    def handle_pass_collecte_prenom(self):
        """Collecte le prénom"""
        if self._normalize_choice() == "0":
            self.session.current_state = 'PASS_COLLECTE_NOM'
            self.session.save()
            self.wa_service.send_text_message(
                self.session.phone_number,
                f"📝 Nom du client ?\n\n0️⃣ Retour"
            )
            return
        
        self.session.update_context('client_prenom', self.message_text.capitalize())
        self.session.current_state = 'PASS_COLLECTE_TELEPHONE'
        self.session.save()
        
        self.wa_service.send_text_message(
            self.session.phone_number,
            f"✅ Prénom: {self.message_text.capitalize()}\n\n"
            f"📞 Téléphone du client ?\n"
            f"Format: +242061234567 ou 061234567\n\n"
            f"0️⃣ Retour"
        )
    
    def handle_pass_collecte_telephone(self):
        """Collecte le téléphone"""
        if self._normalize_choice() == "0":
            self.session.current_state = 'PASS_COLLECTE_PRENOM'
            self.session.save()
            self.wa_service.send_text_message(
                self.session.phone_number,
                f"📝 Prénom du client ?\n\n0️⃣ Retour"
            )
            return
        
        # Normaliser téléphone
        phone = self.message_text.strip()
        if not phone.startswith('+242'):
            phone = '+242' + phone.lstrip('0')
        
        self.session.update_context('client_telephone', phone)
        self.session.current_state = 'PASS_COLLECTE_NAISSANCE'
        self.session.save()
        
        self.wa_service.send_text_message(
            self.session.phone_number,
            f"✅ Téléphone: {phone}\n\n"
            f"🎂 Date de naissance ?\n"
            f"Format: JJ/MM/AAAA\n"
            f"Exemple: 15/05/1990\n\n"
            f"0️⃣ Retour"
        )
    
    def handle_pass_collecte_naissance(self):
        """Collecte date de naissance"""
        if self._normalize_choice() == "0":
            self.session.current_state = 'PASS_COLLECTE_TELEPHONE'
            self.session.save()
            self.wa_service.send_text_message(
                self.session.phone_number,
                f"📞 Téléphone du client ?\nFormat: +242061234567 ou 061234567\n\n0️⃣ Retour"
            )
            return
        
        # Valider format date
        from datetime import datetime
        try:
            date_obj = datetime.strptime(self.message_text, '%d/%m/%Y')
            date_iso = date_obj.strftime('%Y-%m-%d')
            
            self.session.update_context('client_date_naissance', date_iso)
            self.session.current_state = 'PASS_CONFIRMATION'
            self.session.save()
            
            # Afficher récapitulatif
            self.show_pass_recapitulatif()
        
        except ValueError:
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Format de date invalide.\n\n"
                "Utilisez: JJ/MM/AAAA\n"
                "Exemple: 15/05/1990\n\n"
                "0️⃣ Retour"
            )
    
    def show_pass_recapitulatif(self):
        """Affiche le récapitulatif avant confirmation"""
        ctx = self.session.context
        
        # Détails récurrence
        recurrence_details = {
            'quotidien': '200 FCFA/jour' if ctx['produit_nom'] == 'BATELA' else '100 FCFA/jour',
            'mensuel': '6 000 FCFA/mois' if ctx['produit_nom'] == 'BATELA' else '3 000 FCFA/mois',
            'unique': '72 200 FCFA' if ctx['produit_nom'] == 'BATELA' else '22 205 FCFA'
        }
        
        message = (
            f"📋 RÉCAPITULATIF SOUSCRIPTION\n\n"
            f"👤 Client :\n"
            f"• Nom : {ctx['client_nom']}\n"
            f"• Prénom : {ctx['client_prenom']}\n"
            f"• Téléphone : {ctx['client_telephone']}\n"
            f"• Né(e) le : {ctx['client_date_naissance']}\n\n"
            f"📦 Produit :\n"
            f"• PASS {ctx['produit_nom']}\n"
            f"• Récurrence : {ctx['type_recurrence']}\n"
            f"• Montant : {recurrence_details[ctx['type_recurrence']]}\n\n"
            f"✅ Valider la souscription ?\n\n"
            f"O - Oui, créer\n"
            f"N - Non, annuler\n"
            f"0️⃣ Retour menu"
        )
        
        self.wa_service.send_text_message(self.session.phone_number, message)
    
    def handle_pass_confirmation(self):
        """Gère la confirmation finale"""
        choix = self._normalize_choice()

        if choix == "0":
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
            return

        if choix in ("n", "non"):
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Souscription annulée.\n\nRetour au menu..."
            )
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
            return

        if choix not in ("o", "oui"):
            self.send_error("Répondez O (oui) ou N (non).")
            return

        # Créer la souscription via API
        self.creer_souscription_pass()
    
    def creer_souscription_pass(self):
        """Appelle l'API pour créer la souscription"""
        try:
            ctx = self.session.context
            token = ctx.get('access_token')
            
            payload = {
                "produit_pass_id": ctx['produit_pass_id'],
                "type_recurrence": ctx['type_recurrence'],
                "operateur": "mtn_money",  # Par défaut
                "client": {
                    "nom": ctx['client_nom'],
                    "prenom": ctx['client_prenom'],
                    "telephone": ctx['client_telephone'],
                    "date_naissance": ctx['client_date_naissance']
                }
            }
            
            response = requests.post(
                f"{settings.API_BASE_URL}/api/v1/paiements/nouvelle-souscription/",
                json=payload,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code in [200, 201]:
                data = response.json()['data']
                
                message = (
                    f"✅ SOUSCRIPTION CRÉÉE !\n\n"
                    f"📄 Police : {data['souscription']['numero_souscription']}\n"
                    f"📦 Produit : {data['souscription']['produit']}\n"
                    f"💰 Montant : {data['paiement']['montant']} FCFA\n\n"
                    f"📱 Paiement initié sur :\n"
                    f"{data['client']['telephone']}\n\n"
                    f"⏳ En attente de confirmation client...\n\n"
                    f"Réf : {data['paiement']['numero_transaction']}\n\n"
                    f"Le client doit valider le paiement Mobile Money."
                )
                
                self.wa_service.send_text_message(self.session.phone_number, message)

                # Retour au menu
                self.session.current_state = 'MENU_PRINCIPAL'
                self.session.context = {}
                self.session.save()
                self.show_menu_principal()
            
            else:
                error = response.json().get('error', 'Erreur inconnue')
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    f"❌ Erreur lors de la création :\n{error}\n\nRetour au menu..."
                )
                self.session.current_state = 'MENU_PRINCIPAL'
                self.session.save()
                self.show_menu_principal()
        
        except Exception as e:
            logger.error(f"❌ Erreur création souscription: {e}")
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Erreur technique. Réessayez plus tard."
            )
    
    # ========================================
    # COMMISSIONS
    # ========================================
    
    def show_commissions(self):
        """Affiche les commissions de l'agent"""
        try:
            token = self.session.get_context('access_token')
            
            response = requests.get(
                f"{settings.API_BASE_URL}/api/v1/agents/{self.session.get_context('agent_id')}/stats/",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                data = response.json()['data']
                
                message = (
                    f"💰 VOS COMMISSIONS\n\n"
                    f"👤 {data['nom_complet']}\n"
                    f"🆔 {data['matricule']}\n"
                    f"📍 {data['agence']}\n\n"
                    f"📊 STATISTIQUES :\n"
                    f"• Souscriptions totales : {data['nombre_souscriptions']}\n"
                    f"• Souscriptions actives : {data['souscriptions_actives']}\n"
                    f"• Ce mois : {data['souscriptions_ce_mois']}\n\n"
                    f"💵 CHIFFRE D'AFFAIRES :\n"
                    f"• Total : {int(data['chiffre_affaires'])} FCFA\n"
                    f"• BATELA : {int(data['chiffre_affaires_par_produit']['ca_batela'])} FCFA\n"
                    f"• KIMIA : {int(data['chiffre_affaires_par_produit']['ca_kimia'])} FCFA\n"
                    f"• SALISA : {int(data['chiffre_affaires_par_produit']['ca_salisa'])} FCFA\n\n"
                    f"💰 COMMISSIONS ({data['taux_commission']}%) :\n"
                    f"• Solde : {data['solde_commissions']} FCFA\n\n"
                    f"0️⃣ Retour menu"
                )
                
                self.wa_service.send_text_message(self.session.phone_number, message)
            
            else:
                self.send_error("Impossible de récupérer vos commissions.")
        
        except Exception as e:
            logger.error(f"❌ Erreur commissions: {e}")
            self.send_error("Erreur technique.")
    
    def handle_commissions(self):
        """Gère le menu commissions"""
        if self._normalize_choice() == "0":
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
        else:
            self.show_commissions()
    
    # ========================================
    # FLOW SIMULATEUR COMPLET
    # ========================================
    
    def show_simulateur_produits(self):
        """Affiche les produits du simulateur"""
        self.wa_service.send_interactive_list(
            self.session.phone_number,
            "🧮 SIMULATEUR PRODUITS NSIA\n\nChoisissez le produit à simuler :",
            "📋 Voir les produits",
            [
                {
                    "title": "Produits Classiques",
                    "rows": [
                        {
                            "id": "retraite",
                            "title": "NSIA Retraite",
                            "description": "Complément retraite + décès"
                        },
                        {
                            "id": "pension_securite",
                            "title": "Pension Sécurité",
                            "description": "Protection niveau sécurité"
                        },
                        {
                            "id": "pension_confort",
                            "title": "Pension Confort",
                            "description": "Protection niveau confort"
                        },
                        {
                            "id": "pension_renfort",
                            "title": "Pension Renfort",
                            "description": "Protection niveau renfort"
                        },
                        {
                            "id": "prevoyance",
                            "title": "Prévoyance Décès",
                            "description": "Couverture décès + invalidité"
                        },
                        {
                            "id": "etudes",
                            "title": "NSIA Études",
                            "description": "Financement études enfants"
                        }
                    ]
                }
            ]
        )
    
    def handle_simulateur_choix(self):
        """Gère le choix du produit simulateur"""
        produits_map = {
            "1": "retraite",
            "2": "pension_securite",
            "3": "pension_confort",
            "4": "pension_renfort",
            "5": "prevoyance",
            "6": "etudes",
            # IDs directs des listes interactives
            "retraite": "retraite",
            "pension_securite": "pension_securite",
            "pension_confort": "pension_confort",
            "pension_renfort": "pension_renfort",
            "prevoyance": "prevoyance",
            "etudes": "etudes"
        }

        choix = self._normalize_choice()
        
        if choix == "0":
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
            return
        
        if choix not in produits_map:
            self.send_error("Produit invalide. Choisissez 1-6 ou 0.")
            return
        
        produit_code = produits_map[choix]
        
        # Sauvegarder le produit choisi
        self.session.update_context('simulateur_produit', produit_code)
        self.session.current_state = 'SIMULATEUR_COLLECTE'
        self.session.save()
        
        # Afficher le formulaire selon le produit
        self.afficher_formulaire_simulation(produit_code)
    
    def afficher_formulaire_simulation(self, produit_code):
        """Affiche le formulaire de collecte selon le produit"""
        
        formulaires = {
            'retraite': {
                'titre': 'NSIA RETRAITE',
                'instructions': (
                    "📋 Informations requises :\n\n"
                    "1️⃣ Nom du client\n"
                    "2️⃣ Prénom du client\n"
                    "3️⃣ Téléphone\n"
                    "4️⃣ Âge actuel\n"
                    "5️⃣ Prime mensuelle souhaitée (FCFA)\n"
                    "6️⃣ Capital décès (FCFA)\n"
                    "7️⃣ Durée cotisation (années)\n\n"
                    "📝 Commençons par le nom du client :"
                )
            },
            'pension_securite': {
                'titre': 'NSIA PENSION SÉCURITÉ',
                'instructions': (
                    "📋 Informations requises :\n\n"
                    "1️⃣ Nom du client\n"
                    "2️⃣ Prénom du client\n"
                    "3️⃣ Téléphone\n"
                    "4️⃣ Âge actuel\n"
                    "5️⃣ Pension mensuelle souhaitée (FCFA)\n"
                    "6️⃣ Durée couverture (années)\n\n"
                    "📝 Commençons par le nom du client :"
                )
            },
            'pension_confort': {
                'titre': 'NSIA PENSION CONFORT',
                'instructions': (
                    "📋 Informations requises :\n\n"
                    "1️⃣ Nom du client\n"
                    "2️⃣ Prénom du client\n"
                    "3️⃣ Téléphone\n"
                    "4️⃣ Âge actuel\n"
                    "5️⃣ Pension mensuelle souhaitée (FCFA)\n"
                    "6️⃣ Durée couverture (années)\n\n"
                    "📝 Commençons par le nom du client :"
                )
            },
            'pension_renfort': {
                'titre': 'NSIA PENSION RENFORT',
                'instructions': (
                    "📋 Informations requises :\n\n"
                    "1️⃣ Nom du client\n"
                    "2️⃣ Prénom du client\n"
                    "3️⃣ Téléphone\n"
                    "4️⃣ Âge actuel\n"
                    "5️⃣ Pension mensuelle souhaitée (FCFA)\n"
                    "6️⃣ Durée couverture (années)\n\n"
                    "📝 Commençons par le nom du client :"
                )
            },
            'prevoyance': {
                'titre': 'NSIA PRÉVOYANCE DÉCÈS',
                'instructions': (
                    "📋 Informations requises :\n\n"
                    "1️⃣ Nom du client\n"
                    "2️⃣ Prénom du client\n"
                    "3️⃣ Téléphone\n"
                    "4️⃣ Âge actuel\n"
                    "5️⃣ Capital décès souhaité (FCFA)\n"
                    "6️⃣ Durée couverture (années)\n\n"
                    "📝 Commençons par le nom du client :"
                )
            },
            'etudes': {
                'titre': 'NSIA ÉTUDES',
                'instructions': (
                    "📋 Informations requises :\n\n"
                    "1️⃣ Nom du parent\n"
                    "2️⃣ Prénom du parent\n"
                    "3️⃣ Téléphone\n"
                    "4️⃣ Âge du parent\n"
                    "5️⃣ Âge de l'enfant\n"
                    "6️⃣ Rente annuelle études (FCFA)\n"
                    "7️⃣ Durée paiement primes (années)\n"
                    "8️⃣ Durée études (années)\n\n"
                    "📝 Commençons par le nom du parent :"
                )
            }
        }
        
        formulaire = formulaires.get(produit_code)
        
        if formulaire:
            # Initialiser le contexte de collecte
            self.session.update_context('simulateur_etape', 'nom')
            self.session.update_context('simulateur_data', {})
            
            message = f"🎯 {formulaire['titre']}\n\n{formulaire['instructions']}\n\n0️⃣ Retour"
            self.wa_service.send_text_message(self.session.phone_number, message)
    
    def handle_simulateur_collecte(self):
        """Gère la collecte progressive des données de simulation"""
        etape = self.session.get_context('simulateur_etape', 'nom')

        # Si on est à la confirmation, déléguer au handler de confirmation
        if etape == 'confirmation':
            self.handle_simulateur_confirmation()
            return

        if self._normalize_choice() == "0":
            self.session.current_state = 'SIMULATEUR_CHOIX'
            self.session.save()
            self.show_simulateur_produits()
            return
        produit = self.session.get_context('simulateur_produit')
        data = self.session.get_context('simulateur_data', {})
        
        # Mapping des étapes selon le produit
        etapes_retraite = ['nom', 'prenom', 'telephone', 'age', 'prime_mensuelle', 'capital_deces', 'duree']
        etapes_pension = ['nom', 'prenom', 'telephone', 'age', 'pension_mensuelle', 'duree_couverture']
        etapes_prevoyance = ['nom', 'prenom', 'telephone', 'age', 'capital_deces', 'duree_couverture']
        etapes_etudes = ['nom', 'prenom', 'telephone', 'age_parent', 'age_enfant', 'rente_annuelle', 'duree_paiement', 'duree_service']
        
        # Déterminer les étapes selon le produit
        if produit == 'retraite':
            etapes = etapes_retraite
        elif 'pension' in produit:
            etapes = etapes_pension
        elif produit == 'prevoyance':
            etapes = etapes_prevoyance
        elif produit == 'etudes':
            etapes = etapes_etudes
        else:
            etapes = []
        
        # Sauvegarder la donnée actuelle
        if etape == 'nom':
            data['nom'] = self.message_text.upper()
            self.session.update_context('simulateur_data', data)
            self.session.update_context('simulateur_etape', 'prenom')
            self.session.save()
            self.wa_service.send_text_message(
                self.session.phone_number,
                f"✅ Nom: {data['nom']}\n\n📝 Prénom du client ?\n\n0️⃣ Retour"
            )
        
        elif etape == 'prenom':
            data['prenom'] = self.message_text.capitalize()
            self.session.update_context('simulateur_data', data)
            self.session.update_context('simulateur_etape', 'telephone')
            self.session.save()
            self.wa_service.send_text_message(
                self.session.phone_number,
                f"✅ Prénom: {data['prenom']}\n\n📞 Téléphone ?\nFormat: +242061234567 ou 061234567\n\n0️⃣ Retour"
            )
        
        elif etape == 'telephone':
            phone = self.message_text.strip()
            if not phone.startswith('+242'):
                phone = '+242' + phone.lstrip('0')
            data['telephone'] = phone
            self.session.update_context('simulateur_data', data)
            
            # Prochaine étape selon le produit
            if produit == 'etudes':
                self.session.update_context('simulateur_etape', 'age_parent')
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    f"✅ Téléphone: {phone}\n\n🎂 Âge du parent ?\n\n0️⃣ Retour"
                )
            else:
                self.session.update_context('simulateur_etape', 'age')
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    f"✅ Téléphone: {phone}\n\n🎂 Âge du client ?\n\n0️⃣ Retour"
                )
            self.session.save()
        
        elif etape in ['age', 'age_parent']:
            try:
                age = int(self.message_text)
                if age < 18 or age > 65:
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        "❌ Âge invalide (18-65 ans).\n\nRéessayez :"
                    )
                    return
                
                if etape == 'age_parent':
                    data['age_parent'] = age
                    self.session.update_context('simulateur_data', data)
                    self.session.update_context('simulateur_etape', 'age_enfant')
                    self.session.save()
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Âge parent: {age} ans\n\n👶 Âge de l'enfant ?\n\n0️⃣ Retour"
                    )
                else:
                    data['age'] = age
                    self.session.update_context('simulateur_data', data)
                    
                    # Prochaine étape selon produit
                    if produit == 'retraite':
                        self.session.update_context('simulateur_etape', 'prime_mensuelle')
                        self.wa_service.send_text_message(
                            self.session.phone_number,
                            f"✅ Âge: {age} ans\n\n💰 Prime mensuelle souhaitée (FCFA) ?\n\n0️⃣ Retour"
                        )
                    elif 'pension' in produit:
                        self.session.update_context('simulateur_etape', 'pension_mensuelle')
                        self.wa_service.send_text_message(
                            self.session.phone_number,
                            f"✅ Âge: {age} ans\n\n💰 Pension mensuelle souhaitée (FCFA) ?\n\n0️⃣ Retour"
                        )
                    elif produit == 'prevoyance':
                        self.session.update_context('simulateur_etape', 'capital_deces')
                        self.wa_service.send_text_message(
                            self.session.phone_number,
                            f"✅ Âge: {age} ans\n\n💰 Capital décès souhaité (FCFA) ?\n\n0️⃣ Retour"
                        )
                    self.session.save()
            
            except ValueError:
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Âge invalide. Entrez un nombre.\n\nRéessayez :"
                )
        
        elif etape == 'age_enfant':
            try:
                age = int(self.message_text)
                if age < 0 or age > 18:
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        "❌ Âge invalide (0-18 ans).\n\nRéessayez :"
                    )
                    return
                
                data['age_enfant'] = age
                self.session.update_context('simulateur_data', data)
                self.session.update_context('simulateur_etape', 'rente_annuelle')
                self.session.save()
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    f"✅ Âge enfant: {age} ans\n\n💰 Rente annuelle études (FCFA) ?\n\n0️⃣ Retour"
                )
            except ValueError:
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Âge invalide. Entrez un nombre.\n\nRéessayez :"
                )
        
        elif etape in ['prime_mensuelle', 'pension_mensuelle', 'capital_deces', 'rente_annuelle']:
            try:
                montant = float(self.message_text.replace(' ', '').replace(',', ''))
                
                data[etape] = montant
                self.session.update_context('simulateur_data', data)
                
                # Prochaine étape
                if etape == 'prime_mensuelle':
                    self.session.update_context('simulateur_etape', 'capital_deces')
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Prime mensuelle: {int(montant):,} FCFA\n\n💰 Capital décès (FCFA) ?\n\n0️⃣ Retour"
                    )
                elif etape == 'pension_mensuelle':
                    self.session.update_context('simulateur_etape', 'duree_couverture')
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Pension mensuelle: {int(montant):,} FCFA\n\n⏱️ Durée couverture (années) ?\n\n0️⃣ Retour"
                    )
                elif etape == 'capital_deces' and produit == 'retraite':
                    self.session.update_context('simulateur_etape', 'duree')
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Capital décès: {int(montant):,} FCFA\n\n⏱️ Durée cotisation (années) ?\n\n0️⃣ Retour"
                    )
                elif etape == 'capital_deces' and produit == 'prevoyance':
                    self.session.update_context('simulateur_etape', 'duree_couverture')
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Capital décès: {int(montant):,} FCFA\n\n⏱️ Durée couverture (années) ?\n\n0️⃣ Retour"
                    )
                elif etape == 'rente_annuelle':
                    self.session.update_context('simulateur_etape', 'duree_paiement')
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Rente annuelle: {int(montant):,} FCFA\n\n⏱️ Durée paiement primes (années) ?\n\n0️⃣ Retour"
                    )
                
                self.session.save()
            
            except ValueError:
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Montant invalide. Entrez un nombre.\n\nRéessayez :"
                )
        
        elif etape in ['duree', 'duree_couverture', 'duree_paiement']:
            try:
                duree = int(self.message_text)
                if duree < 1 or duree > 50:
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        "❌ Durée invalide (1-50 ans).\n\nRéessayez :"
                    )
                    return
                
                data[etape] = duree
                self.session.update_context('simulateur_data', data)
                
                # Si produit études et dernière étape de paiement
                if etape == 'duree_paiement' and produit == 'etudes':
                    self.session.update_context('simulateur_etape', 'duree_service')
                    self.session.save()
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        f"✅ Durée paiement: {duree} ans\n\n⏱️ Durée études/service (années) ?\n\n0️⃣ Retour"
                    )
                else:
                    # Terminé - afficher récapitulatif
                    self.session.save()
                    self.afficher_recapitulatif_simulation()
            
            except ValueError:
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Durée invalide. Entrez un nombre.\n\nRéessayez :"
                )
        
        elif etape == 'duree_service':
            try:
                duree = int(self.message_text)
                if duree < 1 or duree > 20:
                    self.wa_service.send_text_message(
                        self.session.phone_number,
                        "❌ Durée invalide (1-20 ans).\n\nRéessayez :"
                    )
                    return
                
                data['duree_service'] = duree
                self.session.update_context('simulateur_data', data)
                self.session.save()
                
                # Terminé - afficher récapitulatif
                self.afficher_recapitulatif_simulation()
            
            except ValueError:
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    "❌ Durée invalide. Entrez un nombre.\n\nRéessayez :"
                )
    
    def afficher_recapitulatif_simulation(self):
        """Affiche le récapitulatif avant calcul"""
        data = self.session.get_context('simulateur_data', {})
        produit = self.session.get_context('simulateur_produit')
        
        produits_noms = {
            'retraite': 'NSIA RETRAITE',
            'pension_securite': 'PENSION SÉCURITÉ',
            'pension_confort': 'PENSION CONFORT',
            'pension_renfort': 'PENSION RENFORT',
            'prevoyance': 'PRÉVOYANCE DÉCÈS',
            'etudes': 'NSIA ÉTUDES'
        }
        
        message = f"📋 RÉCAPITULATIF - {produits_noms.get(produit, produit.upper())}\n\n"
        message += f"👤 Client :\n"
        message += f"• {data.get('prenom', '')} {data.get('nom', '')}\n"
        message += f"• {data.get('telephone', '')}\n"
        
        if produit == 'retraite':
            message += f"\n💼 Paramètres :\n"
            message += f"• Âge : {data.get('age')} ans\n"
            message += f"• Prime mensuelle : {int(data.get('prime_mensuelle', 0)):,} FCFA\n"
            message += f"• Capital décès : {int(data.get('capital_deces', 0)):,} FCFA\n"
            message += f"• Durée : {data.get('duree')} ans\n"
        
        elif 'pension' in produit:
            message += f"\n💼 Paramètres :\n"
            message += f"• Âge : {data.get('age')} ans\n"
            message += f"• Pension mensuelle : {int(data.get('pension_mensuelle', 0)):,} FCFA\n"
            message += f"• Durée couverture : {data.get('duree_couverture')} ans\n"
        
        elif produit == 'prevoyance':
            message += f"\n💼 Paramètres :\n"
            message += f"• Âge : {data.get('age')} ans\n"
            message += f"• Capital décès : {int(data.get('capital_deces', 0)):,} FCFA\n"
            message += f"• Durée couverture : {data.get('duree_couverture')} ans\n"
        
        elif produit == 'etudes':
            message += f"\n💼 Paramètres :\n"
            message += f"• Âge parent : {data.get('age_parent')} ans\n"
            message += f"• Âge enfant : {data.get('age_enfant')} ans\n"
            message += f"• Rente annuelle : {int(data.get('rente_annuelle', 0)):,} FCFA\n"
            message += f"• Durée paiement : {data.get('duree_paiement')} ans\n"
            message += f"• Durée études : {data.get('duree_service')} ans\n"
        
        message += f"\n✅ Calculer la simulation ?\n\n"
        message += f"O - Oui, calculer\n"
        message += f"N - Non, recommencer\n"
        message += f"0️⃣ Retour menu"
        
        self.session.update_context('simulateur_etape', 'confirmation')
        self.session.save()
        
        self.wa_service.send_text_message(self.session.phone_number, message)
    
    def handle_simulateur_confirmation(self):
        """Gère la confirmation du calcul"""
        choix = self._normalize_choice()

        if choix == "0":
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
            return

        if choix in ("n", "non"):
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Simulation annulée.\n\nRetour au menu..."
            )
            self.session.current_state = 'MENU_PRINCIPAL'
            self.session.save()
            self.show_menu_principal()
            return

        if choix not in ("o", "oui"):
            self.send_error("Répondez O (oui) ou N (non).")
            return

        # Lancer le calcul
        self.calculer_simulation()
    
    def calculer_simulation(self):
        """Appelle l'API simulateur pour calculer"""
        try:
            produit = self.session.get_context('simulateur_produit')
            data = self.session.get_context('simulateur_data', {})
            token = self.session.get_context('access_token')
            
            # Préparer le payload selon le produit
            if produit == 'retraite':
                endpoint = '/calculateur/retraite/calculer/'
                parametres = {
                    'prime_periodique_commerciale': data['prime_mensuelle'],
                    'capital_deces': data['capital_deces'],
                    'duree': data['duree'],
                    'age': data['age'],
                    'periodicite': 'Mensuelle'
                }
            
            elif 'pension' in produit:
                endpoint = '/calculateur/pensions/calculer/'
                type_pension_map = {
                    'pension_securite': 'pension_securite',
                    'pension_confort': 'pension_confort',
                    'pension_renfort': 'pension_renfort'
                }
                parametres = {
                    'type_pension': type_pension_map[produit],
                    'age': data['age'],
                    'montant_mensuel_pension': data['pension_mensuelle'],
                    'duree_couverture': data['duree_couverture'],
                    'periodicite': 'Mensuelle'
                }
            
            elif produit == 'prevoyance':
                endpoint = '/calculateur/prevoyance/calculer/'
                parametres = {
                    'age': data['age'],
                    'capital_deces': data['capital_deces'],
                    'duree': data['duree_couverture']
                }
            
            elif produit == 'etudes':
                endpoint = '/calculateur/etudes/calculer/'
                parametres = {
                    'age_parent': data['age_parent'],
                    'age_enfant': data.get('age_enfant', 0),
                    'montant_rente': data['rente_annuelle'],
                    'duree_paiement': data['duree_paiement'],
                    'duree_service': data['duree_service']
                }
            
            else:
                self.send_error("Produit non supporté.")
                return
            
            # Appeler l'API
            response = requests.post(
                f"{settings.API_BASE_URL}/api/v1/simulateur{endpoint}",
                json={'parametres_simulation': parametres},
                headers={'Authorization': f'Bearer {token}'}
            )
            
            if response.status_code == 200:
                resultat = response.json()
                
                # Sauvegarder la simulation
                self.sauvegarder_simulation(resultat, parametres)
                
                # Afficher résultats
                self.afficher_resultats_simulation(resultat)
            
            else:
                error = response.json().get('error', 'Erreur calcul')
                self.wa_service.send_text_message(
                    self.session.phone_number,
                    f"❌ Erreur lors du calcul :\n{error}\n\nRetour au menu..."
                )
                self.session.current_state = 'MENU_PRINCIPAL'
                self.session.save()
                self.show_menu_principal()
        
        except Exception as e:
            logger.error(f"❌ Erreur calcul simulation: {e}")
            self.wa_service.send_text_message(
                self.session.phone_number,
                "❌ Erreur technique. Réessayez plus tard."
            )
    
    def sauvegarder_simulation(self, resultat, parametres):
        """Sauvegarde la simulation dans la base"""
        try:
            produit = self.session.get_context('simulateur_produit')
            data = self.session.get_context('simulateur_data', {})
            token = self.session.get_context('access_token')
            
            payload = {
                'produit_type': produit,
                'client_nom': data['nom'],
                'client_prenom': data['prenom'],
                'client_telephone': data['telephone'],
                'parametres_simulation': parametres,
                'resultats_simulation': resultat.get('resultats_simulation', {})
            }
            
            response = requests.post(
                f"{settings.API_BASE_URL}/api/v1/simulateur/simulations/",
                json=payload,
                headers={'Authorization': f'Bearer {token}'}
            )
            
            if response.status_code == 201:
                simulation_data = response.json()
                self.session.update_context('derniere_simulation_id', simulation_data.get('id'))
                self.session.update_context('numero_simulation', simulation_data.get('numero_simulation'))
                logger.info(f"✅ Simulation sauvegardée: {simulation_data.get('numero_simulation')}")
        
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde simulation: {e}")
    
    def afficher_resultats_simulation(self, resultat):
        """Affiche les résultats de la simulation"""
        produit = self.session.get_context('simulateur_produit')
        data = self.session.get_context('simulateur_data', {})
        numero_sim = self.session.get_context('numero_simulation', 'N/A')
        
        res = resultat.get('resultats_simulation', {})
        
        produits_noms = {
            'retraite': 'NSIA RETRAITE',
            'pension_securite': 'PENSION SÉCURITÉ',
            'pension_confort': 'PENSION CONFORT',
            'pension_renfort': 'PENSION RENFORT',
            'prevoyance': 'PRÉVOYANCE DÉCÈS',
            'etudes': 'NSIA ÉTUDES'
        }
        
        message = f"✅ SIMULATION CALCULÉE\n\n"
        message += f"📄 Réf: {numero_sim}\n"
        message += f"📦 Produit: {produits_noms.get(produit, produit.upper())}\n"
        message += f"👤 Client: {data['prenom']} {data['nom']}\n\n"
        message += f"💰 RÉSULTATS :\n\n"
        
        if produit == 'retraite':
            message += f"• Capital garanti : {int(res.get('capital_garanti', 0)):,} FCFA\n"
            message += f"• Prime totale : {int(res.get('prime_totale', 0)):,} FCFA\n"
            message += f"• Prime épargne : {int(res.get('prime_epargne', 0)):,} FCFA\n"
            message += f"• Prime décès : {int(res.get('prime_deces', 0)):,} FCFA\n"
        
        elif 'pension' in produit:
            message += f"• prime_totale : {int(res.get('prime_totale', 0)):,} FCFA\n"
            message += f"• duree_couverture : {int(res.get('duree_couverture', 0)):,} ans\n"
            message += f"• duree_service : {int(res.get('duree_service', 0)):,} FCFA\n"
            message += f"• periodicite : {res.get('periodicite', 'N/A')} \n"
        
        elif produit == 'prevoyance':
            message += f"• Prime_Commerciale : {int(res.get('Prime_Commerciale', 0)):,} FCFA\n"
            message += f"• Frais_Accessoire : {int(res.get('Frais_Accessoire', 0)):,} FCFA\n"
            message += f"• total_prime_periodique : {int(res.get('total_prime_periodique', 0)):,} FCFA\n"
            message += f"• Capital décès : {int(res.get('capital_deces', 0)):,} FCFA\n"
            #message += f"• Durée : {res.get('duree', 'N/A')} ans\n"
        
        elif produit == 'etudes':
            message += f"• Prime annuelle : {int(res.get('prime_annuelle', 0)):,} FCFA\n"
            message += f"• Prime mensuelle : {int(res.get('prime_mensuelle', 0)):,} FCFA\n"
            message += f"• Rente annuelle : {int(res.get('montant_rente_annuel', 0)):,} FCFA\n"
            message += f"• Durée paiement : {res.get('duree_paiement', 'N/A')} ans\n"
            message += f"• Durée service : {res.get('duree_service', 'N/A')} ans\n"
        
        message += f"\n✅ Simulation sauvegardée avec succès !\n\n"
        message += f"📱 Le client recevra les détails par SMS.\n\n"
        message += f"0️⃣ Retour menu"
        
        self.wa_service.send_text_message(self.session.phone_number, message)

        # Retour au menu
        self.session.current_state = 'MENU_PRINCIPAL'
        self.session.context = {}
        self.session.save()
        self.show_menu_principal()
    
    # ========================================
    # HELPERS
    # ========================================
    
    def send_error(self, message):
        """Envoie un message d'erreur"""
        self.wa_service.send_text_message(
            self.session.phone_number,
            f"❌ {message}"
        )
    
    def send_welcome(self):
        """Message de bienvenue"""
        self.wa_service.send_text_message(
            self.session.phone_number,
            "🏦 NSIA VIE ASSURANCES\n"
            "Chatbot Commercial WhatsApp\n\n"
            "📱 Pour vous connecter :\n"
            "MATRICULE:MOTDEPASSE\n\n"
            "Exemple:\n"
            "AG-2025-001:monmotdepasse"
        )
