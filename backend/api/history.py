from fastapi import APIRouter

from db.database import get_connection, get_search_history, delete_search_history, get_sessions_by_history

router = APIRouter()


@router.get("")
def list_history():
    conn = get_connection()
    rows = get_search_history(conn)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{history_id}/sessions")
def list_sessions(history_id: int):
    conn = get_connection()
    sessions = get_sessions_by_history(conn, history_id)
    conn.close()
    return [dict(r) for r in sessions]


@router.delete("/{history_id}")
def remove_history(history_id: int):
    conn = get_connection()
    delete_search_history(conn, history_id)
    conn.close()
    return {"status": "deleted"}
