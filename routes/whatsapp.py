from flask import Flask, current_app, render_template, request, jsonify
import requests
import os
from io import BytesIO
from pydub import AudioSegment
from datetime import datetime, timedelta

from services.admin_service import AdminService
from services.chat_service import ChatService
from services.whatsapp_service import WhatsappService
from . import wa_bp

WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'your_verify_token_here')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
VERSION = 'v24.0'
DEFAULT_ADMIN_ID = os.getenv("DEFAULT_ADMIN_ID")

# Store processed message IDs with timestamps
# Using a dictionary to track when messages were processed
processed_messages = {}
MESSAGE_CACHE_DURATION = timedelta(hours=1)  # Keep message IDs for 1 hour


def cleanup_old_messages():
    """Remove message IDs older than MESSAGE_CACHE_DURATION"""
    current_time = datetime.now()
    expired_ids = [
        msg_id for msg_id, timestamp in processed_messages.items()
        if current_time - timestamp > MESSAGE_CACHE_DURATION
    ]
    for msg_id in expired_ids:
        del processed_messages[msg_id]


def is_duplicate_message(message_id):
    """Check if message has already been processed"""
    cleanup_old_messages()  # Clean up old entries
    
    if message_id in processed_messages:
        # print(f"Duplicate message detected: {message_id}")
        return True
    
    # Mark message as processed
    processed_messages[message_id] = datetime.now()
    return False


def handle_onboarding(chat, user_message, wa_service, settings):
    """
    Handle onboarding flow. Returns question string if continuing, None if complete.
    """
    questions = settings.get("whatsapp_onboarding_questions", [])[:5]  # Max 5
    
    # Skip if feature disabled or no questions
    if not settings.get("whatsapp_onboarding_enabled") or not questions:
        wa_service.complete_onboarding(chat["phone_no"])
        return None
    
    step = chat.get("onboarding_step", 0)
    phone = chat["phone_no"]
    
    # Save previous answer (with bounds check for shrinking questions)
    if step > 0 and step - 1 < len(questions):
        prev_question = questions[step - 1]
        answer = None if user_message.strip().lower() == "skip" else user_message
        wa_service.save_onboarding_response(phone, prev_question, answer)
    
    # Check if all questions answered (or questions shrunk)
    if step >= len(questions):
        wa_service.complete_onboarding(phone)
        return None
    
    # Advance step and return next question
    wa_service.update_onboarding_step(phone, step + 1)
    return f"{questions[step]} (type 'skip' to continue)"


def is_admin_enabled(chat):
    """Check admin_enable with fallback to admin_enabled for backwards compatibility"""
    return chat.get("admin_enable") or chat.get("admin_enabled", False)


@wa_bp.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook for WhatsApp Business API"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        # print("Webhook verified successfully!")
        return challenge, 200
    else:
        # print("Webhook verification failed!")
        return "Forbidden", 403


def detect_audio_format(audio_data):
    """Detect audio format from file signature (magic bytes)"""
    if len(audio_data) < 12:
        return None
    
    # Check common audio format signatures
    if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
        return 'wav'
    elif audio_data[:4] == b'OggS':
        return 'ogg'
    elif audio_data[:3] == b'ID3' or audio_data[:2] == b'\xff\xfb' or audio_data[:2] == b'\xff\xf3':
        return 'mp3'
    elif audio_data[:4] == b'fLaC':
        return 'flac'
    elif audio_data[:4] == b'ftyp' or audio_data[4:8] == b'ftyp':
        return 'mp4'
    
    return None


def convert_to_ogg_opus(audio_data):
    """Convert audio data to OGG Opus format for WhatsApp"""
    try:
        # Detect the audio format
        detected_format = detect_audio_format(audio_data)
        # print(f"Detected audio format: {detected_format}")
        
        # Print first 16 bytes for debugging
        # print(f"First 16 bytes: {audio_data[:16].hex()}")
        
        audio_buffer = BytesIO(audio_data)
        
        # Try to load audio without specifying format first (let pydub detect)
        try:
            if detected_format:
                audio = AudioSegment.from_file(audio_buffer, format=detected_format)
            else:
                # Try common formats
                audio = None
                for fmt in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac']:
                    try:
                        audio_buffer.seek(0)
                        audio = AudioSegment.from_file(audio_buffer, format=fmt)
                        # print(f"Successfully loaded as {fmt}")
                        break
                    except:
                        continue
                
                if audio is None:
                    raise ValueError("Could not detect audio format")
        except Exception as e:
            # print(f"Error loading audio: {e}")
            # Try loading raw PCM data (common for some TTS APIs)
            try:
                audio_buffer.seek(0)
                audio = AudioSegment(
                    data=audio_data,
                    sample_width=2,  # 16-bit
                    frame_rate=24000,  # Common TTS sample rate
                    channels=1
                )
                # print("Loaded as raw PCM data")
            except:
                raise
        
        # Convert to mono if stereo
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Set to 16kHz sample rate (WhatsApp recommendation)
        audio = audio.set_frame_rate(16000)
        
        # Export as OGG with Opus codec
        output_buffer = BytesIO()
        audio.export(
            output_buffer,
            format='ogg',
            codec='libopus',
            parameters=["-strict", "-2"]
        )
        
        output_buffer.seek(0)
        return output_buffer.read()
    
    except Exception as e:
        # print(f"Error converting audio to OGG Opus: {e}")
        import traceback
        traceback.print_exc()
        return None


@wa_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        data = request.get_json()
        print("Received webhook data:", data)
        wa_service = WhatsappService(current_app.db)
        
        # Check if this is a message event
        if data.get('object') == 'whatsapp_business_account':
            entries = data.get('entry', [])
            
            for entry in entries:
                changes = entry.get('changes', [])
                
                for change in changes:
                    value = change.get('value', {})
                    # Check if there are messages
                    if 'messages' in value:
                        messages = value['messages']
                        
                        for message in messages:
                            # Get message ID first to check for duplicates
                            message_id = message.get('id')
                            
                            # Check if this message has already been processed
                            if is_duplicate_message(message_id):
                                # print(f"Ignoring duplicate message: {message_id}")
                                continue  # Skip this message
                            
                            # Get message details
                            from_number = message.get('from')
                            chat = wa_service.get_by_phone_no(from_number)
                            admin = AdminService(current_app.db).get_admin_by_id(DEFAULT_ADMIN_ID)
                            if not chat:
                                current_app.bot.create_chat(from_number, admin)
                            
                            if not chat:
                                wa_service.create(from_number)

                                chat = wa_service.get_by_phone_no(from_number)
                                print("New User")
                            
                            message_type = message.get('type')
                            print(f"Message type: {message_type}")
                            print(f"Message: {message}")
                            
                            # Handle text messages
                            if message_type == 'text':
                                user_message = message.get('text', {}).get('body', '')
                                
                                # ONBOARDING CHECK - before add_message and socket emit
                                if not chat.get("onboarding_complete", True):  # Default True = legacy skip
                                    settings = current_app.config['SETTINGS']
                                    response = handle_onboarding(chat, user_message, wa_service, settings)
                                    if response:
                                        send_whatsapp_message(from_number, response)
                                        return jsonify({"status": "ok"}), 200
                                    # Onboarding complete, refresh chat data
                                    chat = wa_service.get_by_phone_no(from_number)
                                
                                # Normal flow continues
                                wa_service.add_message(user_message, from_number, from_number, type="text")
                                current_app.socketio.emit("wa_message", {"sender": from_number, "message": user_message})
                                
                                if not is_admin_enabled(chat):  # Use helper with fallback
                                    msg, usage = current_app.bot.respond(f"Message from whatsapp: {user_message}", from_number)
                                    print(f"Bot response: {msg}")
                                    wa_service.add_message(msg, from_number, "bot", type="text")
                                    send_whatsapp_message(from_number, msg)
                            
                            # Handle audio messages - audio not supported yet
                            elif message_type == 'audio':
                                send_whatsapp_message(from_number, "Please text instead, audio is not supported at the moment.")
                            
                            # Mark message as read
                            mark_message_read(message_id)
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        # print(f"Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def download_whatsapp_media(media_id):
    """Download media file from WhatsApp"""
    try:
        # Step 1: Get media URL
        url = f"https://graph.facebook.com/{VERSION}/{media_id}"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}"
        }
        
        # print(f"Getting media URL for media_id: {media_id}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        media_url = response.json().get('url')
        
        if not media_url:
            # print("No media URL found in response")
            return None
        
        # print(f"Media URL: {media_url}")
        
        # Step 2: Download the actual media file
        media_response = requests.get(media_url, headers=headers)
        media_response.raise_for_status()
        
        # print(f"Successfully downloaded media: {len(media_response.content)} bytes")
        return media_response.content
    
    except requests.exceptions.RequestException as e:
        # print(f"Error downloading media: {e}")
        import traceback
        traceback.print_exc()
        return None


def send_whatsapp_audio(phone_number, audio_data):
    """Send audio message via WhatsApp"""
    try:
        # Step 1: Upload audio to WhatsApp
        upload_url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/media"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}"
        }
        
        # Create a file-like object from audio bytes
        audio_file = BytesIO(audio_data)
        
        files = {
            'file': ('audio.ogg', audio_file, 'audio/ogg; codecs=opus'),
        }
        
        data = {
            'messaging_product': 'whatsapp'
        }
        
        # print(f"Uploading audio to WhatsApp ({len(audio_data)} bytes)...")
        upload_response = requests.post(upload_url, headers=headers, files=files, data=data)
        upload_response.raise_for_status()
        media_id = upload_response.json().get('id')
        
        if not media_id:
            # print("Failed to upload audio - no media_id returned")
            return None
        
        # print(f"Audio uploaded successfully, media_id: {media_id}")
        
        # Step 2: Send audio message
        send_url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "audio",
            "audio": {
                "id": media_id
            }
        }
        
        # print(f"Sending audio message to {phone_number}...")
        response = requests.post(send_url, headers=headers, json=payload)
        response.raise_for_status()
        # print(f"Audio sent successfully to {phone_number}")
        return response.json()
    
    except requests.exceptions.RequestException as e:
        # print(f"Error sending audio: {e}")
        import traceback
        traceback.print_exc()
        return None


def send_whatsapp_message(phone_number, message):
    """Send a WhatsApp text message using the Facebook Graph API"""
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message
        }
    }
    print(f"Send messgae: {payload} {headers}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"WhatsApp API Response: {response.status_code} {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        return None


def mark_message_read(message_id):
    """Mark a message as read"""
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }
    
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Error marking message as read: {e}")

