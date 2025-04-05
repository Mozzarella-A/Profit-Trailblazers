import os
from dotenv import load_dotenv
from datetime import datetime
import mysql.connector
import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_mail import Mail, Message
from controllers.auth_controller import auth_bp, init_auth
from db import save_article, setup_database, get_db_cursor, log_action, save_like, update_avatar
from models.user_model import User
from functools import wraps
import uuid
import string
import random

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your_secret_key")
app.config['UPLOAD_FOLDER'] = 'static/images'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_TIMEOUT'] = 10

mail = Mail(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def database_exists():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES LIKE 'komodo_hub'")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        return result is not None
    except mysql.connector.Error as err:
        print(f"Error checking database: {err}")
        return False

if not database_exists():
    setup_database()
else:
    print("Database 'komodo_hub' already exists, skipping setup.")

app.register_blueprint(init_auth(mail), url_prefix='/auth')

@app.before_request
def log_request():
    print(f"Request: {request.method} {request.url}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login'))
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("SELECT role, is_superuser FROM users WHERE id = %s", (session['user_id'],))
            result = cursor.fetchone()
            user_role = result[0] if result else None
            is_superuser = bool(result[1]) if result and result[1] is not None else False
            if is_superuser:
                # Redirect superusers to their dashboard
                return redirect(url_for('superuser_dashboard'))
            if not user_role or user_role != "teacher":
                flash("You do not have admin privileges.", "error")
                return redirect(url_for('browse_page'))
        finally:
            cursor.close()
            connection.close()
        return f(*args, **kwargs)
    return decorated_function

def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login'))
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("SELECT is_superuser FROM users WHERE id = %s", (session['user_id'],))
            is_superuser = cursor.fetchone()[0]
            if not is_superuser:
                flash("You do not have superuser privileges.", "error")
                return redirect(url_for('browse_page'))
        finally:
            cursor.close()
            connection.close()
        return f(*args, **kwargs)
    return decorated_function

def get_user_info():
    if 'user_id' not in session:
        return {'theme': 'default', 'role': None, 'avatar_url': None, 'contribution_points': 0, 'unique_access_code': None, 'is_superuser': False}
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT theme, role, avatar_url, contribution_points, unique_access_code, is_superuser FROM users WHERE id = %s", (session['user_id'],))
        result = cursor.fetchone()
        if not result:
            return {'theme': 'default', 'role': None, 'avatar_url': None, 'contribution_points': 0, 'unique_access_code': None, 'is_superuser': False}
        user_info = {
            'theme': result[0] if result[0] else 'default',
            'role': result[1] if result[1] else None,
            'avatar_url': result[2] if result[2] else None,
            'contribution_points': result[3] if result[3] is not None else 0,
            'unique_access_code': result[4] if result[4] else None,
            'is_superuser': bool(result[5])
        }
        print(f"DEBUG: get_user_info for user_id={session['user_id']}: user_info={user_info}")
        return user_info
    finally:
        cursor.close()
        connection.close()

@app.route("/")
def home():
    user_info = get_user_info()
    return render_template("login.html", user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/write", methods=['GET', 'POST'])
@login_required
def write_page():
    if request.method == 'POST':
        content = request.form.get('content')
        subtopic = request.form.get('subtopic')
        image = request.files.get('images')
        image_filename = None
        if image and image.filename:
            if not image.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                flash("Only PNG, JPG, JPEG, and GIF files are allowed.", "error")
                return redirect(url_for('write_page'))
            image_filename = f"{uuid.uuid4()}_{image.filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
        if not content or not subtopic:
            flash("Content and subtopic are required.", "error")
            return redirect(url_for('write_page'))
        user_id = session['user_id']
        save_article(user_id, content, subtopic, image_filename)
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("UPDATE users SET contribution_points = COALESCE(contribution_points, 0) + 5 WHERE id = %s", (user_id,))
            connection.commit()
            log_action(user_id, "article_submitted", f"User {user_id} submitted article on {subtopic}")
        except Exception as e:
            connection.rollback()
            flash(f"Error updating points: {e}", "error")
        finally:
            cursor.close()
            connection.close()
        flash("Article submitted successfully! (Awaiting approval)", "success")
        return redirect(url_for('write_page'))
    user_info = get_user_info()
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT * FROM articles WHERE user_id = %s AND approved = 1", (session['user_id'],))
        my_articles = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        my_articles = [dict(zip(columns, article)) for article in my_articles]
    finally:
        cursor.close()
        connection.close()
    return render_template("write.html", 
                          user_theme=user_info['theme'], 
                          user_role=user_info['role'], 
                          avatar_url=user_info['avatar_url'], 
                          my_articles=my_articles, 
                          unique_access_code=user_info['unique_access_code'],
                          is_superuser=user_info['is_superuser'],
                          _=int(datetime.now().timestamp()))

@app.route("/browse")
def browse_page():
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT * FROM articles WHERE approved = 1 ORDER BY created_at DESC")
        articles = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        articles = [dict(zip(columns, article)) for article in articles]
        if 'user_id' in session:
            for article in articles:
                cursor.execute("SELECT COUNT(*) FROM likes WHERE user_id = %s AND article_id = %s", (session['user_id'], article['id']))
                article['liked_by_user'] = cursor.fetchone()[0] > 0
        else:
            for article in articles:
                article['liked_by_user'] = False
    finally:
        cursor.close()
        connection.close()
    user_info = get_user_info()
    return render_template("browse.html", articles=articles, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/like_article/<int:article_id>", methods=['POST'])
@login_required
def like_article(article_id):
    user_id = session['user_id']
    try:
        save_like(user_id, article_id)
        log_action(user_id, "article_liked", f"User {user_id} liked article {article_id}")
        flash("Article liked successfully!", "success")
    except Exception as e:
        flash(f"Error liking article: {e}", "error")
    return redirect(url_for('browse_page'))

@app.route("/leaderboard")
def leaderboard():
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("""
            SELECT u.username, COALESCE(u.contribution_points, 0) as total_points,
                   COUNT(DISTINCT a.id) as article_count,
                   COUNT(DISTINCT l.id) as like_count,
                   COUNT(DISTINCT sqr.id) as quiz_count
            FROM users u
            LEFT JOIN articles a ON a.user_id = u.id AND a.approved = 1
            LEFT JOIN likes l ON l.article_id = a.id
            LEFT JOIN submit_quiz_results sqr ON sqr.user_id = u.id AND sqr.is_correct = 1
            GROUP BY u.id, u.username, u.contribution_points
            HAVING COALESCE(u.contribution_points, 0) > 0
            ORDER BY COALESCE(u.contribution_points, 0) DESC
            LIMIT 10
        """)
        leaderboard = []
        for row in cursor.fetchall():
            user_data = {
                'username': row[0],
                'total_points': int(row[1]) if row[1] is not None else 0,
                'article_count': int(row[2]) if row[2] is not None else 0,
                'like_count': int(row[3] if row[3] is not None else 0),
                'quiz_count': int(row[4]) if row[4] is not None else 0
            }
            leaderboard.append(user_data)
    except Exception as e:
        print(f"Error calculating leaderboard: {e}")
        leaderboard = []
    finally:
        cursor.close()
        connection.close()
    user_info = get_user_info()
    return render_template("leaderboard.html", leaderboard=leaderboard, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/courses")
def courses():
    user_info = get_user_info()
    return render_template("courses.html", user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code']) if os.path.exists("templates/courses.html") else "Courses Page (Placeholder)"

@app.route("/school_library")
def school_library():
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT class_code FROM users WHERE id = %s", (session.get('user_id'),))
        user = cursor.fetchone()
        class_code = user[0] if user else None
        if not class_code:
            flash("You are not assigned to a class.", "error")
            return redirect(url_for('browse_page'))
        cursor.execute("SELECT * FROM school_documents WHERE class_code = %s ORDER BY created_at DESC", (class_code,))
        documents = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        documents = [dict(zip(columns, doc)) for doc in documents]
        user_info = get_user_info()
        return render_template("school_library.html", documents=documents, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])
    finally:
        cursor.close()
        connection.close()

@app.route("/class_tasks", methods=['GET', 'POST'])
@login_required
def class_tasks():
    user_info = get_user_info()
    user_role = user_info['role']
    connection, cursor = get_db_cursor()

    try:
        # Fetch user's class code
        cursor.execute("SELECT class_code FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        class_code = user[0] if user else None

        if user_role == 'student':
            if not class_code:
                flash("You are not assigned to a class.", "error")
                return redirect(url_for('browse_page'))
            cursor.execute("SELECT * FROM programs WHERE class_code = %s", (class_code,))
            programs = cursor.fetchall()
            programs = [dict(zip([column[0] for column in cursor.description], program)) for program in programs]
            for program in programs:
                cursor.execute("SELECT * FROM quizzes WHERE program_id = %s ORDER BY created_at DESC", (program['id'],))
                quizzes = cursor.fetchall()
                program['quizzes'] = [dict(zip([column[0] for column in cursor.description], quiz)) for quiz in quizzes]
                quiz_results = {}
                for quiz in program['quizzes']:
                    cursor.execute("SELECT answer, is_correct FROM submit_quiz_results WHERE user_id = %s AND quiz_id = %s ORDER BY created_at DESC LIMIT 1", (session['user_id'], quiz['id']))
                    result = cursor.fetchone()
                    if result:
                        quiz_results[quiz['id']] = "Correct!" if result[1] else "Incorrect. Try again!"
                program['quiz_results'] = quiz_results
            return render_template("class_tasks.html", programs=programs, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

        elif user_role == 'teacher':
            if request.method == 'POST':
                action = request.form.get('action')
                
                if action == 'delete_quiz':
                    quiz_id = request.form.get('quiz_id')
                    cursor.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
                    connection.commit()
                    log_action(session['user_id'], "quiz_deleted", f"Teacher {session['user_id']} deleted quiz {quiz_id}")
                    flash("Quiz deleted successfully!", "success")
                
                elif action == 'create_quiz':
                    class_code = request.form.get('class_code')
                    question = request.form.get('question')
                    options = request.form.get('options')
                    correct_answer = request.form.get('correct_answer')
                    program_id = request.form.get('program_id')
                    
                    if not all([class_code, question, options, correct_answer, program_id]):
                        flash("All fields are required to create a quiz.", "error")
                    else:
                        cursor.execute("""
                            INSERT INTO quizzes (class_code, question, options, correct_answer, program_id, created_at)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                        """, (class_code, question, options, correct_answer, program_id))
                        connection.commit()
                        log_action(session['user_id'], "quiz_created", f"Teacher {session['user_id']} created quiz for class {class_code}")
                        flash("Quiz created successfully!", "success")
                
                return redirect(url_for('class_tasks'))

            cursor.execute("SELECT * FROM programs ORDER BY class_code")
            programs = cursor.fetchall()
            programs = [dict(zip([column[0] for column in cursor.description], program)) for program in programs]
            for program in programs:
                cursor.execute("SELECT * FROM quizzes WHERE program_id = %s ORDER BY created_at DESC", (program['id'],))
                quizzes = cursor.fetchall()
                program['quizzes'] = [dict(zip([column[0] for column in cursor.description], quiz)) for quiz in quizzes]
            
            return render_template("class_tasks_teacher.html", programs=programs, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

    except Exception as e:
        print(f"Error in class_tasks: {e}")
        flash("An error occurred while loading class tasks.", "error")
        return redirect(url_for('browse_page'))
    finally:
        cursor.close()
        connection.close()

@app.route("/submit_quiz/<int:quiz_id>", methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT is_correct FROM submit_quiz_results WHERE user_id = %s AND quiz_id = %s AND is_correct = 1", (session['user_id'], quiz_id))
        if cursor.fetchone():
            flash("You have already answered this quiz correctly!", "info")
            return redirect(url_for('class_tasks'))
        cursor.execute("SELECT correct_answer FROM quizzes WHERE id = %s", (quiz_id,))
        quiz = cursor.fetchone()
        if not quiz:
            flash("Quiz not found.", "error")
            return redirect(url_for('class_tasks'))
        correct_answer = quiz[0]
        user_answer = request.form.get('answer')
        is_correct = user_answer == correct_answer
        cursor.execute("""
            INSERT INTO submit_quiz_results (user_id, quiz_id, answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], quiz_id, user_answer, int(is_correct)))
        if is_correct:
            cursor.execute("UPDATE users SET contribution_points = COALESCE(contribution_points, 0) + 5 WHERE id = %s", (session['user_id'],))
        connection.commit()
        log_action(session['user_id'], "quiz_submitted", f"User {session['user_id']} submitted quiz {quiz_id} with result {is_correct}")
        flash("Quiz submitted! Check your result.", "success")
        return redirect(url_for('class_tasks'))
    except Exception as e:
        connection.rollback()
        flash(f"Error submitting quiz: {e}", "error")
        return redirect(url_for('class_tasks'))
    finally:
        cursor.close()
        connection.close()

@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        theme = request.form.get('theme')
        avatar = request.files.get('avatar')
        if theme in ['default', 'dark', 'ocean', 'forest', 'sunset']:
            try:
                User.update_theme(session['user_id'], theme)
                log_action(session['user_id'], "theme_updated", f"User {session['user_id']} updated theme to {theme}")
                session.pop('_user_info_cache', None)  # Optional: only if caching is added later
                flash("Theme updated successfully!", "success")
            except Exception as e:
                flash(f"Error updating theme: {e}", "error")
        else:
            flash("Invalid theme selected.", "error")
        if avatar and avatar.filename:
            if not avatar.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                flash("Only PNG, JPG, JPEG, and GIF files are allowed.", "error")
                return redirect(url_for('profile'))
            filename = f"{uuid.uuid4()}_{avatar.filename}"
            avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            avatar.save(avatar_path)
            update_avatar(session['user_id'], filename)
            log_action(session['user_id'], "avatar_updated", f"User {session['user_id']} updated avatar to {filename}")
            flash("Avatar updated successfully!", "success")
        return redirect(url_for('profile', _=int(datetime.now().timestamp())))
    user_info = get_user_info()
    return render_template("profile.html", 
                          user_theme=user_info['theme'], 
                          user_role=user_info['role'], 
                          avatar_url=user_info['avatar_url'], 
                          unique_access_code=user_info['unique_access_code'],
                          is_superuser=user_info['is_superuser'],
                          _=int(datetime.now().timestamp()))

@app.route("/admin")
@login_required
@admin_required
def admin_page():
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
        articles = cursor.fetchall()
        article_columns = [column[0] for column in cursor.description]
        articles = [dict(zip(article_columns, article)) for article in articles]
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        user_columns = [column[0] for column in cursor.description]
        users = [dict(zip(user_columns, user)) for user in users]
        user_info = get_user_info()
        return render_template("admin.html", articles=articles, users=users, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])
    finally:
        cursor.close()
        connection.close()

@app.route("/admin/delete/<int:article_id>", methods=['POST'])
@login_required
@admin_required
def delete_article(article_id):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("DELETE FROM articles WHERE id = %s", (article_id,))
        connection.commit()
        log_action(session['user_id'], "article_deleted", f"User {session['user_id']} deleted article {article_id}")
        flash("Article deleted successfully!", "success")
    except Exception as e:
        connection.rollback()
        flash(f"Error deleting article: {e}", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('admin_page'))

@app.route("/admin/approve/<int:article_id>", methods=['POST'])
@login_required
@admin_required
def approve_article(article_id):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT approved FROM articles WHERE id = %s", (article_id,))
        was_approved = cursor.fetchone()[0]
        cursor.execute("UPDATE articles SET approved = 1 WHERE id = %s", (article_id,))
        if not was_approved:
            cursor.execute("UPDATE users SET contribution_points = COALESCE(contribution_points, 0) + 5 WHERE id = (SELECT user_id FROM articles WHERE id = %s)", (article_id,))
        connection.commit()
        log_action(session['user_id'], "article_approved", f"User {session['user_id']} approved article {article_id}")
        flash("Article approved successfully!", "success")
    except Exception as e:
        connection.rollback()
        flash(f"Error approving article: {e}", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('admin_page'))

@app.route("/admin/class_management", methods=['GET', 'POST'])
@login_required
@admin_required
def class_management():
    if request.method == 'POST':
        connection, cursor = get_db_cursor()
        try:
            action = request.form.get('action')
            
            if action in ['assign', 'remove', 'regenerate_code']:
                student_id = request.form.get('student_id')
                class_code = request.form.get('class_code')
                
                if action == 'assign':
                    cursor.execute("UPDATE users SET class_code = %s WHERE id = %s AND role = 'student'", (class_code, student_id))
                    connection.commit()
                    log_action(session['user_id'], "student_assigned", f"User {session['user_id']} assigned student {student_id} to {class_code}")
                    flash("Student assigned to class successfully!", "success")
                
                elif action == 'remove':
                    cursor.execute("UPDATE users SET class_code = NULL WHERE id = %s AND role = 'student'", (student_id,))
                    connection.commit()
                    log_action(session['user_id'], "student_removed", f"User {session['user_id']} removed student {student_id} from class")
                    flash("Student removed from class successfully!", "success")
                
                elif action == 'regenerate_code':
                    new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    while User.find_by_access_code(new_code):
                        new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    cursor.execute("UPDATE users SET unique_access_code = %s WHERE id = %s AND role = 'student'", (new_code, student_id))
                    connection.commit()
                    log_action(session['user_id'], "code_regenerated", f"User {session['user_id']} regenerated code for student {student_id}")
                    flash(f"New access code generated: {new_code}", "success")
            
            elif action == 'approve_article':
                article_id = request.form.get('article_id')
                cursor.execute("SELECT approved FROM articles WHERE id = %s", (article_id,))
                was_approved = cursor.fetchone()[0]
                cursor.execute("UPDATE articles SET approved = 1 WHERE id = %s", (article_id,))
                if not was_approved:
                    cursor.execute("UPDATE users SET contribution_points = COALESCE(contribution_points, 0) + 5 WHERE id = (SELECT user_id FROM articles WHERE id = %s)", (article_id,))
                connection.commit()
                log_action(session['user_id'], "article_approved", f"User {session['user_id']} approved article {article_id}")
                flash("Article approved successfully!", "success")
            
            elif action == 'delete_article':
                article_id = request.form.get('article_id')
                cursor.execute("DELETE FROM articles WHERE id = %s", (article_id,))
                connection.commit()
                log_action(session['user_id'], "article_deleted", f"User {session['user_id']} deleted article {article_id}")
                flash("Article deleted successfully!", "success")
        
        except Exception as e:
            connection.rollback()
            flash(f"Error processing action: {e}", "error")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('class_management'))

    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT id, username, email, class_code, unique_access_code FROM users WHERE role = 'student'")
        students = cursor.fetchall()
        student_columns = [column[0] for column in cursor.description]
        students_list = [dict(zip(student_columns, student)) for student in students]

        cursor.execute("""
            SELECT a.id, u.username, a.subtopic, a.content, a.image_filename, a.created_at, a.approved
            FROM articles a
            JOIN users u ON a.user_id = u.id
            WHERE u.role = 'student'
            ORDER BY a.created_at DESC
        """)
        articles = cursor.fetchall()
        article_columns = [column[0] for column in cursor.description]
        articles_list = [dict(zip(article_columns, article)) for article in articles]
    except Exception as e:
        print(f"Error fetching data: {e}")
        students_list = []
        articles_list = []
    finally:
        cursor.close()
        connection.close()

    user_info = get_user_info()
    return render_template("class_management.html", students=students_list, articles=articles_list, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/admin/student_progress/<int:student_id>")
@login_required
@admin_required
def student_progress(student_id):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT username, email, class_code, contribution_points FROM users WHERE id = %s AND role = 'student'", (student_id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for('admin_page'))
        student_dict = dict(zip(['username', 'email', 'class_code', 'contribution_points'], student))
        cursor.execute("SELECT * FROM articles WHERE user_id = %s", (student_id,))
        articles = cursor.fetchall()
        articles = [dict(zip([column[0] for column in cursor.description], article)) for article in articles]
        cursor.execute("SELECT q.question, sqr.answer, sqr.is_correct FROM submit_quiz_results sqr JOIN quizzes q ON sqr.quiz_id = q.id WHERE sqr.user_id = %s", (student_id,))
        quiz_results = cursor.fetchall()
        quiz_results = [dict(zip(['question', 'answer', 'is_correct'], result)) for result in quiz_results]
    finally:
        cursor.close()
        connection.close()
    user_info = get_user_info()
    return render_template("student_progress.html", student=student_dict, articles=articles, quiz_results=quiz_results, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/messages", methods=['GET', 'POST'])
@login_required
def messages():
    connection, cursor = get_db_cursor()
    try:
        if request.method == 'POST':
            receiver_id = request.form.get('receiver_id')
            content = request.form.get('content')
            if not receiver_id or not content:
                flash("Receiver and message content are required.", "error")
                return redirect(url_for('messages'))
            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, content, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (session['user_id'], receiver_id, content))
            connection.commit()
            log_action(session['user_id'], "message_sent", f"User {session['user_id']} sent message to {receiver_id}")
            flash("Message sent successfully!", "success")
        user_role = get_user_info()['role']
        if user_role == 'student':
            cursor.execute("SELECT id, username FROM users WHERE role = 'teacher'")
        else:
            cursor.execute("SELECT id, username FROM users WHERE role = 'student'")
        users = cursor.fetchall()
        users = [dict(zip(['id', 'username'], user)) for user in users]
        cursor.execute("""
            SELECT m.*, u.username as sender_name 
            FROM messages m 
            JOIN users u ON m.sender_id = u.id 
            WHERE m.receiver_id = %s OR m.sender_id = %s 
            ORDER BY m.created_at DESC
        """, (session['user_id'], session['user_id']))
        messages = cursor.fetchall()
        messages = [dict(zip([column[0] for column in cursor.description], message)) for message in messages]
    finally:
        cursor.close()
        connection.close()
    user_info = get_user_info()
    return render_template("messages.html", users=users, messages=messages, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/report_sighting", methods=['GET', 'POST'])
@login_required
def report_sighting():
    if request.method == 'POST':
        species = request.form.get('species')
        location = request.form.get('location')
        sighting_date = request.form.get('sighting_date')
        description = request.form.get('description')
        if not species or not location or not sighting_date:
            flash("Species, location, and sighting date are required.", "error")
            return redirect(url_for('report_sighting'))
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("""
                INSERT INTO sightings (user_id, species, location, sighting_date, description, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (session['user_id'], species, location, sighting_date, description))
            connection.commit()
            log_action(session['user_id'], "sighting_reported", f"User {session['user_id']} reported sighting of {species}")
            flash("Sighting reported successfully!", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Error reporting sighting: {e}", "error")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('report_sighting'))

    connection, cursor = get_db_cursor()
    try:
        cursor.execute("""
            SELECT s.species, s.location, s.sighting_date, s.description, s.created_at, u.username
            FROM sightings s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.created_at DESC
        """)
        sightings = cursor.fetchall()
        sighting_columns = [column[0] for column in cursor.description]
        sightings_list = [dict(zip(sighting_columns, sighting)) for sighting in sightings]
    except Exception as e:
        print(f"Error fetching sightings: {e}")
        sightings_list = []
    finally:
        cursor.close()
        connection.close()

    user_info = get_user_info()
    return render_template("report_sighting.html", sightings=sightings_list, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

def school_profile(class_code):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT * FROM schools WHERE class_code = %s", (class_code,))
        school = cursor.fetchone()
        if not school:
            flash("School not found.", "error")
            return redirect(url_for('browse_page'))
        school = dict(zip([column[0] for column in cursor.description], school))
        cursor.execute("SELECT * FROM school_documents WHERE class_code = %s ORDER BY created_at DESC", (class_code,))
        documents = cursor.fetchall()
        documents = [dict(zip([column[0] for column in cursor.description], doc)) for doc in documents]
        cursor.execute("""
            SELECT a.* FROM articles a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.class_code = %s AND a.approved = 1 
            ORDER BY a.created_at DESC
        """, (class_code,))
        articles = cursor.fetchall()
        articles = [dict(zip([column[0] for column in cursor.description], article)) for article in articles]
    finally:
        cursor.close()
        connection.close()
    user_info = get_user_info()
    return render_template("school_profile.html", school=school, documents=documents, articles=articles, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/superuser", methods=['GET'])
@login_required
@superuser_required
def superuser_dashboard():
    connection, cursor = get_db_cursor()
    try:
        # Fetch stats
        cursor.execute("SELECT COUNT(*) FROM schools WHERE class_code LIKE 'Class%'")
        school_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM schools WHERE class_code NOT LIKE 'Class%'")
        community_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE role != 'superuser'")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM articles WHERE approved = 1")
        article_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sightings")
        sighting_count = cursor.fetchone()[0]
        stats = {
            'schools': school_count,
            'communities': community_count,
            'users': user_count,
            'articles': article_count,
            'sightings': sighting_count
        }

        # Fetch schools
        cursor.execute("SELECT * FROM schools ORDER BY created_at DESC")
        schools = cursor.fetchall()
        schools = [dict(zip([column[0] for column in cursor.description], school)) for school in schools]

        # Fetch recent activity
        cursor.execute("""
            SELECT u.username, a.action, a.details, a.created_at 
            FROM audit_logs a 
            LEFT JOIN users u ON a.user_id = u.id 
            ORDER BY a.created_at DESC 
            LIMIT 10
        """)
        recent_activity = cursor.fetchall()
        recent_activity = [dict(zip(['username', 'action', 'description', 'created_at'], activity)) for activity in recent_activity]

    except Exception as e:
        print(f"Error fetching superuser data: {e}")
        stats = {'schools': 0, 'communities': 0, 'users': 0, 'articles': 0, 'sightings': 0}
        schools = []
        recent_activity = []
    finally:
        cursor.close()
        connection.close()

    user_info = get_user_info()
    return render_template("optimal_superuser_dashboard.html", 
                          stats=stats, 
                          schools=schools, 
                          recent_activity=recent_activity, 
                          user_theme=user_info['theme'], 
                          user_role=user_info['role'], 
                          avatar_url=user_info['avatar_url'], 
                          unique_access_code=user_info['unique_access_code'],
                          is_superuser=user_info['is_superuser'])

@app.route("/register_entity", methods=['POST'])
@login_required
@superuser_required
def register_entity():
    entity_name = request.form.get('entity_name')
    entity_type = request.form.get('entity_type')
    if not entity_name or not entity_type:
        flash("Name and type are required.", "error")
        return redirect(url_for('superuser_dashboard'))

    connection, cursor = get_db_cursor()
    try:
        class_code = f"{entity_type[:3].capitalize()}{random.randint(1000, 9999)}"
        cursor.execute("SELECT COUNT(*) FROM schools WHERE class_code = %s", (class_code,))
        while cursor.fetchone()[0] > 0:
            class_code = f"{entity_type[:3].capitalize()}{random.randint(1000, 9999)}"
        
        cursor.execute("""
            INSERT INTO schools (name, class_code, created_at)
            VALUES (%s, %s, NOW())
        """, (entity_name, class_code))
        connection.commit()
        log_action(session['user_id'], "entity_registered", f"Superuser {session['user_id']} registered {entity_type} '{entity_name}' with class_code {class_code}")
        flash(f"{entity_type.capitalize()} '{entity_name}' registered successfully with class code {class_code}!", "success")
    except Exception as e:
        connection.rollback()
        flash(f"Error registering entity: {e}", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('superuser_dashboard'))

@app.route("/send_email", methods=['POST'])
@login_required
@superuser_required
def send_email():
    subject = request.form.get('email_subject')
    body = request.form.get('email_body')
    if not subject or not body:
        flash("Subject and body are required.", "error")
        return redirect(url_for('superuser_dashboard'))

    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT email FROM users WHERE role = 'teacher'")
        recipients = [row[0] for row in cursor.fetchall()]
        
        if not recipients:
            flash("No recipients found.", "error")
            return redirect(url_for('superuser_dashboard'))

        msg = Message(subject, recipients=recipients)
        msg.body = body
        # mail.send(msg)  # Uncomment when email server is configured
        print(f"Email sent to {len(recipients)} recipients:\nSubject: {subject}\nBody: {body}")
        
        log_action(session['user_id'], "email_sent", f"Superuser {session['user_id']} sent email to {len(recipients)} recipients with subject '{subject}'")
        flash("Email would have been sent to all teachers! Check the terminal for details.", "success")
    except Exception as e:
        flash(f"Error sending email: {e}", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('superuser_dashboard'))

@app.route("/species")
def species_page():
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT name, scientific_name, population_estimate, primary_threat, description FROM species ORDER BY name")
        species = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        species = [dict(zip(columns, spec)) for spec in species]
    finally:
        cursor.close()
        connection.close()
    user_info = get_user_info()
    return render_template("species.html", species=species, user_theme=user_info['theme'], user_role=user_info['role'], avatar_url=user_info['avatar_url'], unique_access_code=user_info['unique_access_code'])

@app.route("/logout")
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], "logout", f"User {session['user_id']} logged out")
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('auth.login'))

@app.after_request
def add_header(response):
    if 'text/css' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route("/styles.css")
def styles_css():
    user_info = get_user_info()
    response = make_response(render_template("styles.css", user_theme=user_info['theme']))
    response.headers['Content-Type'] = 'text/css'
    return response


@app.route("/four_in_a_row")
@login_required
def four_in_a_row():
    user_info = get_user_info()
    if user_info['role'] != 'student':
        flash("Only students can play 4 in a Row!", "error")
        return redirect(url_for('browse_page'))
    return render_template("four_in_a_row.html", 
                          user_theme=user_info['theme'], 
                          user_role=user_info['role'], 
                          avatar_url=user_info['avatar_url'], 
                          unique_access_code=user_info['unique_access_code'],
                          is_superuser=user_info['is_superuser'])

# In app.py, add this route under admin-related routes
@app.route("/admin/initiative_health")
@login_required
@admin_required
def initiative_health():
    connection, cursor = get_db_cursor()
    try:
        # Get all classes
        cursor.execute("SELECT DISTINCT class_code FROM users WHERE class_code IS NOT NULL")
        classes = [row[0] for row in cursor.fetchall() if row[0]]

        health_data = {}
        for class_code in classes:
            # Total students
            cursor.execute("SELECT COUNT(*) FROM users WHERE class_code = %s AND role = 'student'", (class_code,))
            total_students = cursor.fetchone()[0]

            # Active students (submitted articles or quizzes in last 30 days)
            cursor.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                LEFT JOIN articles a ON u.id = a.user_id AND a.created_at > NOW() - INTERVAL 30 DAY
                LEFT JOIN submit_quiz_results sqr ON u.id = sqr.user_id AND sqr.created_at > NOW() - INTERVAL 30 DAY
                WHERE u.class_code = %s AND u.role = 'student'
                AND (a.id IS NOT NULL OR sqr.id IS NOT NULL)
            """, (class_code,))
            active_students = cursor.fetchone()[0]

            # Article submissions
            cursor.execute("SELECT COUNT(*) FROM articles a JOIN users u ON a.user_id = u.id WHERE u.class_code = %s AND a.created_at > NOW() - INTERVAL 30 DAY", (class_code,))
            articles_count = cursor.fetchone()[0]

            # Quiz completions
            cursor.execute("SELECT COUNT(*) FROM submit_quiz_results sqr JOIN users u ON sqr.user_id = u.id WHERE u.class_code = %s AND sqr.created_at > NOW() - INTERVAL 30 DAY", (class_code,))
            quizzes_count = cursor.fetchone()[0]

            # Health score (simple metric: % of active students + activity counts)
            health_score = min(100, round((active_students / max(total_students, 1)) * 50 + (articles_count + quizzes_count) * 5))

            health_data[class_code] = {
                'total_students': total_students,
                'active_students': active_students,
                'articles_count': articles_count,
                'quizzes_count': quizzes_count,
                'health_score': health_score
            }

    except Exception as e:
        print(f"Error fetching initiative health data: {e}")
        health_data = {}
    finally:
        cursor.close()
        connection.close()

    user_info = get_user_info()
    return render_template("initiative_health.html", 
                          health_data=health_data, 
                          user_theme=user_info['theme'], 
                          user_role=user_info['role'], 
                          avatar_url=user_info['avatar_url'], 
                          unique_access_code=user_info['unique_access_code'])



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)