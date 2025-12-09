# file: database.py

import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_NAME = 'specialists.db'

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS specialists (
                user_id INTEGER PRIMARY KEY,
                specialization TEXT,
                skills TEXT,
                experience TEXT,
                portfolio_url TEXT,
                contact_info TEXT,
                is_active INTEGER DEFAULT 0, 
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER,
                rater_id INTEGER,
                score INTEGER,
                target_role TEXT, 
                FOREIGN KEY (target_id) REFERENCES users (user_id),
                FOREIGN KEY (rater_id) REFERENCES users (user_id),
                UNIQUE(target_id, rater_id, target_role) 
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                specialist_id INTEGER,
                status TEXT DEFAULT 'pending',
                finish_requested_by INTEGER DEFAULT NULL,
                client_rated INTEGER DEFAULT 0,
                specialist_rated INTEGER DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES users (user_id),
                FOREIGN KEY (specialist_id) REFERENCES specialists (user_id)
            )
        ''')
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error on init: {e}")
    finally:
        if conn: conn.close()

# --- Користувачі ---
def register_user(user_id, username, full_name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                (user_id, username, full_name))
    cur.execute("SELECT user_id FROM specialists WHERE user_id = ?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO specialists (user_id, is_active) VALUES (?, 0)", (user_id,))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT full_name, username FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result

def get_user_info(user_id):
    data = get_user_data(user_id)
    return data[1] if data else "Невідомий"

def get_client_details_full(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT full_name, username FROM users WHERE user_id = ?", (user_id,))
    user_res = cur.fetchone()
    cur.execute("SELECT AVG(score), COUNT(score) FROM ratings WHERE target_id = ? AND target_role = 'client'", (user_id,))
    rating_res = cur.fetchone()
    conn.close()
    if user_res:
        avg = round(rating_res[0], 1) if rating_res[0] else 0.0
        count = rating_res[1] if rating_res[1] else 0
        return {"name": user_res[0], "username": user_res[1], "rating": avg, "reviews": count}
    return None

# --- Фахівці ---
def update_specialist_profile(user_id, profile_data, activate=True):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    is_active = 1 if activate else 0
    cur.execute('''
        UPDATE specialists 
        SET specialization=?, skills=?, experience=?, portfolio_url=?, contact_info=?, is_active=?
        WHERE user_id=?
    ''', (profile_data.get('specialization'), profile_data.get('skills'), 
          profile_data.get('experience'), profile_data.get('portfolio_url'), 
          profile_data.get('contact_info'), is_active, user_id))
    if cur.rowcount == 0:
        cur.execute('''
            INSERT INTO specialists (user_id, specialization, skills, experience, portfolio_url, contact_info, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, profile_data.get('specialization'), profile_data.get('skills'), 
              profile_data.get('experience'), profile_data.get('portfolio_url'), 
              profile_data.get('contact_info'), is_active))
    conn.commit()
    conn.close()

def search_specialists(query):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.user_id, u.full_name, s.specialization, s.skills 
        FROM specialists s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.is_active = 1 AND lower(s.skills) LIKE ?
    """, (f'%{query.lower()}%',))
    results = cur.fetchall()
    conn.close()
    return results

def search_specialists_by_spec(specialization):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.user_id, u.full_name, s.specialization, s.skills 
        FROM specialists s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.is_active = 1 AND s.specialization = ?
    """, (specialization,))
    results = cur.fetchall()
    conn.close()
    return results

def get_specialist_details(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.user_id, u.full_name, s.specialization, s.skills, s.experience, s.portfolio_url, s.contact_info, s.is_active
        FROM specialists s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.user_id = ?
    """, (user_id,))
    result = cur.fetchone()
    conn.close()
    return result

# --- Рейтинги ---
def add_rating(target_id, rater_id, score, role_type):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT OR REPLACE INTO ratings (target_id, rater_id, score, target_role) 
            VALUES (?, ?, ?, ?)
        """, (target_id, rater_id, score, role_type))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error rating: {e}")
        return False
    finally:
        conn.close()

def get_rating(user_id, role_type):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT AVG(score), COUNT(score) FROM ratings WHERE target_id = ? AND target_role = ?", (user_id, role_type))
    result = cur.fetchone()
    conn.close()
    return round(result[0], 1) if result[0] else 0.0, result[1] if result[1] else 0

# --- Замовлення ---
def create_order(client_id, specialist_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM orders WHERE (client_id = ? OR specialist_id = ?) AND status IN ('active', 'pending', 'finish_request')", (client_id, specialist_id))
    if cur.fetchone():
        conn.close()
        return None
    cur.execute("INSERT INTO orders (client_id, specialist_id, status, client_rated, specialist_rated) VALUES (?, ?, 'pending', 0, 0)", (client_id, specialist_id))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_active_order(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE (client_id = ? OR specialist_id = ?) AND status IN ('active', 'pending', 'finish_request')", (user_id, user_id))
    result = cur.fetchone()
    conn.close()
    return result

def get_order_by_id(order_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    result = cur.fetchone()
    conn.close()
    return result

def get_last_completed_order(user1_id, user2_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM orders 
        WHERE ((client_id=? AND specialist_id=?) OR (client_id=? AND specialist_id=?))
        AND status='completed' 
        ORDER BY id DESC LIMIT 1
    """, (user1_id, user2_id, user2_id, user1_id))
    result = cur.fetchone()
    conn.close()
    return result

def update_order_status(order_id, new_status, finish_requested_by=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if finish_requested_by:
        cur.execute("UPDATE orders SET status = ?, finish_requested_by = ? WHERE id = ?", (new_status, finish_requested_by, order_id))
    else:
        cur.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

def set_order_rated(order_id, role_who_rated):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if role_who_rated == 'client':
        cur.execute("UPDATE orders SET client_rated = 1 WHERE id = ?", (order_id,))
    else:
        cur.execute("UPDATE orders SET specialist_rated = 1 WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

def cancel_order_db(order_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()