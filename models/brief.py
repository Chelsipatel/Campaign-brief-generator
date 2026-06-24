from database import get_db


class Brief:
    @staticmethod
    def save(org_name, cause, audience, tone, goal, platforms, brief_text):
        db = get_db()
        db.execute(
            """INSERT INTO briefs (org_name, cause, audience, tone, platforms, goal, brief_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (org_name, cause, audience, tone, ",".join(platforms), goal, brief_text),
        )
        db.commit()

    @staticmethod
    def all():
        db = get_db()
        return db.execute(
            "SELECT * FROM briefs ORDER BY created_at DESC"
        ).fetchall()

    @staticmethod
    def get(brief_id):
        db = get_db()
        return db.execute(
            "SELECT * FROM briefs WHERE id = ?", (brief_id,)
        ).fetchone()

    @staticmethod
    def delete(brief_id):
        db = get_db()
        db.execute("DELETE FROM briefs WHERE id = ?", (brief_id,))
        db.commit()
