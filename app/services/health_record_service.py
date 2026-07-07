from datetime import datetime

from ..errors import BadRequestException, NotFoundException
from ..models.health_record import HealthRecord
from ..repositories.department_repository import DepartmentRepository
from ..repositories.health_record_repository import HealthRecordRepository
from ..repositories.patient_repository import PatientRepository
from ..repositories.user_repository import UserRepository


class HealthRecordService:
    def __init__(
        self,
        health_record_repository=None,
        patient_repository=None,
        doctor_repository=None,
        department_repository=None,
    ):
        self.records = health_record_repository or HealthRecordRepository()
        self.patients = patient_repository or PatientRepository()
        self.doctors = doctor_repository or UserRepository()
        self.departments = department_repository or DepartmentRepository()

    def list_records(self, patient_id, page, size):
        self._ensure_patient_exists(patient_id)
        return self.records.paginate_by_patient(page, size, patient_id)

    def get_record(self, patient_id, record_id):
        record = self.records.find_by_patient_and_id(patient_id, record_id)
        if record is None:
            raise NotFoundException("errors.health_record_not_found")
        return record

    def create_record(
        self,
        patient_id,
        title,
        visit_date=None,
        doctor_id=None,
        department_id=None,
        notes=None,
        diagnosis=None,
        treatment=None,
    ):
        self._ensure_patient_exists(patient_id)
        doctor = None
        if doctor_id is not None:
            doctor = self.doctors.find_by_id(doctor_id)
            if doctor is None:
                raise NotFoundException("errors.doctor_not_found")
        department = None
        if department_id is not None:
            department = self.departments.find_by_id(department_id)
            if department is None:
                raise NotFoundException("errors.department_not_found")
        record = HealthRecord(
            patient_id=patient_id,
            title=title,
            visit_date=self._parse_datetime(visit_date),
            doctor_id=doctor_id,
            department_id=department_id,
            notes=notes,
            diagnosis=diagnosis,
            treatment=treatment,
        )
        self.records.add(record)
        self.records.commit()
        return record

    def update_record(
        self,
        patient_id,
        record_id,
        *,
        title=None,
        visit_date=None,
        doctor_id=None,
        department_id=None,
        notes=None,
        diagnosis=None,
        treatment=None,
    ):
        record = self.get_record(patient_id, record_id)
        if title is not None:
            record.title = title
        if visit_date is not None:
            record.visit_date = self._parse_datetime(visit_date)
        if doctor_id is not None:
            if doctor_id:
                doctor = self.doctors.find_by_id(doctor_id)
                if doctor is None:
                    raise NotFoundException("errors.doctor_not_found")
            record.doctor_id = doctor_id
        if department_id is not None:
            if department_id:
                department = self.departments.find_by_id(department_id)
                if department is None:
                    raise NotFoundException("errors.department_not_found")
            record.department_id = department_id
        if notes is not None:
            record.notes = notes
        if diagnosis is not None:
            record.diagnosis = diagnosis
        if treatment is not None:
            record.treatment = treatment
        self.records.commit()
        return record

    def _ensure_patient_exists(self, patient_id):
        if self.patients.find_by_id(patient_id) is None:
            raise NotFoundException("errors.patient_not_found")

    def _parse_datetime(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise BadRequestException("errors.invalid_datetime_format")
        raise BadRequestException("errors.invalid_datetime_format")
