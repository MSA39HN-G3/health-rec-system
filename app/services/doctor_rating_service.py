"""Service quản lý đánh giá bác sĩ từ bệnh nhân."""
from ..common.roles import Role
from ..errors import ForbiddenException, NotFoundException, ValidationException, ConflictException
from ..models.doctor_rating import DoctorRating
from ..repositories.doctor_rating_repository import DoctorRatingRepository
from ..repositories.doctor_repository import DoctorRepository
from ..repositories.patient_repository import PatientRepository


class DoctorRatingService:
    def __init__(
        self,
        rating_repository=None,
        doctor_repository=None,
        patient_repository=None,
        statistics_repository=None,
    ):
        from ..repositories.doctor_statistics_repository import DoctorStatisticsRepository

        self.ratings = rating_repository or DoctorRatingRepository()
        self.doctors = doctor_repository or DoctorRepository()
        self.patients = patient_repository or PatientRepository()
        self.statistics = statistics_repository or DoctorStatisticsRepository()

    def _check_patient_permission(self, actor, patient_id):
        """Kiểm tra quyền của bệnh nhân (hoặc admin đặt hộ)."""
        if not actor:
            raise ForbiddenException("errors.unauthorized")

        # Admin có thể đặt cho bất kỳ ai
        if actor.has_role(Role.ADMIN):
            return True

        # Kiểm tra patient_id trùng với user hiện tại (thông qua patient)
        # Hoặc user có vai trò phù hợp
        if actor.has_role(Role.PATIENT):
            patient = self.patients.find_by_id(patient_id)
            if patient and patient.user_id == actor.id:
                return True

        # Staff có thể tạo đánh giá hộ bệnh nhân
        if actor.has_role(Role.STAFF):
            return True

        raise ForbiddenException("errors.forbidden")

    def create_rating(self, actor, data):
        """Tạo đánh giá mới cho bác sĩ.

        Args:
            actor: User đang thực hiện
            data: Dict chứa {doctor_id, patient_id, appointment_id, rating, comment}

        Returns:
            DoctorRating: Đánh giá đã tạo
        """
        doctor_id = data.get("doctor_id")
        patient_id = data.get("patient_id")
        appointment_id = data.get("appointment_id")
        rating_value = data.get("rating")

        # Validate rating value (1-5)
        if not rating_value or not isinstance(rating_value, int) or rating_value < 1 or rating_value > 5:
            raise ValidationException({"rating": "invalid_range"})

        # Validate doctor exists
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        # Validate patient exists
        patient = self.patients.find_by_id(patient_id)
        if not patient:
            raise ValidationException({"patient_id": "not_found"})

        # Validate appointment if provided
        if appointment_id:
            # Check if appointment belongs to this doctor and patient
            # and is completed (only completed appointments can be rated)
            pass  # Simplified - can add appointment validation later

        # Check if already rated
        if appointment_id and self.ratings.has_rated_appointment(patient_id, appointment_id):
            raise ConflictException("errors.already_exists")

        # Create rating
        rating = DoctorRating(
            doctor_id=doctor_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            rating=rating_value,
            comment=data.get("comment"),
        )

        rating = self.ratings.add(rating)

        # Update doctor statistics
        self.statistics.recalculate_for_doctor(doctor_id)

        return rating

    def get_doctor_ratings(self, actor, doctor_id, page=None, size=None):
        """Lấy đánh giá của một bác sĩ."""
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        # Ai cũng có thể xem đánh giá (public)
        return self.ratings.find_by_doctor_id(doctor_id, page, size)

    def get_rating(self, actor, rating_id):
        """Lấy chi tiết một đánh giá."""
        rating = self.ratings.find_by_id(rating_id)
        if not rating:
            raise NotFoundException("errors.not_found")
        return rating

    def update_rating(self, actor, rating_id, data):
        """Cập nhật đánh giá (chỉ bệnh nhân sở hữu hoặc admin)."""
        rating = self.ratings.find_by_id(rating_id)
        if not rating:
            raise NotFoundException("errors.not_found")

        # Check permission: chỉ người tạo hoặc admin được sửa
        if not actor.has_role(Role.ADMIN):
            patient = self.patients.find_by_id(rating.patient_id)
            if not patient or patient.user_id != actor.id:
                raise ForbiddenException("errors.forbidden")

        # Update fields
        if "rating" in data:
            rating_value = data["rating"]
            if not isinstance(rating_value, int) or rating_value < 1 or rating_value > 5:
                raise ValidationException({"rating": "invalid_range"})
            rating.rating = rating_value

        if "comment" in data:
            rating.comment = data["comment"]

        rating = self.ratings.update(rating)

        # Recalculate doctor statistics
        self.statistics.recalculate_for_doctor(rating.doctor_id)

        return rating

    def delete_rating(self, actor, rating_id):
        """Xóa đánh giá (chỉ admin)."""
        if not actor or not actor.has_role(Role.ADMIN):
            raise ForbiddenException("errors.forbidden")

        rating = self.ratings.find_by_id(rating_id)
        if not rating:
            raise NotFoundException("errors.not_found")

        doctor_id = rating.doctor_id
        self.ratings.delete(rating)

        # Recalculate doctor statistics
        self.statistics.recalculate_for_doctor(doctor_id)

    def get_rating_distribution(self, actor, doctor_id):
        """Lấy phân bố đánh giá theo sao."""
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        return self.ratings.get_rating_distribution(doctor_id)

    def get_patient_ratings(self, actor, patient_id):
        """Lấy tất cả đánh giá của một bệnh nhân."""
        if not actor:
            raise ForbiddenException("errors.unauthorized")

        # Chỉ chính bệnh nhân hoặc admin được xem
        if not actor.has_role(Role.ADMIN):
            patient = self.patients.find_by_id(patient_id)
            if not patient or patient.user_id != actor.id:
                raise ForbiddenException("errors.forbidden")

        return self.ratings.find_by_patient_id(patient_id)
