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

import re
from google import genai


def get_questions(settings):
    """Get questions with V1/V2 format compatibility"""
    questions = settings.get("whatsapp_onboarding_questions", [])[:5]  # Max 5
    if not questions:
        return []
    # V1 format: list of strings -> convert to V2 format
    if isinstance(questions[0], str):
        return [{"text": q, "type": "text", "mandatory": False} for q in questions]
    # V2 format: list of dicts
    return questions


def validate_with_fallback(question_type, answer, bot):
    """
    Validate answer against question type.
    Uses AI validation for all types except 'text' (free-form).
    Accepts answer on any AI failure.
    """
    answer = answer.strip()
    q_type = question_type.lower().strip()
    
    # Free-form text always valid
    if q_type == "text" or q_type == "":
        return True
    
    # Use AI validation for all other types (name, email, phone, custom types)
    try:
        return validate_answer_ai(question_type, answer, bot)
    except Exception as e:
        print(f"AI validation failed, accepting answer: {e}")
        return True  # Accept on AI failure


def validate_answer_ai(question_type, answer, bot):
    """Isolated AI validation - does NOT affect chat history"""
    try:
        client = genai.Client(api_key=bot.gm_key)
        prompt = f'''Is "{answer}" a valid {question_type}?
Respond with ONLY the word "VALID" or "INVALID", nothing else.'''
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        result = response.text.strip().upper()
        return result == "VALID"
    except Exception:
        return True  # Accept on any exception


def handle_onboarding(chat, user_message, wa_service, settings, bot=None):
    """
    Handle onboarding flow V2.
    Returns tuple: (response_message, should_return_early)
    - (message, True) = send message and return
    - (None, False) = onboarding complete, continue to AI
    """
    phone = chat["phone_no"]
    
    # Skip if feature disabled
    if not settings.get("whatsapp_onboarding_enabled"):
        wa_service.complete_onboarding(phone)
        return None, False
    
    # Snapshot questions on first interaction
    if chat.get("onboarding_questions_snapshot") is None:
        questions = get_questions(settings)
        if not questions:
            wa_service.complete_onboarding(phone)
            return None, False
        wa_service.set_snapshot(phone, questions)
        chat["onboarding_questions_snapshot"] = questions
    
    questions = chat["onboarding_questions_snapshot"]
    step = chat.get("onboarding_step", 0)
    attempts = chat.get("onboarding_attempt_count", 0)
    
    # If step == 0, this is the first message - ask first question
    if step == 0:
        wa_service.reset_attempt_and_advance(phone, 1)
        q = questions[0]
        q_text = q.get("text", q) if isinstance(q, dict) else q
        mandatory = q.get("mandatory", False) if isinstance(q, dict) else False
        suffix = "" if mandatory else " (type 'skip' to continue)"
        return f"{q_text}{suffix}", True
    
    # Get previous question (step-1 because step is 1-indexed after first question)
    prev_idx = step - 1
    if prev_idx >= len(questions):
        # All questions answered
        wa_service.complete_onboarding(phone)
        return None, False
    
    prev_q = questions[prev_idx]
    q_text = prev_q.get("text", prev_q) if isinstance(prev_q, dict) else prev_q
    q_type = prev_q.get("type", "text") if isinstance(prev_q, dict) else "text"
    mandatory = prev_q.get("mandatory", False) if isinstance(prev_q, dict) else False
    
    user_input = user_message.strip()
    is_skip = user_input.lower() == "skip" or user_input == ""  # Empty = skip
    
    # Handle skip attempt (including empty input)
    if is_skip:
        if mandatory:
            return "This question is required. Please provide an answer.", True
        else:
            # Save as skipped, advance
            wa_service.save_onboarding_response_v2(phone, prev_q, "skipped")
            wa_service.reset_attempt_and_advance(phone, step + 1)
            # Check if more questions
            if step >= len(questions):
                wa_service.complete_onboarding(phone)
                return None, False
            # Ask next question
            next_q = questions[step]
            next_text = next_q.get("text", next_q) if isinstance(next_q, dict) else next_q
            next_mandatory = next_q.get("mandatory", False) if isinstance(next_q, dict) else False
            suffix = "" if next_mandatory else " (type 'skip' to continue)"
            return f"{next_text}{suffix}", True
    
    # Validate answer
    is_valid = validate_with_fallback(q_type, user_input, bot) if bot else True
    
    if not is_valid:
        if attempts >= 2:  # 3rd attempt (0, 1, 2)
            # Accept anyway after 3 attempts
            is_valid = True
        else:
            # Increment attempts and ask again
            wa_service.increment_attempt(phone)
            return f"Please provide a valid {q_type}. Try again:", True
    
    # Save valid answer and advance
    wa_service.save_onboarding_response_v2(phone, prev_q, user_input)
    wa_service.reset_attempt_and_advance(phone, step + 1)
    
    # Check if more questions
    if step >= len(questions):
        wa_service.complete_onboarding(phone)
        return None, False
    
    # Ask next question
    next_q = questions[step]
    next_text = next_q.get("text", next_q) if isinstance(next_q, dict) else next_q
    next_mandatory = next_q.get("mandatory", False) if isinstance(next_q, dict) else False
    suffix = "" if next_mandatory else " (type 'skip' to continue)"
    return f"{next_text}{suffix}", True


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
                                    # Fetch fresh settings from DB to ensure multi-worker consistency
                                    settings_doc = current_app.db.config.find_one({"id": "settings"}) or {}
                                    # Fallback to config if DB read fails (rare), or empty dict
                                    settings = settings_doc if settings_doc else current_app.config.get('SETTINGS', {})
                                    
                                    response, should_return = handle_onboarding(
                                        chat, user_message, wa_service, settings, current_app.bot
                                    )
                                    if should_return:
                                        send_whatsapp_message(from_number, response)
                                        return jsonify({"status": "ok"}), 200
                                    # Onboarding complete, refresh chat data
                                    chat = wa_service.get_by_phone_no(from_number)
                                
                                # Normal flow continues
                                wa_service.add_message(user_message, from_number, from_number, type="text")
                                current_app.socketio.emit("wa_message", {"sender": from_number, "message": user_message})
                                
                                if not is_admin_enabled(chat):  # Use helper with fallback
                                    # Use locally fetched settings from above (or fetch if missing for edge cases)
                                    if 'settings' not in locals():
                                        settings_doc = current_app.db.config.find_one({"id": "settings"}) or {}
                                        settings = settings_doc if settings_doc else current_app.config.get('SETTINGS', {})
                                    
                                    # Context Injection Logic
                                    if (settings.get("whatsapp_onboarding_use_context") 
                                        and not chat.get("context_injected", False)):
                                        
                                        # Get validated answers
                                        responses = chat.get("onboarding_responses", [])
                                        valid_context_parts = []
                                        
                                        for resp in responses:
                                            # Skip skipped/empty
                                            answer = resp.get("answer", "")
                                            if answer and answer.lower() != "skipped":
                                                # Truncate to 200 chars for safety
                                                safe_answer = answer[:200] + "..." if len(answer) > 200 else answer
                                                q_text = resp.get("question", "Question")
                                                valid_context_parts.append(f"{q_text}: {safe_answer}")
                                        
                                        if valid_context_parts:
                                            context_str = "\n".join(valid_context_parts)
                                            # Prepend context to user message
                                            user_message = f"User provided context:\n{context_str}\n\nUser Message:\n{user_message}"
                                            # Mark injected so we don't do it again
                                            wa_service.set_context_injected(from_number, True)

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

