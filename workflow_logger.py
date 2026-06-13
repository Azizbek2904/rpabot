"""
📊 Workflow Logger — FIXED
Author: BTEC L6 | PDP University
Fixes: thread safety, proper file handling, error resilience
"""
import os
import json
import csv
import threading
from datetime import datetime

LOG_DIR = "logs"
OPS_FILE = os.path.join(LOG_DIR, "ops.csv")
STATS_FILE = os.path.join(LOG_DIR, "stats.json")


class WorkflowLogger:
    """Thread-safe operation logger for RPA bot."""

    def __init__(self):
        self._lock = threading.Lock()
        os.makedirs(LOG_DIR, exist_ok=True)
        if not os.path.exists(OPS_FILE):
            with open(OPS_FILE, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["timestamp", "operation", "chat_id", "details", "status"])

    def log(self, operation, chat_id, details="", status="ok"):
        """Log an operation (thread-safe)."""
        with self._lock:
            try:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(OPS_FILE, "a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow([ts, operation, chat_id, details, status])

                # Update daily stats
                date_key = datetime.now().strftime("%Y-%m-%d")
                stats = {}
                if os.path.exists(STATS_FILE):
                    with open(STATS_FILE, "r", encoding="utf-8") as f:
                        stats = json.load(f)

                if date_key not in stats:
                    stats[date_key] = {"total": 0, "ok": 0, "error": 0, "ops": {}}

                day = stats[date_key]
                day["total"] += 1
                day["ok" if status == "ok" else "error"] += 1
                day["ops"][operation] = day["ops"].get(operation, 0) + 1

                with open(STATS_FILE, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Logger error: {e}")

    def get_today_stats(self):
        """Get today's operation statistics."""
        with self._lock:
            try:
                if os.path.exists(STATS_FILE):
                    with open(STATS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return data.get(datetime.now().strftime("%Y-%m-%d"), {})
            except Exception:
                pass
            return {}

    def get_all_stats(self):
        """Get all statistics."""
        with self._lock:
            try:
                if os.path.exists(STATS_FILE):
                    with open(STATS_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                pass
            return {}

    def get_operations_log(self, limit=50):
        """Get recent operations log entries."""
        with self._lock:
            try:
                rows = []
                with open(OPS_FILE, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        rows.append(row)
                return rows[-limit:]
            except Exception:
                return []
