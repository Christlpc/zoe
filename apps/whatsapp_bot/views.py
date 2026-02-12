from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import json
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
            
            # Le texte du message (y compris pour les réponses aux boutons/listes dans Wassenger)
            text = msg_data.get('body', '').strip()
            
            if not phone_number or not text:
                return JsonResponse({'status': 'invalid_data'})
            
            # Vérifier si le message a déjà été traité (idempotence)
            if message_id and WhatsAppMessage.objects.filter(whatsapp_message_id=message_id).exists():
                logger.info(f"⏭️ Message {message_id} déjà traité, on ignore.")
                return JsonResponse({'status': 'ok', 'detail': 'already processed'})

            # Créer ou récupérer la session
            session, created = WhatsAppSession.objects.get_or_create(
                phone_number=phone_number,
                defaults={'is_active': True}
            )
            
            # Enregistrer le message dans la DB
            WhatsAppMessage.objects.create(
                session=session,
                whatsapp_message_id=message_id,
                direction='incoming',
                message_type=message_type,
                content={'text': text, 'raw': data}
            )
            
            # Traiter avec le handler existant
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