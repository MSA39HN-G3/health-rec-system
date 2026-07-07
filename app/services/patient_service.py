from datetime import datetime

from ..errors import BadRequestException, NotFoundException
from ..models.patient import Patient
from ..repositories.patient_repository import PatientRepository


class PatientService:
    def __init__(self, patient_repository=None):
        self.patients = patient_repository or PatientRepository()

    def count_patients(self):
        return self.patients.count()

    def list_patients(self, page, size):
        return self.patients.paginate(page, size)

    def get_patient(self, patient_id):
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
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                raise BadRequestException("errors.invalid_date_format")
        raise BadRequestException("errors.invalid_date_format")
