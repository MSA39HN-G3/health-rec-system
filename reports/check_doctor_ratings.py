"""Check doctor_ratings table on production DB."""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
os.environ.pop("FLASK_ENV", None)

from app import create_app
from sqlalchemy import text

app = create_app()
with app.app_context():
    engine = app.extensions["migrate"].db.engine
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name='doctor_ratings'"
        )).fetchall()
        print("doctor_ratings table exists:", len(rows) > 0)
        if rows:
            cnt = c.execute(text("SELECT count(*) FROM doctor_ratings")).scalar()
            print("count:", cnt)
        # Also doctor_statistics
        rows = c.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name='doctor_statistics'"
        )).fetchall()
        print("doctor_statistics table exists:", len(rows) > 0)
        if rows:
            cnt = c.execute(text("SELECT count(*) FROM doctor_statistics")).scalar()
            print("count:", cnt)