"""Service quản lý thống kê bác sĩ."""
from ..common.roles import Role
from ..errors import ForbiddenException, NotFoundException
from ..repositories.doctor_repository import DoctorRepository
from ..repositories.doctor_statistics_repository import DoctorStatisticsRepository


class DoctorStatisticsService:
    def __init__(
        self,
        statistics_repository=None,
        doctor_repository=None,
    ):
        self.statistics = statistics_repository or DoctorStatisticsRepository()
        self.doctors = doctor_repository or DoctorRepository()

    def _check_permission(self, actor):
        """Kiểm tra quyền xem thống kê."""
        if not actor or not actor.has_role(Role.ADMIN, Role.DEPARTMENT_HEAD):
            raise ForbiddenException("errors.forbidden")

    def _check_admin_only(self, actor):
        """Chỉ admin được thực hiện."""
        if not actor or not actor.has_role(Role.ADMIN):
            raise ForbiddenException("errors.forbidden")

    def get_doctor_statistics(self, actor, doctor_id):
        """Lấy thống kê của một bác sĩ."""
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        self._check_permission(actor)

        # Department head chỉ xem được thống kê của khoa mình
        if actor.has_role(Role.DEPARTMENT_HEAD):
            from ..repositories.department_repository import DepartmentRepository
            dept_repo = DepartmentRepository()
            my_dept = dept_repo.find_by_head_doctor_id(actor.id)
            if my_dept and doctor.department_id != my_dept.id:
                raise ForbiddenException("errors.forbidden")

        return self.statistics.find_or_create(doctor_id)

    def recalculate_statistics(self, actor, doctor_id):
        """Tính lại thống kê cho bác sĩ (chỉ admin)."""
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        self._check_admin_only(actor)
        return self.statistics.recalculate_for_doctor(doctor_id)

    def get_top_rated_doctors(self, actor, limit=10):
        """Lấy danh sách bác sĩ có điểm đánh giá cao nhất."""
        self._check_permission(actor)
        return self.statistics.get_top_rated(limit)

    def get_most_active_doctors(self, actor, limit=10):
        """Lấy danh sách bác sĩ có nhiều lịch hẹn nhất."""
        self._check_permission(actor)
        return self.statistics.get_most_appointments(limit)

    def get_all_statistics(self, actor, page=1, size=20):
        """Lấy thống kê của tất cả bác sĩ (phân trang)."""
        self._check_admin_only(actor)
        # Get all statistics with pagination
        from ..extensions import db
        from ..models.doctor_statistics import DoctorStatistics

        query = DoctorStatistics.query.order_by(DoctorStatistics.average_rating.desc().nullslast())
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
