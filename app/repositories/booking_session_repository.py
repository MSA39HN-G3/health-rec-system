from ..extensions import db
from ..models.booking_session import BookingSession, BookingSessionSymptom


class BookingSessionRepository:
    """Repository handling database operations for BookingSession models."""

    def find_by_id(self, session_id):
        """Find booking session by ID.

        Args:
            session_id (str): Session ID.

        Returns:
            BookingSession: BookingSession object if found, None otherwise.
        """
        return db.session.get(BookingSession, session_id)

    def add(self, session):
        """Add booking session to the current database session.

        Args:
            session (BookingSession): Session object.

        Returns:
            BookingSession: The added session object.
        """
        db.session.add(session)
        return session

    def add_session_symptom(self, session_symptom):
        """Add session symptom link to the database session.

        Args:
            session_symptom (BookingSessionSymptom): Relation object.

        Returns:
            BookingSessionSymptom: The added object.
        """
        db.session.add(session_symptom)
        return session_symptom

    def commit(self):
        """Commit all changes in current session to database."""
        db.session.commit()

    def rollback(self):
        """Rollback current database session changes."""
        db.session.rollback()
