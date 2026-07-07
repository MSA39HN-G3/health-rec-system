"""Repository layer for Patient model — encapsulates database queries."""
from ..extensions import db
from ..models.patient import Patient


class PatientRepository:
    """Handles data access for Patient records."""
    def find_by_id(self, patient_id):
        """Find patient by ID.
        
        Args:
            patient_id (int): Patient ID to search for.
            
        Returns:
            Patient: Patient object if found, None otherwise.
        """
        return db.session.get(Patient, patient_id)

    def paginate(self, page, size):
        """Fetch paginated list of patients.
        
        Args:
            page (int): Page number (1-indexed).
            size (int): Number of items per page.
            
        Returns:
            tuple: (list of Patient objects, total count).
        """
        query = Patient.query.order_by(Patient.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, patient):
        """Add patient to session for insertion.
        
        Args:
            patient (Patient): Patient object to add.
            
        Returns:
            Patient: The added patient object.
        """
        db.session.add(patient)
        return patient

    def count(self):
        """Count total number of patients in database.
        
        Returns:
            int: Total count of patients.
        """
        return Patient.query.count()

    def commit(self):
        """Commit all changes in current session to database."""
        db.session.commit()
