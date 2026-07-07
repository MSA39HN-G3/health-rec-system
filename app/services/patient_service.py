"""Service layer for Patient — encapsulates business logic."""
from datetime import datetime

from ..errors import BadRequestException, NotFoundException
from ..models.patient import Patient
from ..repositories.patient_repository import PatientRepository


class PatientService:
    """Handles business logic for patient management operations."""
    def __init__(self, patient_repository=None):
        self.patients = patient_repository or PatientRepository()

    def count_patients(self):
        """Get total count of all patients.
        
        Returns:
            int: Total number of patients in database.
        """
        return self.patients.count()

    def list_patients(self, page, size):
        """Fetch paginated list of patients.
        
        Args:
            page (int): Page number (1-indexed).
            size (int): Number of items per page.
            
        Returns:
            tuple: (list of Patient dicts, total count).
        """
        return self.patients.paginate(page, size)

    def get_patient(self, patient_id):
        """Retrieve patient by ID.
        
        Args:
            patient_id (int): Patient ID.
            
        Returns:
            Patient: Patient object.
            
        Raises:
            NotFoundException: If patient not found.
        """
        patient = self.patients.find_by_id(patient_id)
        if patient is None:
            raise NotFoundException("errors.patient_not_found")
        return patient

    def create_patient(
        self,
        full_name,
        date_of_birth=None,
        gender=None,
        phone=None,
        email=None,
        address=None,
    ):
        """Create new patient record.
        
        Args:
            full_name (str): Patient full name (required).
            date_of_birth (str, optional): ISO format date string.
            gender (str, optional): Patient gender.
            phone (str, optional): Contact phone number.
            email (str, optional): Email address.
            address (str, optional): Physical address.
            
        Returns:
            Patient: Newly created patient object.
            
        Raises:
            BadRequestException: If date format invalid.
        """
        patient = Patient(
            full_name=full_name,
            date_of_birth=self._parse_date(date_of_birth),
            gender=gender,
            phone=phone,
            email=email,
            address=address,
        )
        self.patients.add(patient)
        self.patients.commit()
        return patient

    def update_patient(
        self,
        patient_id,
        *,
        full_name=None,
        date_of_birth=None,
        gender=None,
        phone=None,
        email=None,
        address=None,
    ):
        """Update existing patient record (only specified fields).
        
        Args:
            patient_id (int): Patient ID to update.
            full_name (str, optional): New full name.
            date_of_birth (str, optional): New date of birth (ISO format).
            gender (str, optional): New gender.
            phone (str, optional): New phone number.
            email (str, optional): New email.
            address (str, optional): New address.
            
        Returns:
            Patient: Updated patient object.
            
        Raises:
            NotFoundException: If patient not found.
            BadRequestException: If date format invalid.
        """
        patient = self.get_patient(patient_id)
        if full_name is not None:
            patient.full_name = full_name
        if date_of_birth is not None:
            patient.date_of_birth = self._parse_date(date_of_birth)
        if gender is not None:
            patient.gender = gender
        if phone is not None:
            patient.phone = phone
        if email is not None:
            patient.email = email
        if address is not None:
            patient.address = address
        self.patients.commit()
        return patient

    def _parse_date(self, value):
        """Parse ISO format date string to date object.
        
        Args:
            value (str or None): ISO format date string (e.g., '2000-01-15').
            
        Returns:
            date or None: Parsed date object, or None if input is None.
            
        Raises:
            BadRequestException: If date format is invalid.
        """
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                raise BadRequestException("errors.invalid_date_format")
        raise BadRequestException("errors.invalid_date_format")
