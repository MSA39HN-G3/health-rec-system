"""Check doctor_statistics columns."""
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
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='doctor_statistics' ORDER BY ordinal_position"
        )).fetchall()
        print("doctor_statistics cols:", [r.column_name for r in rows])
        rows = c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='doctor_ratings' ORDER BY ordinal_position"
        )).fetchall()
        print("doctor_ratings cols:", [r.column_name for r in rows])