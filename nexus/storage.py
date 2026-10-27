"""SQLite-backed local conversations, settings and reminders."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import datetime

APP_DIR = Path.home() / ".nexus_ai"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "nexus.sqlite3"

class Store:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._init()
    def _connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con
    def _init(self):
        with self._connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, title TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created TEXT NOT NULL, FOREIGN KEY(conversation_id) REFERENCES conversations(id));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, title TEXT NOT NULL, due TEXT, done INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
            ''')
    def setting(self, key, default=None):
        with self._connect() as c:
            row = c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
            if not row: return default
            try: return json.loads(row['value'])
            except Exception: return row['value']
    def set_setting(self, key, value):
        with self._connect() as c:
            c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))
    def create_conversation(self, title='New conversation'):
        with self._connect() as c:
            cur=c.execute('INSERT INTO conversations(title,created) VALUES(?,?)',(title,datetime.now().isoformat(timespec='seconds')))
            return cur.lastrowid
    def conversations(self):
        with self._connect() as c: return [dict(r) for r in c.execute('SELECT * FROM conversations ORDER BY id DESC')]
    def add_message(self, cid, role, content):
        with self._connect() as c:
            c.execute('INSERT INTO messages(conversation_id,role,content,created) VALUES(?,?,?,?)',(cid,role,content,datetime.now().isoformat(timespec='seconds')))
            if role=='user':
                row=c.execute('SELECT title FROM conversations WHERE id=?',(cid,)).fetchone()
                if row and row['title']=='New conversation':
                    title=' '.join(content.split())[:48] or 'New conversation'
                    c.execute('UPDATE conversations SET title=? WHERE id=?',(title,cid))
    def messages(self, cid):
        with self._connect() as c: return [dict(r) for r in c.execute('SELECT role,content,created FROM messages WHERE conversation_id=? ORDER BY id',(cid,))]
    def delete_conversation(self,cid):
        with self._connect() as c:
            c.execute('DELETE FROM messages WHERE conversation_id=?',(cid,)); c.execute('DELETE FROM conversations WHERE id=?',(cid,))
    def add_reminder(self,title,due=''):
        with self._connect() as c: c.execute('INSERT INTO reminders(title,due,created) VALUES(?,?,?)',(title,due,datetime.now().isoformat(timespec='seconds')))
    def reminders(self):
        with self._connect() as c: return [dict(r) for r in c.execute('SELECT * FROM reminders ORDER BY done,due,id DESC')]
    def complete_reminder(self,rid,done=True):
        with self._connect() as c: c.execute('UPDATE reminders SET done=? WHERE id=?',(int(done),rid))
