"""Check current state of production DB before running migration."""
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
os.environ.pop("FLASK_ENV", None)

from app import create_app
from sqlalchemy import text

app = create_app()
with app.app_context():
    engine = app.extensions["migrate"].db.engine
    with engine.connect() as c:
        try:
            r = c.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            print("alembic version:", r[0] if r else None)
        except Exception as e:
            print("alembic_version error:", e)

        try:
            rows = c.execute(text("SELECT id, name FROM roles ORDER BY id")).fetchall()
            print("roles:", [(r.id, r.name) for r in rows])
        except Exception as e:
            print("roles error:", e)

        try:
            rows = c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='departments' ORDER BY ordinal_position"
            )).fetchall()
            print("departments cols:", [r.column_name for r in rows])
        except Exception as e:
            print("departments cols error:", e)

        try:
            rows = c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='permissions' ORDER BY ordinal_position"
            )).fetchall()
            print("permissions cols:", [r.column_name for r in rows])
            rows = c.execute(text("SELECT id, name FROM permissions ORDER BY id")).fetchall()
            print("permissions rows:", [(r.id, r.name) for r in rows])
        except Exception as e:
            print("permissions error:", e)

        try:
            rows = c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='ratings' ORDER BY ordinal_position"
            )).fetchall()
            print("ratings cols:", [r.column_name for r in rows])
            rows = c.execute(text("SELECT count(*) FROM ratings")).fetchone()
            print("ratings count:", r[0] if rows else 0)
        except Exception as e:
            print("ratings error:", e)