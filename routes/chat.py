from flask import render_template, session, request, jsonify, redirect, url_for, current_app
from flask_socketio import join_room, leave_room, emit
from . import chat_bp
from services.user_service import UserService
from services.usage_service import UsageService
from services.chat_service import ChatService
from functools import wraps


def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(session)
        if session.get('role') != 'user':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@chat_bp.route('/')
@user_required
def index():

    user_service = UserService(current_app.db)

    if 'user_id' not in session:
        # return render_template('index-login.html')
        return redirect(url_for('auth.login'))

    user = user_service.get_user_by_id(session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    # chats = []
    # for chat_id in user.chat_ids:
    #     chat = chat_service.get_chat_by_id(chat_id)
    #     if chat:
    #         chats.append(chat.to_dict())

    chat_service = ChatService(current_app.db)
    chats = [chat_service.get_chat_by_id(idx) for idx in user.chat_ids]
    if request.headers.get('HX_Request'):
        return render_template('user/fragments/chat_page.html', chats=chats, username=user.name)
    return render_template('user/index.html', chats=chats, username=user.name)


@chat_bp.route('/chat/<chat_id>', methods=['GET'])
@user_required
def chat(chat_id):

    if 'user_id' not in session:
        return redirect(url_for('chat.index'))

    user_service = UserService(current_app.db)
    chat_service = ChatService(current_app.db)

    user = user_service.get_user_by_id(session['user_id'])
    # if not user:
    #     return redirect(url_for('chat.index'))
    # print(f'{user.user_id}-{chat_id}')
    chat = chat_service.get_chat_by_room_id(f'{user.user_id}-{chat_id[:8]}')
    # print(chat)
    chats = [chat_service.get_chat_by_id(idx) for idx in user.chat_ids]
    if not chat:
        return redirect(url_for('chat.index'))
    if request.headers.get('HX-Request'):
        return render_template('user/fragments/chat_page.html', chat=chat, chats=chats, username=user.name)

    return render_template('user/index.html', chat=chat, chats=chats, username=user.name)


@chat_bp.route('/chat/<chat_id>/ping_admin', methods=['POST'])
@user_required
def ping_admin(chat_id):

    if 'user_id' not in session:
        if request.headers.get('HX-Request'):
            return "Please log in first", 401
        return jsonify({"error": "Unauthorized"}), 401

    user_service = UserService(current_app.db)
    chat_service = ChatService(current_app.db)

    user = user_service.get_user_by_id(session['user_id'])
    room_id = f"{user.user_id}-{chat_id[:8]}"
    chat = chat_service.get_chat_by_room_id(room_id)

    if not chat:
        if request.headers.get('HX-Request'):
            return "Chat not found", 404
        return jsonify({"error": "Chat not found"}), 404

    if chat.admin_required:
        return "", 304
    # Mark the chat as requiring admin attention
    chat_service.set_admin_required(chat.room_id, True)

    # Notify admins via socketio
    current_app.socketio.emit('admin_required', {
        'room_id': room_id,
        'chat_id': chat.chat_id, 'subject': chat.subject
    }, room='admin')

    new_message = chat_service.add_message(
        chat.room_id, 'SYSTEM', 'Anna has been notified! She will join soon')
    current_app.socketio.emit('new_message', {
        'sender': 'SYSTEM',
        'content': new_message.content,
        'timestamp': new_message.timestamp.isoformat(),
    }, room=f'{user.user_id}-{chat_id[:8]}')

    if request.headers.get('HX-Request'):  # HTMX request
        return "", 204  # No content response for successful submission

    return jsonify({"status": "Anna has been notified"}), 200


@chat_bp.route('/chat/<chat_id>/send_message', methods=['POST'])
@user_required
def send_message(chat_id):

    if 'user_id' not in session:
        if request.headers.get('HX-Request'):
            return "Please log in first", 401
        return "<h1>Unauthorized</h1>", 401

    message = request.form.get('message')
    print(rf'{message}')
    if not message:
        return "", 302
    user_service = UserService(current_app.db)
    chat_service = ChatService(current_app.db)

    user = user_service.get_user_by_id(session['user_id'])
    if not user:
        if request.headers.get('HX-Request'):
            return "User not found", 404
        return jsonify({"error": "User not found"}), 401

    chat = chat_service.get_chat_by_room_id(f'{user.user_id}-{chat_id[:8]}')
    if not chat:
        if request.headers.get('HX-Request'):
            return "Chat not found", 404
        return jsonify({"error": "Chat not found"}), 404
    # print(request.form.get('message'))
    new_message = chat_service.add_message(
        chat.room_id, user.name, message)
    # print(new_message)

    current_app.socketio.emit('new_message', {
        'sender': user.name,
        'content': message,
        'timestamp': new_message.timestamp.isoformat(),
    }, room=f'{user.user_id}-{chat_id[:8]}')
    if (not chat.admin_required):
        msg, usage = current_app.bot.responed(
            message, chat.room_id)
        print(msg)
        print(usage)

        usage_service = UsageService(current_app.db)
        usage_service.add_cost(usage['input'], usage['output'], usage['cost'])

        bot_message = chat_service.add_message(
            chat.room_id, chat.bot_name, msg)

        current_app.socketio.emit('new_message', {
            'sender': chat.bot_name,
            'content': msg,
            'timestamp': bot_message.timestamp.isoformat()
        }, room=f'{user.user_id}-{chat_id[:8]}')

    return render_template('user/fragments/chat_message.html', message=new_message, username=user.name)


@chat_bp.route('/newchat/<string:subject>', methods=['GET'])
@user_required
def new_chat(subject):
    if 'user_id' not in session:
        return redirect(url_for('chat.index'))

    user_service = UserService(current_app.db)
    chat_service = ChatService(current_app.db)

    user = user_service.get_user_by_id(session['user_id'])
    if not user:
        return redirect(url_for('chat.index'))

    # Create a new chat with server-generated room_id
    chat = chat_service.create_chat(user.user_id, subject=subject)
    user_service.add_chat_to_user(user.user_id, chat.chat_id)
    current_app.bot.create_chat(chat.room_id)

    if request.headers.get('HX-Request'):  # HTMX request
        return render_template('user/fragments/chat_page.html', chat=chat, chats=user.chat_ids, username=user.name)

    return redirect(url_for('chat.chat', chat_id=chat.chat_id))


def register_socketio_events(socketio):
    @socketio.on('join')
    def on_join(data):
        room = data.get('room')
        user_id = session.get('user_id')

        if not room or not user_id:
            return

        user_service = UserService(current_app.db)

        user = user_service.get_user_by_id(user_id)
        if not user:
            return

        join_room(room)
        user_service.update_last_active(user_id)
        print(f'{user.name} has joined the room.')
        emit('status', {'msg': f'{user.name} has joined the room.'}, room=room)

    @socketio.on('leave')
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
