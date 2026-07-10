"""Repository layer for Appointment model — encapsulates database queries."""
from ..extensions import db
from ..models.appointment import Appointment, AppointmentStatusHistory


class AppointmentRepository:
    """Handles data access for Appointment records."""

    def find_by_id(self, appointment_id):
        """Find appointment by ID.

        Args:
            appointment_id (int): Appointment ID.

        Returns:
            Appointment | None.
        """
        return db.session.get(Appointment, appointment_id)

    def paginate(
        self,
        page,
        size,
        *,
        date_from=None,
        date_to=None,
        status=None,
        doctor_id=None,
        department_id=None,
        patient_id=None,
    ):
        """Fetch paginated + filtered list of appointments, mới nhất trước.

        Args:
            page (int): Page number (1-indexed).
            size (int): Items per page.
            date_from (date, optional): appointment_date >= date_from.
            date_to (date, optional): appointment_date <= date_to.
            status (str, optional): lọc theo trạng thái chính xác.
            doctor_id (int, optional).
            department_id (int, optional).
            patient_id (int, optional).

        Returns:
            tuple: (list of Appointment objects, total count).
        """
        query = Appointment.query
        if date_from is not None:
            query = query.filter(Appointment.appointment_date >= date_from)
        if date_to is not None:
            query = query.filter(Appointment.appointment_date <= date_to)
        if status is not None:
            query = query.filter(Appointment.status == status)
        if doctor_id is not None:
            query = query.filter(Appointment.doctor_id == doctor_id)
        if department_id is not None:
            query = query.filter(Appointment.department_id == department_id)
        if patient_id is not None:
            query = query.filter(Appointment.patient_id == patient_id)

        query = query.order_by(
            Appointment.appointment_date.desc(), Appointment.start_time.desc()
        )
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add_status_history(self, appointment_id, *, old_status, new_status, changed_by=None, note=None):
        """Ghi 1 bản ghi lịch sử đổi trạng thái."""
        entry = AppointmentStatusHistory(
            appointment_id=appointment_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )
        db.session.add(entry)
        return entry

    def list_status_history(self, appointment_id):
        """Lấy lịch sử đổi trạng thái của 1 lịch hẹn, mới nhất trước."""
        return (
            AppointmentStatusHistory.query.filter_by(appointment_id=appointment_id)
            .order_by(AppointmentStatusHistory.created_at.desc())
            .all()
        )

    def commit(self):
        """Commit all changes in current session to database."""
        db.session.commit()
