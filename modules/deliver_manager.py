# ============================================
# modules/deliver_manager.py 鈥� 鍏�鑷�鍔�鎶�閫�绠�瀹�
# 澶�鐧�璇�锛�璐�璐�鎶�鎶�閫�璁�褰�鍐�杩�鏁�鎹�搴�锛�骞�闅�鏃�杩�韪�闈�璇�鐘�鎬�
# ============================================

import sqlite3
import hashlib
from datetime import datetime
from modules.db_client import get_connection

class DeliverManager:
    """鎶�閫�绠�瀹�锛�涓�闂�璐�璐�鍜� deliveries 鎶�灞�鎵�浜�閬�"""

    def _ensure_notes_column(self):
        """纭�淇� deliveries 琛�閲�鏈� notes 瀛�娈�锛�鍏�瀹�涔�鍓�娌�寤�杩�涓�鏍�瀛�鐨�鎯�鍐�锛�"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # 灏�璇�鏌�璇� notes锛�濡�鏋�鎶�閿�璇�鏄�娌�鏈�杩�涓�瀛�娈�锛�鎴�浠�灏�涓�鏃�鍔�涓�涓�
            try:
                cursor.execute("SELECT notes FROM deliveries LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE deliveries ADD COLUMN notes TEXT")
                conn.commit()
            conn.close()
        except Exception:
            pass

    def __init__(self):
        self._ensure_notes_column()

    def mark_delivered(self, url, title, company, salary, score, notes, resume_filename="unknown.json"):
        """
        璁�褰�涓�鏉�鏂�鎶�閫�
        澶�鐧�璇�锛�鍦�灏�鏈�鏈�涓�璁�涓�涓�绗�鈥�浠�澶�鐢�鏌�浠�绠�鍘�鎶�浜�杩�涓�鍏�鍙�鈥�
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. 鍥�涓�涔�鍓�鐨�绯�缁�鏄�闈� URL 璁�浜�鐨�锛�鎴�浠�瑕�鍏�鍘� jobs 鎶�灞�閲�鎵�鎵�鐪�鏈�娌�鏈�杩�涓�宀�浣�
            cursor.execute("SELECT job_id FROM jobs WHERE url = ?", (url,))
            row = cursor.fetchone()
            
            if row:
                job_id = row["job_id"]
            else:
                # 濡�鏋�杩�涓�宀�浣�鏄�浠�鍓�鎵�鍔�鐨�锛�娌�鍦�搴�閲�锛�閭�鎴�浠�灏�褰�鍦�缁�瀹�鍔�涓�鈥�涓�鏃�韬�浠�璇�鈥�瀛�杩� jobs
                job_id = "manual_" + hashlib.md5((url + company).encode()).hexdigest()[:10]
                cursor.execute('''
                    INSERT INTO jobs (job_id, platform, title, company, salary, url)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (job_id, "manual", title, company, salary, url))
                
            # 2. 妫�鏌�鏄�涓�鏄�宸�缁�鎶�杩�杩�涓�宀�浣�浜�锛�闃�閲�澶�鎶�閫�锛�
            cursor.execute("SELECT id FROM deliveries WHERE job_id = ?", (job_id,))
            if cursor.fetchone():
                return {"ok": False, "error": "璇�宀�浣�宸�鎶�閫�杩�锛�璇�鍕�閲�澶�鎶�閫�锛�"}
                
            # 3. 姝�寮�鎶�绾�绾�锛�鎶�閫�璁�褰�锛�鍐�杩� deliveries 鎶�灞�
            cursor.execute('''
                INSERT INTO deliveries (job_id, resume_filename, status, match_score, notes)
                VALUES (?, ?, 'delivered', ?, ?)
            ''', (job_id, resume_filename, score, notes))
            
            conn.commit()
            return {"ok": True, "msg": "鎶�閫�璁�褰�宸�鎴�鍔�鍏�搴�锛�"}
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            conn.close()

    def get_history(self):
        """
        鑾�鍙�鎵�鏈�鍘�鍙�鎶�閫�璁�褰�
        澶�鐧�璇�锛�鎶�鎶�閫�灏�鏈�鏈�杩�鍚�宀�浣�璇�鎯�涓�璧�浜�缁�浣�瀹�鏌�
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 鏂�灞� SQL 榄�娉�锛�JOIN锛�锛�鍚�鏃�浠� deliveries 鍜� jobs 鎶�灞�閲�鎷�涓�瑗�锛�鎷�鍦�涓�璧�缁�浣�鐪�锛�
            cursor.execute('''
                SELECT 
                    d.id as delivery_id,
                    d.status,
                    d.match_score as score,
                    d.notes,
                    d.created_at as delivered_at,
                    j.title,
                    j.company,
                    j.salary,
                    j.url
                FROM deliveries d
                LEFT JOIN jobs j ON d.job_id = j.job_id
                ORDER BY d.created_at DESC
            ''')
            rows = cursor.fetchall()
            history = []
            for r in rows:
                history.append({
                    "id": r["delivery_id"],
                    "title": r["title"],
                    "company": r["company"],
                    "salary": r["salary"],
                    "url": r["url"],
                    "score": r["score"],
                    "notes": r["notes"],
                    "status": r["status"],
                    # 鎶�鏃�闂�鏍�寮�鍖�鎴�婕�浜�鐨�瀛�绗�涓�
                    "delivered_at_display": r["delivered_at"]
                })
            return history
        finally:
            conn.close()

    def update_status(self, delivery_id, new_status):
        """
        鏇�鏂�鎶�閫�鐘�鎬�
        澶�鐧�璇�锛�姣�濡�鎶�鈥�宸�鎶�閫�鈥�鏀�鎴�鈥�鏀�鍒�闈�璇�鈥�锛�杩�閲�灏�鏄�淇�鏀�鐘�鎬�鐨�鍦�鏂�
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE deliveries SET status = ? WHERE id = ?", (new_status, delivery_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    def undo_deliver(self, url):
        """
        撤销投递（根据URL）
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT job_id FROM jobs WHERE url = ?", (url,))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM deliveries WHERE job_id = ?", (row["job_id"],))
                conn.commit()
                return cursor.rowcount > 0
            return False
        finally:
            conn.close()
