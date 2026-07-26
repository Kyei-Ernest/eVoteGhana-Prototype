from database import DatabaseManager


def log_action(action: str, table_name: str, record_id: str | int, details: str, actor: str = "system") -> None:
    try:
        with DatabaseManager() as db:
            sql = "INSERT INTO audit_log (action, table_name, record_id, details, actor) VALUES (%s, %s, %s, %s, %s)"
            db.execute_query(sql, (action, table_name, str(record_id), str(details), actor))
    except Exception as e:
        print(f"Audit log error: {e}")


def get_audit_trail(table_name: str | None = None, record_id: str | None = None, limit: int = 100) -> list[tuple]:
    try:
        with DatabaseManager() as db:
            if table_name and record_id:
                sql = "SELECT * FROM audit_log WHERE table_name = %s AND record_id = %s ORDER BY created_at DESC LIMIT %s"
                db.execute_query(sql, (table_name, str(record_id), limit))
            elif table_name:
                sql = "SELECT * FROM audit_log WHERE table_name = %s ORDER BY created_at DESC LIMIT %s"
                db.execute_query(sql, (table_name, limit))
            else:
                sql = "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT %s"
                db.execute_query(sql, (limit,))
            return db.fetch_all()
    except Exception as e:
        print(f"Audit trail error: {e}")
        return []
