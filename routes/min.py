from services.expo_noti import send_push_noti
import markdown
from flask import make_response
from services.notification_service import NotificationService
from flask_mail import Mail
from services.admin_service import AdminService
from datetime import datetime
import requests
from services.timezone import UTCZoneManager
from flask import render_template_string
from services.usage_service import UsageService
import random
from flask import render_template, session, request, jsonify, redirect, url_for, current_app
from flask_socketio import join_room, leave_room, emit
from . import min_bp
from services.user_service import UserService
from services.chat_service import ChatService
from functools import wraps
from services.email_service import send_email
import os
import pytz
import threading
import time
from flask import copy_current_request_context


def handle_bot_response(room_id, message, chat, admin, max_retries=3, retry_delay=1):
    """Handle bot response with retry logic - can be called from multiple endpoints"""
    @copy_current_request_context
    def _bot_response_worker():
        chat_service = ChatService(current_app.db)
        admin_service = AdminService(current_app.db)
        
        for attempt in range(max_retries):
            try:
                msg, usage = current_app.bot.respond(
                    f"Subject of chat: {chat.subject}\n{message}", chat.room_id)
                
                admin_service.update_tokens(admin.admin_id, usage['cost'])

                bot_message = chat_service.add_message(chat.room_id, chat.bot_name, msg)

                current_app.socketio.emit('new_message', {
                    'room_id': chat.room_id,
                    'sender': chat.bot_name,
                    'content': msg,
                    'timestamp': bot_message.timestamp.isoformat()
                }, room=chat.room_id)
                return  # Success, exit retry loop
                
            except Exception as e:
                print(f"Bot response error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    # All retries failed, send error message
                    error_message = chat_service.add_message(chat.room_id, "SYSTEM", 
                                                            "We Apologize, there was an unexpected error, please try again after some time")
                    
                    current_app.socketio.emit('new_message', {
                        'room_id': chat.room_id,
                        'sender': "SYSTEM",
                        'content': "We Apologize, there was an unexpected error, please try again after some time",
                        'timestamp': error_message.timestamp.isoformat()
                    }, room=chat.room_id)
    
    # Start the bot response in a separate thread
    thread = threading.Thread(target=_bot_response_worker)
    thread.daemon = True
    thread.start()


@min_bp.before_request
def before_req():
    path = request.path
    print(session.items())
    print(f"Path: {path}")
    print(f"LastVisit: {session.get('last_visit')}")
    if path.startswith("/min") and (path.split("/")[-1] not in ['auth', 'send_message', 'ping_admin', "send_audio"] and path not in ['/min/', '/min/get-headers'] and "audio_file" not in path):
        session["last_visit"] = path

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for("min.index"))

        user_service = UserService(current_app.db)
        user = user_service.get_user_by_id(session['user_id'])

        if not user:
            return redirect(url_for("min.index"))
        return f(*args, **kwargs)
    return decorated_function


@min_bp.route('/get-headers')
def headers():
    return render_template('user/min-headers.html')


@min_bp.route('/')
def index():
    last_visit = session.get('last_visit')
    print(f"Index - last_visit: {last_visit}")
    
    if last_visit and last_visit not in ['/min/', '/min/get-headers']:
        return redirect(last_visit)
    
    return redirect('/min/onboarding')


@min_bp.route('login/', defaults={'subject': "I need services"}, methods=['GET',"POST"])
@min_bp.route('login/<string:subject>', methods=['GET',"POST"])
def login(subject):
    if request.method == "GET":
        try:
            ip = request.headers.get("X-Real-IP", request.remote_addr)
            ip = ip.split(",")[0]

            geo = requests.get(f"http://ipleak.net/json/{ip}", timeout=3)
            geo = geo.json()
            country = geo.get("country_name", None)
        except Exception as e:
            print(f"Geo lookup error: {e}")
            country = None
        return render_template('user/min-login.html', default_subject=subject, user_country=country)

    elif request.method == "POST":
        session["initial_msg"] = request.form.get("initial_msg")
        subject="I need services"
        try:
            ip = request.headers.get("X-Real-IP", request.remote_addr)
            ip = ip.split(",")[0]

            geo = requests.get(f"http://ipleak.net/json/{ip}", timeout=3)
            geo = geo.json()
            country = geo.get("country_name", None)
        except Exception as e:
            print(f"Geo lookup error: {e}")
            country = None
        return render_template('user/min-login.html', default_subject=subject, user_country=country)


@min_bp.route('onboarding', methods=['GET'])
def onboard():
    admin_id = session.get("admin_id")
    session.clear()
    session["admin_id"] = admin_id
    session["last_visit"] = "/min/onboarding"
    print("clearing session")
    return render_template('user/min-onboard.html')


def generate_random_username():
    return f"user_{random.randint(1000, 9999)}"


@min_bp.route('/auth', methods=['POST', 'GET'])
def auth_user():
    is_htmx = request.headers.get('HX-Request') == 'true'

    if request.content_type == 'application/json':
        data = request.json or {}
    else:
        data = request.form.to_dict() or {}
    
    name = data.get('name')
    email = data.get('email', "")
    phone = data.get('phone', " ")
    subject = data.get('subject')
    desg = data.get('desg', " ")
    is_anon = data.get('anonymous')
    
    user_ip = request.headers.get("X-Real-IP", request.remote_addr).split(",")[0]
    user_service = UserService(current_app.db)

    if is_anon:
        name = generate_random_username()
        user = user_service.create_user(name, ip=user_ip)
    else:
        user = user_service.create_user(
            name, email=email, phone=phone, ip=user_ip, desg=desg)

    if not (name or email or phone):
        name = generate_random_username()

    session['user_id'] = user.user_id
    session['role'] = "user"
    session.modified = True
    print(session["initial_msg"])

    return redirect(url_for('min.new_chat', subject=subject))


@min_bp.route('/newchat', defaults={'subject': "Other"}, methods=['GET'])
@min_bp.route('/newchat/<string:subject>', methods=['GET'])
@login_required
def new_chat(subject):
    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])
    chat_service = ChatService(current_app.db)
    message = session["initial_msg"]
    chat = chat_service.create_chat(
        user.user_id, subject=subject, admin_id=session.get('admin_id'),initial_msg=message,username=user.name)

    user_service.add_chat_to_user(user.user_id, chat.chat_id)

    admin = AdminService(current_app.db).get_admin_by_id(session.get('admin_id'))

    admin_service = AdminService(current_app.db)
    current_app.bot.create_chat(chat.room_id, admin)

    #### SEND THE INITAIL MESSAGE TO GEMINI
    # handle_bot_response(room_id=chat.room_id,message=initial_msg,chat=chat,admin=admin)
    max_retries=3
    retry_delay=1
    


    for attempt in range(max_retries):
        try:
            msg, usage = current_app.bot.respond(
                f"Subject of chat: {chat.subject}\n{message}", chat.room_id)
            
            admin_service.update_tokens(admin.admin_id, usage['cost'])

            bot_message = chat_service.add_message(chat.room_id, chat.bot_name, msg)

            current_app.socketio.emit('new_message', {
                'room_id': chat.room_id,
                'sender': chat.bot_name,
                'content': msg,
                'timestamp': bot_message.timestamp.isoformat()
            }, room=chat.room_id)
            break
            # return  # Success, exit retry loop
            
        except Exception as e:
            print(f"Bot response error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                # All retries failed, send error message
                error_message = chat_service.add_message(chat.room_id, "SYSTEM", 
                                                        "We Apologize, there was an unexpected error, please try again after some time")
                
                current_app.socketio.emit('new_message', {
                    'room_id': chat.room_id,
                    'sender': "SYSTEM",
                    'content': "We Apologize, there was an unexpected error, please try again after some time",
                    'timestamp': error_message.timestamp.isoformat()
                }, room=chat.room_id)
    # Redirect to chat using room_id (consistent with App 2)
    return redirect(url_for('min.chat', room_id=chat.room_id))


@min_bp.route('/chat/<string:room_id>', methods=['GET'])
@login_required
def chat(room_id):
    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])

    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)
    
    if not chat:
        print(f"Chat not found for room_id: {room_id}")
        return redirect(url_for("min.onboard"))

    # Security check - verify chat belongs to user
    # if not chat.room_id:
    #     print(f"Unauthorized access attempt to chat: {room_id}")
    #     return redirect(url_for("min.onboard"))

    return render_template('user/min-index.html', chat=chat, username=user.name)


@min_bp.route('/chat/<room_id>/ping_admin', methods=['POST'])
@login_required
def ping_admin(room_id):
    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get('admin_id'))

    if current_admin:
        settings = current_admin.settings
        timings = settings.get('timings', [])
        timezone = settings.get('timezone', "UTC")
    else:
        settings = current_app.config.get('SETTINGS', {})
        timings = settings.get('timings', [])
        timezone = settings.get('timezone', "UTC")

    now = UTCZoneManager().get_current_date(timezone)
    current_day = now.strftime('%A').lower()
    current_time = now.strftime('%H:%M')

    available = any(
        t['day'].lower() == current_day and t['startTime'] <= current_time <= t['endTime']
        for t in timings
    )

    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])
    
    chat = chat_service.get_chat_by_room_id(room_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    chat_service.set_admin_required(chat.room_id, True)

    current_app.socketio.emit('admin_required', {
        'room_id': room_id,
        'chat_id': chat.chat_id,
        'subject': chat.subject
    }, room='admin')

    noti_service = NotificationService(current_app.db)
    noti_service.create_admin_required_notification(
        chat.admin_id, chat.room_id, user.name)

    new_message = chat_service.add_message(
        chat.room_id, 'SYSTEM', 'Ana has been notified! She will join soon'
    )
    
    current_app.socketio.emit('new_message', {
        'sender': 'SYSTEM',
        'content': new_message.content,
        'timestamp': new_message.timestamp.isoformat(),
        'room_id': room_id
    }, room=room_id)

    msg = f"""Hi Ana,

{user.name} has just requested to have a live chat.

{current_app.config['SETTINGS']['backend_url']}/admin/chat/{chat.room_id}

User Information:
    Name: {user.name}
    Email: {user.email}
    Phone #: {user.phone}
    Designation: {user.desg}
    IP: {user.ip}
    Country: {user.country}
    City: {user.city}"""

    mail = Mail(current_app)
    send_email(current_admin.email, f'Assistance Required: {chat.subject}', 
               "Ping", mail, render_template('/email/admin_required.html', user=user, chat=chat))

    noti_res = send_push_noti(
        admin_service.get_expo_tokens(session.get("admin_id")), 
        "Admin Assistance Required!", 
        f'{user.name}: {chat.subject}', 
        chat.room_id
    )
    
    if noti_res.status_code != 200:
        print(f"Notification Error: {noti_res.__dict__}")

    return "", 204


import wave

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)




from flask import send_from_directory, abort

@min_bp.route("/chat/<room_id>/audio_file/<message_id>")
@login_required
def audio_file(room_id, message_id):
    base_dir = os.path.join('files', room_id)
    file_path = os.path.join(base_dir, f"{message_id}.wav")
    
    if not os.path.exists(file_path):
        abort(404, description="Audio file not found")
    
    return send_from_directory(base_dir, f"{message_id}.wav", mimetype="audio/wav")


@min_bp.route('/chat/<room_id>/send_message', methods=['POST'])
@login_required
def send_message(room_id):
    """Send a text message to the chat"""
    message = request.form.get('message')
    
    if not message or not len(message.strip()):
        return "", 204

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])
    chat_service = ChatService(current_app.db)
    admin_service = AdminService(current_app.db)
    admin = admin_service.get_admin_by_id(session.get('admin_id'))

    chat = chat_service.get_chat_by_room_id(room_id)
    
    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    new_message = chat_service.add_message(chat.room_id, user.name, message)
    new_message.content = markdown.markdown(new_message.content)
    
    # Emit user message
    current_app.socketio.emit('new_message', {
        'sender': user.name,
        'content': message,
        'timestamp': new_message.timestamp.isoformat(),
        'room_id': chat.room_id,
    }, room=chat.room_id)

    # Handle bot response or admin notification
    if not chat.admin_required:
        # try:
        #     msg, usage = current_app.bot.respond(
        #         f"Subject of chat: {chat.subject}\n{message}", chat.room_id)
        #     
        #     admin_service.update_tokens(admin.admin_id, usage['cost'])
        #
        #     bot_message = chat_service.add_message(chat.room_id, chat.bot_name, msg)
        #
        #     current_app.socketio.emit('new_message', {
        #         'room_id': chat.room_id,
        #         'sender': chat.bot_name,
        #         'content': msg,
        #         'timestamp': bot_message.timestamp.isoformat()
        #     }, room=chat.room_id)
        # except Exception as e:
        #     print(f"Bot response error: {e}")
        
        handle_bot_response(room_id, message, chat, admin)
    else:
        # Admin required
        current_app.socketio.emit('new_message_admin', {
            'room_id': chat.room_id,
            'sender': user.name,
            'content': message,
            'timestamp': new_message.timestamp.isoformat(),
        }, room=chat.room_id)
        
        noti_service = NotificationService(current_app.db)
        noti_service.create_notification(
            chat.admin_id, 
            f'{user.name} sent a message', 
            message, 
            'admin_required', 
            chat.room_id
        )

    return jsonify({'success': True}), 200


def register_min_socketio_events(socketio):
    @socketio.on('join_min')
    def on_join(data):
        room = data.get('room')

        if 'user_id' not in session:
            return

        join_room(room)
        username = session.get('name', "USER")
        current_app.config['ONLINE_USERS'] = current_app.config.get('ONLINE_USERS', 0) + 1
        emit('status', {'msg': f'{username} has joined the room.'}, room=room)

    @socketio.on('leave_min')
    def on_leave(data):
        room = data.get('room')
        user_id = session.get('user_id')

        if not room or not user_id:
            return

        user_service = UserService(current_app.db)
        user = user_service.get_user_by_id(user_id)
        if not user:
            return

        leave_room(room)

        current_app.config['ONLINE_USERS'] = max(0, current_app.config.get('ONLINE_USERS', 1) - 1)
        emit('status', {'msg': f'{user.name} has left the room.'}, room=room)
