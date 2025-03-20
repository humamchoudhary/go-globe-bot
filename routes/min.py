import random
from flask import render_template, session, request, jsonify, redirect, url_for, current_app
from flask_socketio import join_room, leave_room, emit
from . import min_bp
from services.user_service import UserService
from services.chat_service import ChatService
from functools import wraps


# Add a login_required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/min/login')

        user_service = UserService(current_app.db)
        user = user_service.get_user_by_id(session['user_id'])

        if not user:
            return redirect('/min/login')
        return f(*args, **kwargs)
    return decorated_function


@min_bp.route('/')
@login_required
def index():
    return redirect(url_for('min.new_chat'))


@min_bp.route('login', methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template('user/min-login.html')


def generate_random_username():
    return f"user_{random.randint(1000, 9999)}"


@min_bp.route('/auth', methods=['POST', 'GET'])
def auth_user():
    # print(request.json)
    # return jsonify({'error':"test error"}),404
    if request.method == "GET":
        sess_user = session.get('user_id')
        return ('', 204) if sess_user else jsonify(False)

    # Check if the user is already authenticated
    # if 'user_id' in session:
    #     return ('', 204)

    data = request.json or {}
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    subject = data.get('subject')
    is_anon = data.get('anonymous')
    user_ip = request.remote_addr  # Automatically fetch IP
    user_service = UserService(current_app.db)
    if is_anon:
        name = generate_random_username()
        user = user_service.create_user(name, ip=user_ip)

    else:
        user = user_service.create_user(
            name, email=email, phone=phone, ip=user_ip)

    if not (name or email or phone):
        # if not ALLOW_EMPTY_USERS:
        if not True:
            return jsonify({"error": "Empty users are not allowed."}), 400
        name = generate_random_username()

    # Store user details in session (replace with DB logic if needed)

    session['user_id'] = user.user_id
    session['role'] = "user"
    # return redirect(url_for('chat.index'))
    print(subject)
    return redirect(url_for('min.new_chat', subject=subject))

    # return jsonify({"error": "Empty users are not allowed."}), 400


@min_bp.route('/newchat/<string:subject>', methods=['GET'])
@login_required
def new_chat(subject):
    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])
    chat_service = ChatService(current_app.db)
    chat = chat_service.create_chat(user.user_id, subject=subject)
    user_service.add_chat_to_user(user.user_id, chat.chat_id)

    return redirect(url_for('min.chat', chat_id=chat.chat_id))


@min_bp.route('/chat/<chat_id>', methods=['GET'])
@login_required
def chat(chat_id):

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])

    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(f'{user.user_id}-{chat_id[:8]}')
    print(not chat)
    if not chat:
        return redirect(url_for('min.new_chat'))
    # Get the username from session, fallback to "USER" if not available
    return render_template('user/min-index.html', chat=chat, username=user.name)


@min_bp.route('/chat/<chat_id>/ping_admin', methods=['POST'])
@login_required
def ping_admin(chat_id):
    chat_service = ChatService(current_app.db)

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])
    room_id = f"{user.user_id}-{chat_id[:8]}"
    chat = chat_service.get_chat_by_room_id(room_id)

    if not chat:
        if request.headers.get('HX-Request'):
            return "Chat not found", 404
        return jsonify({"error": "Chat not found"}), 404

    # Mark the chat as requiring admin attention
    chat_service.set_admin_required(chat.room_id, True)

    # Notify admins via socketio
    current_app.socketio.emit('admin_required', {
        'room_id': room_id,
        'chat_id': chat.chat_id, 'subject': chat.subject
    }, room='admin')

    if request.headers.get('HX-Request'):  # HTMX request
        return "", 204  # No content response for successful submission

    return jsonify({"status": "Admin has been notified"}), 200


@min_bp.route('/chat/<chat_id>/send_message', methods=['POST'])
@login_required
def send_message(chat_id):
    message = request.form.get('message')
    print(rf'{message}')
    if not message or not len(message):
        return "", 302

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(session['user_id'])
    chat_service = ChatService(current_app.db)

    chat = chat_service.get_chat_by_room_id(f'{user.user_id}-{chat_id[:8]}')
    if not chat:
        if request.headers.get('HX-Request'):
            return "Chat not found", 404
        return jsonify({"error": "Chat not found"}), 404

    # Get the username from session, fallback to "USER" if not available

    new_message = chat_service.add_message(
        chat.room_id, user.name, message)

    print(f'{session["user_id"]}-{chat_id[:8]}')

    current_app.socketio.emit('new_message', {
        'sender': user.name,
        'content': message,
        'timestamp': new_message.timestamp.isoformat(),
    }, room=f'{user.user_id}-{chat_id[:8]}')

    if (not chat.admin_required):
        msg = current_app.bot.responed(message)

        bot_message = chat_service.add_message(
            chat.room_id, chat.bot_name, msg)

        current_app.socketio.emit('new_message', {
            'sender': chat.bot_name,
            'content': msg,
            'timestamp': bot_message.timestamp.isoformat()
        }, room=f'{user.user_id}-{chat_id[:8]}')

    return jsonify({'success': True}), 200


def register_min_socketio_events(socketio):
    @socketio.on('join_min')
    def on_join(data):
        room = data.get('room')

        # Allow joining only if authenticated
        if 'user_id' not in session:
            return

        join_room(room)
        username = session.get('name', "USER")
        print(f'{username} has joined the room.')
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
        emit('status', {'msg': f'{user.name} has left the room.'}, room=room)
