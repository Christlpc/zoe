from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction, IntegrityError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import json
import hashlib
import logging
from .models import WhatsAppSession, WhatsAppMessage
from .handlers import ConversationHandler

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """
    Webhook Wassenger API
    
    GET : Vérification (optionnel pour Wassenger mais gardé pour compatibilité)
    POST : Réception messages
    """
    
    if request.method == "GET":
        # Vérification standard (Meta style)
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        
        return HttpResponse('OK', status=200)
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"📩 Webhook Wassenger reçu: {data.get('event')}")

            # Wassenger envoie l'événement dans 'event' et les données dans 'data'
            event = data.get('event')
            msg_data = data.get('data', {})

            # On ne traite que les nouveaux messages entrants
            if event != 'message:in:new':
                return JsonResponse({'status': 'ignored', 'event': event})

            # Extraire les infos du message
            phone_number = msg_data.get('fromNumber')
            message_id = msg_data.get('id')
            message_type = msg_data.get('type')  # 'chat', 'image', etc.

            # Extraire le texte — gérer les réponses interactives Wassenger
            text = msg_data.get('body', '').strip()

            # Pour les réponses aux listes interactives, utiliser l'ID de la sélection
            list_reply = msg_data.get('listReply') or msg_data.get('list_reply')
            if list_reply and isinstance(list_reply, dict):
                text = list_reply.get('id', '') or list_reply.get('title', '') or text

            # Pour les réponses aux boutons, utiliser l'ID du bouton si disponible
            button_reply = msg_data.get('selectedButtonId') or msg_data.get('buttonReply')
            if button_reply:
                if isinstance(button_reply, dict):
                    text = button_reply.get('id', '') or text
                elif isinstance(button_reply, str):
                    text = button_reply or text

            text = text.strip()

            if not phone_number or not text:
                return JsonResponse({'status': 'invalid_data'})

            # Garantir un message_id pour l'idempotence (PostgreSQL autorise
            # plusieurs NULL dans une colonne unique, ce qui laisserait passer
            # les doublons si Wassenger n'envoie pas d'ID).
            if not message_id:
                raw = f"{phone_number}:{text}:{msg_data.get('timestamp', '')}"
                message_id = f"gen_{hashlib.sha256(raw.encode()).hexdigest()[:20]}"

            # Idempotence atomique : créer le message dans une transaction.
            # La contrainte unique sur whatsapp_message_id empêche les doublons.
            try:
                with transaction.atomic():
                    session, created = WhatsAppSession.objects.get_or_create(
                        phone_number=phone_number,
                        defaults={'is_active': True}
                    )

                    WhatsAppMessage.objects.create(
                        session=session,
                        whatsapp_message_id=message_id,
                        direction='incoming',
                        message_type=message_type or 'chat',
                        content={'text': text, 'raw': data}
                    )
            except IntegrityError:
                logger.info(f"⏭️ Message {message_id} déjà traité, on ignore.")
                return JsonResponse({'status': 'ok', 'detail': 'already processed'})

            # Traiter avec le handler
            handler = ConversationHandler(session, text)
            handler.handle()

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            logger.error(f"❌ Erreur webhook Wassenger: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_session(request):
    """
    Reset une session WhatsApp (pour tests)
    
    POST /api/whatsapp/reset-session/
    {
        "phone_number": "+242061234567"
    }
    """
    try:
        phone = request.data.get('phone_number')
        
        if not phone:
            return JsonResponse({'error': 'phone_number requis'}, status=400)
        
        session = WhatsAppSession.objects.filter(phone_number=phone).first()
        
        if session:
            session.current_state = 'ATTENTE_LOGIN'
            session.reset_context()
            session.agent = None
            session.is_active = True
            session.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Session réinitialisée'
            })
        
        return JsonResponse({
            'success': False,
            'message': 'Session non trouvée'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def sessions_actives(request):
    """
    Liste des sessions WhatsApp actives
    
    GET /api/whatsapp/sessions/
    """
    sessions = WhatsAppSession.objects.filter(is_active=True).order_by('-last_activity')[:20]
    
    data = [
        {
            'phone_number': s.phone_number,
            'agent': s.agent.nom_complet if s.agent else None,
            'current_state': s.current_state,
            'last_activity': s.last_activity.isoformat()
        }
        for s in sessions
    ]
    
    return JsonResponse({
        'total': len(data),
        'sessions': data
    })