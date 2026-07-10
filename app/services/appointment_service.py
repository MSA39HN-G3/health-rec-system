"""Service layer for Appointment — quản lý (xem/đổi trạng thái/hủy) lịch hẹn đã đặt."""
from datetime import datetime

from ..errors import BadRequestException, NotFoundException
from ..repositories.appointment_repository import AppointmentRepository

# Trạng thái hợp lệ của 1 lịch hẹn (khớp app/models/appointment.py).
VALID_STATUSES = ("pending", "confirmed", "checked_in", "completed", "cancelled", "no_show")

# Trạng thái kết thúc — không cho đổi tiếp sau khi đã ở trạng thái này.
TERMINAL_STATUSES = ("completed", "cancelled")


class AppointmentService:
    """Business logic cho quản trị lịch hẹn (dành cho staff/admin)."""

    def __init__(self, appointment_repository=None):
        self.appointments = appointment_repository or AppointmentRepository()

    def list_appointments(
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
        """Danh sách lịch hẹn có phân trang + lọc.

        Args:
            page (int), size (int): phân trang.
            date_from/date_to (str, optional): ISO date string ("YYYY-MM-DD").
            status (str, optional): 1 trong VALID_STATUSES.
            doctor_id/department_id/patient_id (int, optional).

        Returns:
            tuple: (list Appointment, total count).

        Raises:
            BadRequestException: ngày hoặc trạng thái không hợp lệ.
        """
        if status is not None and status not in VALID_STATUSES:
            raise BadRequestException("errors.invalid_appointment_status")

        return self.appointments.paginate(
            page,
            size,
            date_from=self._parse_date(date_from),
            date_to=self._parse_date(date_to),
            status=status,
            doctor_id=doctor_id,
            department_id=department_id,
            patient_id=patient_id,
        )

    def get_appointment(self, appointment_id):
        """Lấy 1 lịch hẹn theo ID.

        Raises:
            NotFoundException: không tìm thấy.
        """
        appointment = self.appointments.find_by_id(appointment_id)
        if appointment is None:
            raise NotFoundException("errors.appointment_not_found")
        return appointment

    def get_status_history(self, appointment_id):
        """Lấy lịch sử đổi trạng thái của 1 lịch hẹn."""
        self.get_appointment(appointment_id)  # đảm bảo tồn tại -> 404 nếu không
        return self.appointments.list_status_history(appointment_id)

    def update_status(self, appointment_id, new_status, *, changed_by=None, note=None):
        """Đổi trạng thái lịch hẹn + ghi lịch sử.

        Raises:
            NotFoundException: không tìm thấy lịch hẹn.
            BadRequestException: trạng thái không hợp lệ, hoặc lịch hẹn đã ở
                trạng thái kết thúc (completed/cancelled) nên không đổi tiếp được.
        """
        if new_status not in VALID_STATUSES:
            raise BadRequestException("errors.invalid_appointment_status")

        appointment = self.get_appointment(appointment_id)
        if appointment.status in TERMINAL_STATUSES:
            raise BadRequestException("errors.appointment_already_finalized")

        old_status = appointment.status
        appointment.status = new_status
        self.appointments.add_status_history(
            appointment.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )
        self.appointments.commit()
        return appointment

    def cancel_appointment(self, appointment_id, *, reason=None, changed_by=None):
        """Hủy lịch hẹn (đặt status=cancelled + lưu cancel_reason).

        Raises:
            NotFoundException: không tìm thấy lịch hẹn.
            BadRequestException: lịch hẹn đã ở trạng thái kết thúc.
        """
        appointment = self.get_appointment(appointment_id)
        if appointment.status in TERMINAL_STATUSES:
            raise BadRequestException("errors.appointment_already_finalized")

        old_status = appointment.status
        appointment.status = "cancelled"
        appointment.cancel_reason = reason
        self.appointments.add_status_history(
            appointment.id,
            old_status=old_status,
            new_status="cancelled",
            changed_by=changed_by,
            note=reason,
        )
        self.appointments.commit()
        return appointment

    def _parse_date(self, value):
        """Parse ISO format date string ("YYYY-MM-DD") -> date object.

        Args:
            value (str | None).

        Returns:
            date | None.

        Raises:
            BadRequestException: định dạng ngày không hợp lệ.
        """
        if value is None:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise BadRequestException("errors.invalid_date_format")
