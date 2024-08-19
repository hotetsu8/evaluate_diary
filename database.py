import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'diaries.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # ユーザーテーブルの作成
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL)''')
    
    # 日記テーブルの作成（user_idカラムを含む）
    c.execute('''CREATE TABLE IF NOT EXISTS diaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  title TEXT,
                  content TEXT,
                  sentiment TEXT,
                  score REAL,
                  created_at TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # テーブルが存在するか確認
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='diaries'")
    table_exists = c.fetchone()

    if not table_exists:
        # テーブルが存在しない場合、新しく作成
        c.execute('''CREATE TABLE diaries
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      title TEXT,
                      content TEXT,
                      sentiment TEXT,
                      score REAL,
                      created_at TIMESTAMP)''')
    else:
        # テーブルが存在する場合、必要なカラムを追加
        try:
            c.execute("ALTER TABLE diaries ADD COLUMN title TEXT")
        except sqlite3.OperationalError:
            # カラムが既に存在する場合は無視
            pass

    conn.commit()
    conn.close()

def add_user(username, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    normalized_username = username.lower().strip()
    c.execute("SELECT * FROM users WHERE LOWER(username) = ?", (normalized_username,))
    existing_user = c.fetchone()
    if existing_user:
        conn.close()
        return False  # ユーザー名が既に存在する場合
    c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
              (username, generate_password_hash(password)))
    conn.commit()
    conn.close()
    return True

def get_user(username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    normalized_username = username.lower().strip()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def get_diary_count_for_today(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    today = datetime.now().date()
    c.execute("SELECT COUNT(*) FROM diaries WHERE user_id = ? AND DATE(created_at) = DATE(?)", (user_id, today))
    count = c.fetchone()[0]
    conn.close()
    return count


def add_diary(user_id, title, content, sentiment, score):
    print(f"Adding diary: user_id={user_id}, title={title}")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    print(f"Diary added successfully: id={c.lastrowid}")
    
    try:
        today = datetime.now().date()
        c.execute("SELECT COUNT(*) FROM diaries WHERE DATE(created_at) = DATE(?) AND user_id = ?", (today, user_id))
        count = c.fetchone()[0]
        
        if count < 3:
            if not title:
                title = f"日記 - {today}"
            c.execute("INSERT INTO diaries (user_id, title, content, sentiment, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (user_id, title, content, sentiment, float(score), datetime.now()))
            conn.commit()
            return True
        else:
            return False
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def get_all_diaries(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        SELECT id, title, content, score, DATE(created_at) as date
        FROM diaries 
        WHERE user_id = ?
        ORDER BY date DESC, created_at DESC
    """, (user_id,))
    diaries = c.fetchall()
    conn.close()
    
    processed_diaries = {}
    for id, title, content, score, date in diaries:
        if date not in processed_diaries:
            processed_diaries[date] = {'entries': [], 'avg_score': 0}
        processed_diaries[date]['entries'].append({'id': id, 'title': title or 'No Title', 'content': content, 'score': round(score)})
    
    for date, data in processed_diaries.items():
        data['avg_score'] = round(sum(entry['score'] for entry in data['entries']) / len(data['entries']))
    
    return processed_diaries

def get_diary(id, user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM diaries WHERE id = ? AND user_id = ?", (id, user_id))
    diary = c.fetchone()
    conn.close()
    return diary

def update_diary(id, user_id, title, content, sentiment, score):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE diaries 
            SET title = ?, content = ?, sentiment = ?, score = ? 
            WHERE id = ? AND user_id = ?
        """, (title, content, sentiment, float(score), id, user_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error updating diary: {e}")
        return False
    finally:
        conn.close()

def delete_diary(id, user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM diaries WHERE id = ? AND user_id = ?", (id, user_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error deleting diary: {e}")
        return False
    finally:
        conn.close()

def get_diaries_for_month(user_id, year, month):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        query = """
            SELECT DATE(created_at) as date, COUNT(*) as count, ROUND(AVG(score)) as avg_score, 
                   GROUP_CONCAT(title) as titles, GROUP_CONCAT(content) as contents, GROUP_CONCAT(score) as scores
            FROM diaries 
            WHERE user_id = ? AND strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
            GROUP BY DATE(created_at)
        """
        c.execute(query, (user_id, str(year), f"{month:02d}"))
        
        rows = c.fetchall()
        
        diaries = {}
        for row in rows:
            date, count, avg_score, titles, contents, scores = row
            formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d')
            diaries[formatted_date] = {
                'count': count,
                'avg_score': round(float(avg_score)) if avg_score else 0,
                'titles': titles.split(',') if titles else [],
                'contents': contents.split(',') if contents else [],
                'scores': [round(float(score)) for score in scores.split(',')] if scores else []
            }
        
        return diaries
    except sqlite3.OperationalError as e:
        print(f"Error in get_diaries_for_month: {e}")
        return {}
    finally:
        conn.close()

def check_table_structure():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("PRAGMA table_info(diaries)")
    columns = c.fetchall()
    conn.close()
    print("Table structure:", columns)