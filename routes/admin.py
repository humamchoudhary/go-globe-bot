from flask import send_from_directory
import uuid
import os
from flask import render_template, session, request, jsonify, redirect, url_for, current_app, flash
from flask_socketio import join_room, leave_room, emit
import bcrypt
from functools import wraps
from . import admin_bp
from services.chat_service import ChatService
from services.user_service import UserService

from werkzeug.utils import secure_filename
import pdf2image


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('admin/login.html')

    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if username != current_app.config['ADMIN_USERNAME']:
        return jsonify({"error": "Invalid credentials"}), 401

    stored_hash = current_app.config['ADMIN_PASSWORD']
    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return jsonify({"error": "Invalid credentials"}), 401
    session.clear()
    session['role'] = 'admin'
    # session['admin'] = True
    return jsonify({"status": "success"}), 200


@admin_bp.route('/chat/<room_id>', methods=['GET'])
@admin_required
def chat(room_id):

    chat_service = ChatService(current_app.db)

    chat = chat_service.get_chat_by_room_id(room_id)
    chats = chat_service.get_all_chats()

    chats_data = [c.room_id for c in chats if c.admin_required]
    if not chat:
        return redirect(url_for('admin.dashboard'))
    if request.headers.get('HX-Request'):
        return render_template('admin/fragments/chat_page.html', chat=chat, username="Admin")

    return render_template('admin/dashboard.html', chat=chat, chats=chats_data, username="Admin")


@admin_bp.route('/chat/<room_id>/send_message', methods=['POST'])
@admin_required
def send_message(room_id):

    # if 'user_id' not in session:
    #     if request.headers.get('HX-Request'):
    #         return "Please log in first", 401
    #     return "<h1>Unauthorized</h1>", 401

    message = request.form.get('message')
    print(rf'{message}')
    print(f'{room_id}')
    if not message:
        return "", 302
    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)

    chat = chat_service.get_chat_by_room_id(room_id)
    if not chat:
        if request.headers.get('HX-Request'):
            return "Chat not found", 404
        return jsonify({"error": "Chat not found"}), 404

    new_message = chat_service.add_message(
        chat.room_id, "Admin", message)
    user = user_service.get_user_by_id(chat.user_id)
    if not user:
        return '<p>User Not Found</>'
    current_app.socketio.emit('new_message', {
        'sender': new_message.sender,
        'content': message,
        'timestamp': new_message.timestamp.isoformat()
    }, room=room_id)

    return render_template('admin/fragments/chat_message.html', message=new_message, username="Admin")


uploaded_files = ['file1.txt']

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'files')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@admin_bp.route('/files/')
@admin_required
def files():
    return render_template('admin/files.html', files=os.listdir(UPLOAD_FOLDER))


def is_readable_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


@admin_bp.route('/files/<file_name>', methods=['GET'])
@admin_required
def file_page(file_name):
    file = {}
    file_readable = False
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if os.path.exists(file_path):
        file["filename"] = file_name
        # Get file extension
        file_ext = os.path.splitext(file_name)[1].lower()
        # Check if file is an image
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
            # If it's an image, we don't need to read its content
            # The template will display it as an image
            file_readable = False
        else:
            # Try to read the file content for non-image files
            file['content'] = is_readable_file(file_path)
            if file['content']:
                file_readable = True
    return render_template('admin/read_file.html', file=file, file_readable=file_readable)


@admin_bp.route('/files/delete/<file_name>', methods=['POST'])
@admin_required
def delete_file(file_name):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        # Check if file exists before attempting to delete
        if os.path.exists(file_path):
            os.remove(file_path)
            flash('File deleted successfully', 'success')
        else:
            flash('File not found', 'error')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')

    # Redirect to the file list page
    # Assuming 'file_list' is your route for /file
    return redirect(url_for('admin.files'))


@admin_bp.route('/serve-file/<file_name>')
@admin_required
def serve_file(file_name):
    # Securely serve the file from the UPLOAD_FOLDER
    return send_from_directory(UPLOAD_FOLDER, file_name)


# @admin_bp.route('/add-admin', methods=['GET', 'POST'])
# @admin_required
# def add_admin():
#     if request.method == "GET":
#         return render_template('admin/add_admin.html')


@admin_bp.route("/upload", methods=["POST"])
@admin_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    original_filename = secure_filename(file.filename)
    file_extension = os.path.splitext(original_filename)[1].lower()

    # Generate a unique filename to prevent overwriting
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

    # Check if the file is a PDF
    if file_extension == '.pdf':
        try:
            # Save the file temporarily
            temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{unique_filename}")
            file.save(temp_path)

            # Convert PDF to images
            images = pdf2image.convert_from_path(temp_path)

            # If PDF has multiple pages, save the first one
            # You can modify this to save all pages if needed
            if images:
                image_filename = f"{os.path.splitext(unique_filename)[0]}.png"
                image_path = os.path.join(UPLOAD_FOLDER, image_filename)
                images[0].save(image_path, 'PNG')

                # Remove the temporary PDF file
                os.remove(temp_path)

                # Return the image filename instead
                return render_template("admin/fragments/file_item.html", file=image_filename), 200
            else:
                # If conversion fails, save original PDF
                file.save(file_path)
        except Exception as e:
            # If conversion fails, save original PDF
            file.seek(0)  # Reset file pointer
            file.save(file_path)
            print(f"PDF conversion error: {e}")
    else:
        # For non-PDF files, save directly
        file.save(file_path)

    return render_template("admin/fragments/file_item.html", file=unique_filename), 200


@admin_bp.route('/logout')
@admin_required
def logout():
    # session.pop('user', None)
    session.clear()
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_required
def dashboard():

    chat_service = ChatService(current_app.db)
    chats = chat_service.get_all_chats()

    # Convert to dictionary representation
    chats_data = [chat.room_id for chat in chats if chat.admin_required]
    return render_template('admin/dashboard.html', chats=chats_data, username="Admin")


@admin_bp.route('/chats')
@admin_required
def get_chats():
    chat_service = ChatService(current_app.db)
    chats = chat_service.get_all_chats()

    # Convert to dictionary representation
    chats_data = [chat.to_dict() for chat in chats if chat.admin_required]
    return jsonify(chats_data)


@admin_bp.route('/join/<room_id>')
@admin_required
def join_chat(room_id):
    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    # Mark admin as present in this chat
    chat_service.set_admin_present(chat.chat_id, True)

    # Notify the room that admin has joined
    current_app.socketio.emit('admin_joined', {
        'message': 'Admin has joined the chat'
    }, room=room_id)

    return render_template('chat.html', room_id=room_id, is_admin=True)

# Socket.IO events for admin


def register_admin_socketio_events(socketio):
    @socketio.on('admin_join')
    def on_admin_join(data):
        if session.get('role') != 'admin':
            print('ret')
            return

        room = data.get('room')
        if not room:
            return

        join_room(room)
        join_room('admin')  # Join the admin room for broadcasts
        print('admin joined')
        emit('status', {'msg': 'Admin has joined the room.'}, room=room)

    @socketio.on('admin_leave')
    def on_admin_leave(data):
        if session.get('user') != 'admin':
            return

        room = data.get('room')
        chat_id = data.get('chat_id')

        if not room or not chat_id:
            return

        leave_room(room)

        # Mark admin as no longer present
        chat_service = ChatService(current_app.db)
        chat_service.set_admin_present(chat_id, False)

        emit('status', {'msg': 'Admin has left the room.'}, room=room)
