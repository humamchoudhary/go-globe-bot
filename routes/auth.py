import random
from flask import url_for, redirect, session, request, jsonify, render_template, current_app
from . import auth_bp
from services.user_service import UserService


@auth_bp.route('/set-username', methods=['POST'])
def set_username():
    data = request.json
    name = data.get('name')

    if not name:
        return jsonify({"error": "Name is required"}), 400

    user_service = UserService(current_app.db)

    # If user already has a session, update their name
    if 'user_id' in session:
        user = user_service.get_user_by_id(session['user_id'])
        if user:
            user.name = name
            current_app.db.users.update_one(
                {'user_id': user.user_id},
                {'$set': {'name': name}}
            )
            return jsonify({"user_id": user.user_id, "name": name}), 200

    # Create a new user
    user = user_service.create_user(name)
    session['user_id'] = user.user_id
    session['admin'] = False
    session.permanent = True

    return jsonify({"user_id": user.user_id, "name": name}), 201


def generate_random_username():
    return f"user_{random.randint(1000, 9999)}"


@auth_bp.route('/login', methods=['GET'])
def login():
    return render_template('user/login.html')


@auth_bp.route('/auth', methods=['POST', 'GET'])
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
    if request.args.get('redir'):
        return redirect(url_for(request.args.get('redir')))
    else:
        return redirect(url_for('chat.index'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
