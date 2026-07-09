import uuid
import os
import requests
import random
from datetime import datetime, date, time, timedelta

from ..extensions import db
from ..errors import BadRequestException, NotFoundException, ConflictException
from ..models.booking_session import BookingSession, BookingSessionSymptom
from ..models.patient import Patient
from ..models.ai_recommendation import AIRecommendation
from ..models.department import Department
from ..models.room import Room
from ..models.doctor import Doctor
from ..models.doctor_schedule import DoctorSchedule
from ..models.appointment import Appointment, AppointmentStatusHistory
from ..repositories.booking_session_repository import BookingSessionRepository
from ..repositories.symptom_repository import SymptomRepository
from .symptom_service import SymptomService


class BookingSessionService:
    """Handles business logic for booking sessions."""

    def __init__(self, booking_session_repository=None, symptom_repository=None):
        self.sessions = booking_session_repository or BookingSessionRepository()
        self.symptoms = symptom_repository or SymptomRepository()

    def create_session(self, symptom_ids, free_text_symptom=None, created_by_user_id=None):
        """Create a new booking session (Step 1: Choose Symptoms).

        Args:
            symptom_ids (list of int): List of symptom IDs selected.
            free_text_symptom (str, optional): Additional text description.
            created_by_user_id (int, optional): The user ID creating this session.

        Returns:
            BookingSession: Created booking session.

        Raises:
            BadRequestException: If both symptom_ids and free_text_symptom are empty.
            NotFoundException: If any of the symptom_ids does not exist.
        """
        # Validate that we have at least some symptoms or description
        if not symptom_ids and not free_text_symptom:
            raise BadRequestException("errors.empty_symptoms")

        # Verify all symptom_ids exist in the database
        if symptom_ids:
            for symptom_id in symptom_ids:
                symptom = self.symptoms.find_by_id(symptom_id)
                if not symptom:
                    raise NotFoundException("errors.symptom_not_found")

        # Generate a unique session ID (UUID)
        session_id = str(uuid.uuid4())

        session = BookingSession(
            id=session_id,
            patient_id=None,
            created_by_user_id=created_by_user_id,
            status="CREATED",
            current_step=1,
            free_text_symptom=free_text_symptom,
        )

        try:
            self.sessions.add(session)

            # Insert selected symptoms
            if symptom_ids:
                for symptom_id in symptom_ids:
                    session_symptom = BookingSessionSymptom(
                        session_id=session_id,
                        symptom_id=symptom_id,
                    )
                    self.sessions.add_session_symptom(session_symptom)

            self.sessions.commit()
            return session
        except Exception:
            self.sessions.rollback()
            raise

    def update_patient_info(self, session_id, patient_data):
        """Step 2: Update patient info in session (finds existing patient by phone or creates a new one)."""
        session = self.sessions.find_by_id(session_id)
        if not session:
            raise NotFoundException("errors.booking_session_not_found")

        phone = patient_data.get("phone")
        full_name = patient_data.get("full_name")
        date_of_birth_str = patient_data.get("date_of_birth")
        gender = patient_data.get("gender")
        email = patient_data.get("email")
        address = patient_data.get("address")

        if not phone or not full_name:
            raise BadRequestException("errors.missing_patient_required_fields")

        dob = None
        if date_of_birth_str:
            try:
                # Support full ISO string (e.g. 2000-01-15T00:00:00.000Z) or YYYY-MM-DD
                if "T" in date_of_birth_str:
                    dob = datetime.fromisoformat(date_of_birth_str.replace("Z", "+00:00")).date()
                else:
                    dob = datetime.strptime(date_of_birth_str, "%Y-%m-%d").date()
            except ValueError:
                raise BadRequestException("errors.invalid_date_format")

        patient = Patient.query.filter_by(phone=phone).first()
        if patient:
            if full_name:
                patient.full_name = full_name
            if dob:
                patient.date_of_birth = dob
            if gender:
                patient.gender = gender
            if email:
                patient.email = email
            if address:
                patient.address = address
        else:
            patient = Patient(
                full_name=full_name,
                date_of_birth=dob,
                gender=gender,
                phone=phone,
                email=email,
                address=address
            )
            db.session.add(patient)

        db.session.flush()

        session.patient_id = patient.id
        session.status = "PATIENT_INFO_COMPLETED"
        session.current_step = 2

        db.session.commit()
        return session

    def get_ai_recommendations(self, session_id):
        """Step 3: Call AI to get top 3 specialties based on symptoms."""
        session = self.sessions.find_by_id(session_id)
        if not session:
            raise NotFoundException("errors.booking_session_not_found")

        # Check if recommendations already exist for this session to optimize and handle concurrent requests
        existing_recs = AIRecommendation.query.filter_by(session_id=session.id).order_by(AIRecommendation.rank).all()
        if existing_recs:
            if session.status not in ["AI_RECOMMENDED", "DEPARTMENT_SELECTED", "DOCTOR_SELECTED", "BOOKED"]:
                session.status = "AI_RECOMMENDED"
                session.current_step = 3
                db.session.commit()
            return existing_recs

        symptom_names = [s.name for s in session.symptoms]
        free_text = session.free_text_symptom
        trieu_chung = ", ".join(symptom_names)
        if free_text:
            if trieu_chung:
                trieu_chung += f" ({free_text})"
            else:
                trieu_chung = free_text

        recommendations = []
        ai_success = False

        try:
            url = os.getenv("AI_API_URL", "http://localhost:8000/ppr501.22/recommend")
            api_key = os.getenv("AI_API_KEY", "dev-key")
            response = requests.post(
                url,
                json={"trieu_chung": trieu_chung},
                headers={"x-api-key": api_key},
                timeout=3.0
            )
            if response.status_code == 200:
                res_data = response.json()
                ai_recs = res_data if isinstance(res_data, list) else res_data.get("recommendations", [])

                depts = Department.query.all()
                def map_dept_name(name):
                    clean_name = name.lower().replace("khoa", "").replace("phòng", "").strip()
                    for dept in depts:
                        dept_clean = dept.name.lower().replace("khoa", "").replace("phòng", "").strip()
                        if clean_name in dept_clean or dept_clean in clean_name:
                            return dept
                    return None

                seen_dept_ids = set()
                rank = 1
                for item in ai_recs:
                    if len(recommendations) >= 3:
                        break
                    name = item.get("Chuyen_Khoa") or item.get("specialty_name") or item.get("name")
                    if not name:
                        continue
                    dept = map_dept_name(name)
                    if dept and dept.id not in seen_dept_ids:
                        seen_dept_ids.add(dept.id)
                        score = item.get("Do_Chinh_Xac") or item.get("confidence_score") or item.get("score") or 0.5
                        reasoning = item.get("reasoning") or f"Gợi ý bởi mô hình AI cho chuyên khoa {dept.name}."
                        rec = AIRecommendation(
                            session_id=session.id,
                            department_id=dept.id,
                            rank=rank,
                            confidence_score=score,
                            reasoning=reasoning,
                            model_name="ppr501.22-recommend"
                        )
                        recommendations.append(rec)
                        rank += 1

                if recommendations:
                    ai_success = True
        except Exception as e:
            # Fallback will trigger below
            pass

        if not ai_success:
            symptom_service = SymptomService()
            rule_recs = symptom_service.get_recommendations(symptom_names)

            seen_dept_ids = set()
            rank = 1
            recommendations = []
            for item in rule_recs:
                if len(recommendations) >= 3:
                    break
                dept_id = item["specialty"]["id"]
                if dept_id in seen_dept_ids:
                    continue
                seen_dept_ids.add(dept_id)
                score = item["score"]
                explanation = item["explanation"]

                rec = AIRecommendation(
                    session_id=session.id,
                    department_id=dept_id,
                    rank=rank,
                    confidence_score=score,
                    reasoning=explanation,
                    model_name="rule-based-fallback"
                )
                recommendations.append(rec)
                rank += 1

        try:
            # Delete old recommendations
            AIRecommendation.query.filter_by(session_id=session.id).delete()
            
            # Add new recommendations
            for rec in recommendations:
                db.session.add(rec)

            session.status = "AI_RECOMMENDED"
            session.current_step = 3
            db.session.commit()
            return recommendations
        except Exception as db_err:
            db.session.rollback()
            # If there's a unique violation/integrity error, check if a concurrent request succeeded
            existing_recs = AIRecommendation.query.filter_by(session_id=session.id).order_by(AIRecommendation.rank).all()
            if existing_recs:
                return existing_recs
            raise db_err

    def select_department(self, session_id, department_id):
        """Step 3: User selects one department from top 3 recommendations."""
        session = self.sessions.find_by_id(session_id)
        if not session:
            raise NotFoundException("errors.booking_session_not_found")

        recs = AIRecommendation.query.filter_by(session_id=session.id).all()
        found = False
        for rec in recs:
            if rec.department_id == department_id:
                rec.is_selected = True
                found = True
            else:
                rec.is_selected = False

        if not found:
            dept = Department.query.get(department_id)
            if not dept:
                raise NotFoundException("errors.department_not_found")
            rec = AIRecommendation(
                session_id=session.id,
                department_id=department_id,
                rank=4,
                confidence_score=1.0,
                reasoning="Lựa chọn của người dùng",
                model_name="user-selected",
                is_selected=True
            )
            db.session.add(rec)

        session.status = "DEPARTMENT_SELECTED"
        session.current_step = 3
        db.session.commit()
        return session

    def get_available_slots(self, session_id, date_str):
        """Step 3: Get open rooms, scheduled doctors and free time slots for selected department."""
        session = self.sessions.find_by_id(session_id)
        if not session:
            raise NotFoundException("errors.booking_session_not_found")

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise BadRequestException("errors.invalid_date_format")

        selected_rec = AIRecommendation.query.filter_by(session_id=session.id, is_selected=True).first()
        if not selected_rec:
            selected_rec = AIRecommendation.query.filter_by(session_id=session.id, rank=1).first()
            if not selected_rec:
                raise BadRequestException("errors.no_department_selected")

        dept_id = selected_rec.department_id

        rooms = Room.query.filter_by(department_id=dept_id, status='OPEN').all()
        room_ids = [r.id for r in rooms]
        if not room_ids:
            return []

        py_dow = date_obj.weekday()
        db_dow = (py_dow + 1) % 7

        schedules = DoctorSchedule.query.filter(
            DoctorSchedule.room_id.in_(room_ids),
            DoctorSchedule.day_of_week == db_dow,
            DoctorSchedule.is_active == True
        ).all()

        valid_schedules = []
        for ds in schedules:
            if ds.effective_from and date_obj < ds.effective_from:
                continue
            if ds.effective_to and date_obj > ds.effective_to:
                continue
            valid_schedules.append(ds)

        results = []
        from sqlalchemy import text
        query = """
            SELECT 
                gs.slot_start::time AS start_time,
                (gs.slot_start + make_interval(mins => ds.slot_duration_minutes))::time AS end_time,
                (COALESCE(a.booked_count, 0) < ds.max_patients_per_slot) AS available
            FROM doctor_schedules ds
            CROSS JOIN LATERAL generate_series(
                :date_val + ds.start_time,
                :date_val + ds.end_time - make_interval(mins => ds.slot_duration_minutes),
                make_interval(mins => ds.slot_duration_minutes)
            ) AS gs(slot_start)
            LEFT JOIN (
                SELECT doctor_id, appointment_date, start_time, COUNT(id) AS booked_count
                FROM appointments
                WHERE appointment_date = :date_val
                  AND status NOT IN ('cancelled', 'no_show')
                GROUP BY doctor_id, appointment_date, start_time
            ) a ON a.doctor_id = ds.doctor_id AND a.start_time = gs.slot_start::time
            WHERE ds.id = :schedule_id
            ORDER BY start_time;
        """

        for ds in valid_schedules:
            slots_rows = db.session.execute(
                text(query),
                {"date_val": date_obj, "schedule_id": ds.id}
            ).fetchall()

            slots = []
            for row in slots_rows:
                slots.append({
                    "start_time": row.start_time.strftime("%H:%M"),
                    "end_time": row.end_time.strftime("%H:%M"),
                    "available": bool(row.available)
                })

            results.append({
                "room": {"id": ds.room.id, "name": ds.room.name, "code": ds.room.code},
                "doctor": {"id": ds.doctor.id, "full_name": ds.doctor.full_name, "title": ds.doctor.title},
                "schedule_id": ds.id,
                "slots": slots
            })

        return results

    def confirm_appointment(self, session_id, appointment_data):
        """Step 3: Confirm selection, block the slot and complete booking session in 1 transaction."""
        session = self.sessions.find_by_id(session_id)
        if not session:
            raise NotFoundException("errors.booking_session_not_found")

        if not session.patient_id:
            raise BadRequestException("errors.patient_info_missing")

        doctor_id = appointment_data.get("doctor_id")
        room_id = appointment_data.get("room_id")
        schedule_id = appointment_data.get("schedule_id")
        date_str = appointment_data.get("appointment_date")
        start_time_str = appointment_data.get("start_time")
        end_time_str = appointment_data.get("end_time")

        if not all([doctor_id, room_id, schedule_id, date_str, start_time_str, end_time_str]):
            raise BadRequestException("errors.missing_appointment_required_fields")

        selected_rec = AIRecommendation.query.filter_by(session_id=session.id, is_selected=True).first()
        if not selected_rec:
            selected_rec = AIRecommendation.query.filter_by(session_id=session.id, rank=1).first()
            if not selected_rec:
                raise BadRequestException("errors.no_department_selected")
        dept_id = selected_rec.department_id

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # support both HH:MM and HH:MM:SS format
            def parse_time(t_str):
                parts = t_str.split(":")
                return time(int(parts[0]), int(parts[1]))

            start_time_obj = parse_time(start_time_str)
            end_time_obj = parse_time(end_time_str)
        except (ValueError, IndexError):
            raise BadRequestException("errors.invalid_date_or_time_format")

        ds = DoctorSchedule.query.get(schedule_id)
        if not ds:
            raise NotFoundException("errors.schedule_not_found")

        booked_count = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=date_obj,
            start_time=start_time_obj
        ).filter(Appointment.status.notin_(['cancelled', 'no_show'])).count()

        if booked_count >= ds.max_patients_per_slot:
            raise ConflictException("errors.slot_already_booked")

        session.status = "DOCTOR_SELECTED"
        db.session.flush()

        code = f"APT-{date_obj.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        apt = Appointment(
            code=code,
            session_id=session.id,
            patient_id=session.patient_id,
            department_id=dept_id,
            doctor_id=doctor_id,
            room_id=room_id,
            schedule_id=schedule_id,
            appointment_date=date_obj,
            start_time=start_time_obj,
            end_time=end_time_obj,
            status="pending",
            symptom_note=session.free_text_symptom
        )
        db.session.add(apt)
        db.session.flush()

        history = AppointmentStatusHistory(
            appointment_id=apt.id,
            old_status=None,
            new_status="pending",
            note="Đặt lịch tự động qua Kiosk"
        )
        db.session.add(history)

        session.status = "BOOKED"
        session.current_step = 3

        db.session.commit()
        return apt

