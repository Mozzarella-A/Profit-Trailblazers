import os
from dotenv import load_dotenv
from datetime import datetime
import mysql.connector
import bcrypt

load_dotenv()

def get_db_connection(db_name="komodo_hub"):
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=db_name if db_name else None
    )

def get_db_cursor(db_name="komodo_hub"):
    connection = get_db_connection(db_name)
    cursor = connection.cursor()
    if db_name:
        cursor.execute(f"USE {db_name}")
    return connection, cursor

def setup_database():
    connection, cursor = get_db_cursor(None)
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS komodo_hub")
        print("Database 'komodo_hub' created or already exists.")
        cursor.close()
        connection.close()

        connection, cursor = get_db_cursor("komodo_hub")
        
        # Create tables with filename columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                class_code VARCHAR(50) DEFAULT NULL,
                unique_access_code VARCHAR(10) UNIQUE DEFAULT NULL,
                is_verified TINYINT(1) DEFAULT 0,
                theme VARCHAR(50) DEFAULT 'default',
                avatar_url VARCHAR(255) DEFAULT NULL,  -- Revert to filename
                contribution_points INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_superuser TINYINT(1) DEFAULT 0
            )
        """)

        # Check if unique_access_code column exists, add if not
        cursor.execute("SHOW COLUMNS FROM users LIKE 'unique_access_code'")
        if not cursor.fetchone():
            print("Adding unique_access_code column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN unique_access_code VARCHAR(10) UNIQUE DEFAULT NULL")
            print("unique_access_code column added.")
        else:
            cursor.execute("SHOW COLUMNS FROM users WHERE Field = 'unique_access_code'")
            column_info = cursor.fetchone()
            column_type = column_info[1]
            if 'varchar(255)' in column_type.lower():
                print("Modifying unique_access_code column length back to VARCHAR(10)...")
                cursor.execute("ALTER TABLE users MODIFY COLUMN unique_access_code VARCHAR(10) UNIQUE DEFAULT NULL")
                print("unique_access_code column length updated.")

        # Check if avatar_url exists, add if not
        cursor.execute("SHOW COLUMNS FROM users LIKE 'avatar_url'")
        if not cursor.fetchone():
            print("Adding avatar_url column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255) DEFAULT NULL")
            print("avatar_url column added.")

        # Remove avatar_data if it exists
        cursor.execute("SHOW COLUMNS FROM users LIKE 'avatar_data'")
        if cursor.fetchone():
            print("Dropping avatar_data column from users table...")
            cursor.execute("ALTER TABLE users DROP COLUMN avatar_data")
            print("avatar_data column dropped.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                content TEXT NOT NULL,
                subtopic VARCHAR(255) NOT NULL,
                image_filename VARCHAR(255) DEFAULT NULL,  -- Revert to filename (single image for now)
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved TINYINT(1) DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Remove image_data if it exists
        cursor.execute("SHOW COLUMNS FROM articles LIKE 'image_data'")
        if cursor.fetchone():
            print("Dropping image_data column from articles table...")
            cursor.execute("ALTER TABLE articles DROP COLUMN image_data")
            print("image_data column dropped.")

        # Check if image_filename exists, add if not
        cursor.execute("SHOW COLUMNS FROM articles LIKE 'image_filename'")
        if not cursor.fetchone():
            print("Adding image_filename column to articles table...")
            cursor.execute("ALTER TABLE articles ADD COLUMN image_filename VARCHAR(255) DEFAULT NULL")
            print("image_filename column added.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token VARCHAR(255) NOT NULL,
                purpose VARCHAR(50) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schools (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                class_code VARCHAR(50) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS programs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                class_code VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                class_code VARCHAR(50) NOT NULL,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                correct_answer VARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                program_id INT,
                FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                article_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                UNIQUE (user_id, article_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submit_quiz_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                quiz_id INT NOT NULL,
                answer VARCHAR(255) NOT NULL,
                is_correct TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS school_documents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                class_code VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sightings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                species VARCHAR(255) NOT NULL,
                location VARCHAR(255) NOT NULL,
                sighting_date DATETIME NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                action VARCHAR(255) NOT NULL,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS species (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                scientific_name VARCHAR(255),
                population_estimate INT,
                primary_threat VARCHAR(255),
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
        print("Database tables created successfully.")

        # Insert test teacher account
        teacher_password = "test".encode('utf-8')
        teacher_hashed_password = bcrypt.hashpw(teacher_password, bcrypt.gensalt()).decode('utf-8')
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, is_verified, contribution_points, is_superuser)
            VALUES ('test_teacher', %s, %s, 'teacher', 1, 0, 0)
        """, ('test@gmail.com', teacher_hashed_password))
        cursor.execute("SELECT LAST_INSERT_ID()")
        teacher_id = cursor.fetchone()[0]
        connection.commit()
        print("Test teacher account inserted successfully.")

        # Insert test superuser
        admin_password = "adminpass".encode('utf-8')
        admin_hashed_password = bcrypt.hashpw(admin_password, bcrypt.gensalt()).decode('utf-8')
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, is_verified, is_superuser, contribution_points)
            VALUES ('admin', %s, %s, 'superuser', 1, 1, 0)
        """, ('admin@komodohub.org', admin_hashed_password))
        connection.commit()
        print("Test superuser account inserted successfully.")

        # Insert test users for ClassA and ClassB
        cursor.execute("DELETE FROM users WHERE email LIKE 'teststudent%@example.com'")
        connection.commit()
        test_users = [
            ("teststudent1", "teststudent1@example.com", "student", "ClassA"),
            ("teststudent2", "teststudent2@example.com", "student", "ClassA"),
            ("teststudent3", "teststudent3@example.com", "student", "ClassB"),
            ("teststudent4", "teststudent4@example.com", "student", "ClassB"),
            ("teststudent5", "teststudent5@example.com", "student", "ClassA")
        ]
        password = "password123".encode('utf-8')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        user_ids = []
        for username, email, role, class_code in test_users:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role, class_code, is_verified, contribution_points)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, email, hashed_password, role, class_code, 1, 0))
            cursor.execute("SELECT LAST_INSERT_ID()")
            user_ids.append(cursor.fetchone()[0])
        connection.commit()
        print("Test users inserted successfully.")

        # Insert test schools
        cursor.execute("DELETE FROM schools")
        connection.commit()
        cursor.execute("INSERT INTO schools (name, class_code) VALUES ('Ujung Raya Primary School', 'ClassA')")
        cursor.execute("INSERT INTO schools (name, class_code) VALUES ('Ujung Raya Primary School', 'ClassB')")
        connection.commit()
        print("Test schools inserted successfully.")

        # Insert test programs
        cursor.execute("DELETE FROM programs")
        connection.commit()
        cursor.execute("INSERT INTO programs (name, description, class_code) VALUES ('Javan Rhino Conservation', 'Learn about and contribute to Javan Rhino conservation.', 'ClassA')")
        cursor.execute("INSERT INTO programs (name, description, class_code) VALUES ('Sumatran Tiger Protection', 'Engage in activities to protect Sumatran Tigers.', 'ClassB')")
        connection.commit()
        print("Test programs inserted successfully.")

        # Insert test quizzes
        cursor.execute("DELETE FROM quizzes")
        connection.commit()
        test_quizzes = [
            ("ClassA", "What is the primary threat to the Javan Rhinoceros?", "Habitat loss,Poaching,Pollution", "Habitat loss", 1),
            ("ClassA", "How many Sumatran Tigers are left?", "Less than 100,Less than 500,Less than 1000", "Less than 500", 1),
            ("ClassB", "What is the primary threat to the Javan Rhinoceros?", "Habitat loss,Poaching,Pollution", "Habitat loss", 2),
            ("ClassB", "How many Sumatran Tigers are left?", "Less than 100,Less than 500,Less than 1000", "Less than 500", 2)
        ]
        quiz_ids = []
        for class_code, question, options, correct_answer, program_id in test_quizzes:
            cursor.execute("""
                INSERT INTO quizzes (class_code, question, options, correct_answer, program_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (class_code, question, options, correct_answer, program_id))
            cursor.execute("SELECT LAST_INSERT_ID()")
            quiz_ids.append(cursor.fetchone()[0])
        connection.commit()
        print("Test quizzes inserted successfully.")

        # Insert test articles
        cursor.execute("DELETE FROM articles")
        connection.commit()
        test_articles = [
            ("Javan Rhinoceros", "The Javan Rhinoceros is one of the rarest large mammals on Earth...", user_ids[0], 1),
            ("Sumatran Tiger", "The Sumatran Tiger is critically endangered...", user_ids[1], 1),
            ("Bali Myna", "The Bali Myna is a beautiful white bird...", user_ids[2], 1),
            ("Javan Eagle", "The Javan Eagle is a majestic bird of prey...", user_ids[3], 1),
            ("Tarsier", "Tarsiers are small primates found in Sulawesi...", user_ids[4], 1)
        ]
        article_ids = []
        for subtopic, content, user_id, approved in test_articles:
            cursor.execute("""
                INSERT INTO articles (user_id, content, subtopic, approved)
                VALUES (%s, %s, %s, %s)
            """, (user_id, content, subtopic, approved))
            cursor.execute("SELECT LAST_INSERT_ID()")
            article_ids.append(cursor.fetchone()[0])
        connection.commit()
        print("Test articles inserted successfully.")

        # Insert test likes
        cursor.execute("DELETE FROM likes")
        connection.commit()
        cursor.execute("INSERT INTO likes (user_id, article_id) VALUES (%s, %s)", (user_ids[1], article_ids[0]))
        connection.commit()
        print("Test likes inserted successfully.")

        # Insert test quiz results
        cursor.execute("DELETE FROM submit_quiz_results")
        connection.commit()
        cursor.execute("INSERT INTO submit_quiz_results (user_id, quiz_id, answer, is_correct) VALUES (%s, %s, %s, %s)", (user_ids[0], quiz_ids[0], "Habitat loss", 1))
        connection.commit()
        print("Test quiz results inserted successfully.")

        # Insert test school documents
        cursor.execute("DELETE FROM school_documents")
        connection.commit()
        test_documents = [
            ("ClassA", "Javan Rhinoceros Fact Sheet", "The Javan Rhinoceros is one of the rarest large mammals on Earth..."),
            ("ClassA", "Sumatran Tiger Overview", "The Sumatran Tiger is critically endangered..."),
            ("ClassB", "Javan Rhinoceros Fact Sheet", "The Javan Rhinoceros is one of the rarest large mammals on Earth..."),
            ("ClassB", "Sumatran Tiger Overview", "The Sumatran Tiger is critically endangered...")
        ]
        cursor.executemany("INSERT INTO school_documents (class_code, title, content) VALUES (%s, %s, %s)", test_documents)
        connection.commit()
        print("Test school documents inserted successfully.")

        # Insert test species data
        cursor.execute("DELETE FROM species")
        connection.commit()
        species_data = [
            ("Sumatran Tiger", "Panthera tigris sumatrae", 400, "Habitat loss", "A critically endangered tiger species native to Sumatra."),
            ("Javan Rhinoceros", "Rhinoceros sondaicus", 75, "Habitat loss", "One of the rarest large mammals, found only in Ujung Kulon."),
            ("Bali Myna", "Leucopsar rothschildi", 100, "Poaching", "A striking white bird endemic to Bali."),
            ("Javan Eagle", "Nisaetus bartelsi", 200, "Habitat loss", "An endemic raptor of Java’s forests."),
            ("Tarsier", "Tarsius spp.", 500, "Habitat loss", "Small primates from Sulawesi and nearby islands.")
        ]
        cursor.executemany("INSERT INTO species (name, scientific_name, population_estimate, primary_threat, description) VALUES (%s, %s, %s, %s, %s)", species_data)
        connection.commit()
        print("Test species data inserted successfully.")

    except mysql.connector.Error as err:
        print(f"Error creating tables: {err}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

def save_article(user_id, content, subtopic, image_filename=None):
    connection, cursor = get_db_cursor()
    try:
        query = """
            INSERT INTO articles (user_id, content, subtopic, image_filename, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (user_id, content, subtopic, image_filename, datetime.now()) if image_filename else (user_id, content, subtopic, None, datetime.now())
        cursor.execute(query, values)
        connection.commit()
    except mysql.connector.Error as err:
        connection.rollback()
        raise Exception(f"Database error: {err}")
    finally:
        cursor.close()
        connection.close()

def save_like(user_id, article_id):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("INSERT IGNORE INTO likes (user_id, article_id) VALUES (%s, %s)", (user_id, article_id))
        connection.commit()
        cursor.execute("UPDATE users SET contribution_points = COALESCE(contribution_points, 0) + 1 WHERE id = (SELECT user_id FROM articles WHERE id = %s)", (article_id,))
        connection.commit()
    except mysql.connector.Error as err:
        connection.rollback()
        raise Exception(f"Database error: {err}")
    finally:
        cursor.close()
        connection.close()

def log_action(user_id, action, details=None):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("INSERT INTO audit_logs (user_id, action, details, created_at) VALUES (%s, %s, %s, NOW())", (user_id, action, details))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def update_avatar(user_id, avatar_filename):
    connection, cursor = get_db_cursor()
    try:
        cursor.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (avatar_filename, user_id))
        connection.commit()
    except mysql.connector.Error as err:
        connection.rollback()
        raise Exception(f"Database error: {err}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    setup_database()