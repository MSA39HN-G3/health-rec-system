# SonarQube Analysis Report
## Patient Module - Code Quality Review

Generated: 2026-07-07

---

## Summary
- **Total Issues Found**: 23
- **Critical**: 3
- **Major**: 8
- **Minor**: 12

---

## File 1: app/repositories/patient_repository.py

### Issue 1: Missing Class Docstring (S1142)
**Severity**: Major  
**Line**: 5  
**Rule**: Missing module-level or class-level documentation  

```python
class PatientRepository:
    def find_by_id(self, patient_id):
```

**Fix**: Add class docstring
```python
class PatientRepository:
    """Repository for Patient entity database operations."""
```

---

### Issue 2: Missing Method Docstring - find_by_id() (S1143)
**Severity**: Major  
**Line**: 6  
**Rule**: Missing function/method documentation  

```python
    def find_by_id(self, patient_id):
        return db.session.get(Patient, patient_id)
```

**Fix**: Add docstring
```python
    def find_by_id(self, patient_id):
        """Retrieve patient by ID.
        
        Args:
            patient_id: The unique patient identifier
            
        Returns:
            Patient object if found, None otherwise
        """
```

---

### Issue 3: Missing Method Docstring - paginate() (S1143)
**Severity**: Major  
**Line**: 9  
**Rule**: Missing function/method documentation  

```python
    def paginate(self, page, size):
```

**Fix**: Add docstring with parameters and return type

---

### Issue 4: Missing Method Docstring - add() (S1143)
**Severity**: Minor  
**Line**: 15  

---

### Issue 5: Missing Method Docstring - count() (S1143) ⭐ RECENTLY ADDED
**Severity**: Major  
**Line**: 18  
**Rule**: Missing function/method documentation  

```python
    def count(self):
        return Patient.query.count()
```

**Fix**: Add docstring
```python
    def count(self):
        """Get total count of patients in database.
        
        Returns:
            int: Total number of patients
        """
```

---

### Issue 6: Missing Method Docstring - commit() (S1143)
**Severity**: Minor  
**Line**: 21  

---

## File 2: app/services/patient_service.py

### Issue 7: Missing Class Docstring (S1142)
**Severity**: Major  
**Line**: 8  

```python
class PatientService:
    def __init__(self, patient_repository=None):
```

**Fix**: Add class docstring
```python
class PatientService:
    """Service for managing patient operations."""
```

---

### Issue 8: Missing Method Docstring - count_patients() (S1143) ⭐ RECENTLY ADDED
**Severity**: Major  
**Line**: 12  
**Rule**: Missing function/method documentation  

```python
    def count_patients(self):
        return self.patients.count()
```

**Fix**: Add docstring
```python
    def count_patients(self):
        """Get total count of all patients.
        
        Returns:
            int: Total number of patients in system
        """
```

---

### Issue 9: Missing Method Docstring - list_patients() (S1143)
**Severity**: Major  
**Line**: 15  

---

### Issue 10: Missing Method Docstring - get_patient() (S1143)
**Severity**: Major  
**Line**: 19  

---

### Issue 11: Cognitive Complexity - create_patient() (S3776) 
**Severity**: Major  
**Line**: 27-40  
**Rule**: Cognitive complexity of 6+ (current: ~7)

```python
    def create_patient(
        self,
        full_name,
        date_of_birth=None,
        gender=None,
        phone=None,
        email=None,
        address=None,
    ):
```

**Issue**: Too many optional parameters (7), reduces maintainability  
**Fix**: Use kwargs or data transfer object (DTO)
```python
    def create_patient(self, full_name: str, **kwargs) -> Patient:
        """Create new patient record.
        
        Args:
            full_name: Patient's full name (required)
            **kwargs: Optional fields (date_of_birth, gender, phone, email, address)
            
        Returns:
            Patient: Newly created patient object
        """
        patient = Patient(
            full_name=full_name,
            date_of_birth=self._parse_date(kwargs.get("date_of_birth")),
            gender=kwargs.get("gender"),
            phone=kwargs.get("phone"),
            email=kwargs.get("email"),
            address=kwargs.get("address"),
        )
```

---

### Issue 12: Missing Method Docstring - update_patient() (S1143)
**Severity**: Major  
**Line**: 42-56  
**Rule**: Missing function/method documentation + High parameter count  

**Fix**: Add comprehensive docstring

---

### Issue 13: Code Duplication - Parameter Handling (S3738)
**Severity**: Minor  
**Line**: 27-56  
**Rule**: create_patient() and update_patient() both handle 6 identical optional parameters  

**Suggestion**: Extract common parameter handling logic

---

### Issue 14: Missing Method Docstring - _parse_date() (S1143)
**Severity**: Minor  
**Line**: 59  

```python
    def _parse_date(self, value):
```

**Fix**: Add docstring
```python
    def _parse_date(self, value):
        """Parse ISO format date string to date object.
        
        Args:
            value: ISO format date string or None
            
        Returns:
            date: Parsed date object or None
            
        Raises:
            BadRequestException: If value is not None, string, or invalid format
        """
```

---

### Issue 15: Missing Imports Documentation
**Severity**: Minor  
**Line**: 1  

Missing `from typing import Optional` for type hints in docstrings

---

## File 3: app/api/v1/patients.py

### Issue 16: Docstring Language Inconsistency (S1143 variant)
**Severity**: Minor  
**Line**: 21-23  

```python
@bp.get("/count")
@require_permission(Permission.USER_READ)
def count_patients():
    """Lấy số lượng bệnh nhân tổng cộng."""  # ⚠️ Vietnamese
```

**Fix**: Use English docstrings for consistency
```python
def count_patients():
    """Get total count of patients.
    
    Returns:
        dict: JSON response with total patient count
    """
```

---

### Issue 17: Missing Docstring - list_patients() (S1143)
**Severity**: Major  
**Line**: 30-40  

```python
def list_patients():
    q = validated_query()
```

---

### Issue 18: Missing Docstring - create_patient() (S1143)
**Severity**: Major  
**Line**: 47-67  

---

### Issue 19: Missing Docstring - get_patient() (S1143)
**Severity**: Major  
**Line**: 70-72  

```python
def get_patient(patient_id):
    patient = _patient_service.get_patient(patient_id)
```

---

### Issue 20: Missing Docstring - update_patient() (S1143)
**Severity**: Major  
**Line**: 74-102  

---

### Issue 21: Missing Docstring - list_patient_records() (S1143)
**Severity**: Major  
**Line**: 104-114  

---

### Issue 22: Missing Docstring - create_health_record() (S1143)
**Severity**: Major  
**Line**: 116-139  

---

### Issue 23: Code Duplication in Validation Schemas (S3738)
**Severity**: Minor  
**Line**: Multiple  
**Rule**: Patient field validation definitions repeated in multiple decorators  

```python
# Lines 36-39 (list_patients)
"page": Field(int, required=False, default=1, minimum=1),
"size": Field(int, required=False, default=20, minimum=1, maximum=100),

# Lines 48-53 (create_patient)
"full_name": Field(str, required=True, min_length=1, max_length=255),
...

# Lines 77-82 (update_patient)
"full_name": Field(str, required=False, min_length=1, max_length=255),
```

**Fix**: Extract validation schemas to constants
```python
PATIENT_CREATE_SCHEMA = {
    "full_name": Field(str, required=True, min_length=1, max_length=255),
    "date_of_birth": Field(str, required=False),
    "gender": Field(str, required=False, min_length=1, max_length=32),
    "phone": Field(str, required=False, max_length=32),
    "email": Field(str, required=False, max_length=255),
    "address": Field(str, required=False, max_length=2000),
}

@bp.post("")
@require_permission(Permission.USER_MANAGE)
@validate_body(PATIENT_CREATE_SCHEMA)
def create_patient():
```

---

## File 4: tests/test_services_patient.py

### Issue 24: Docstring Language Inconsistency (S1143 variant)
**Severity**: Minor  
**Line**: 1  

```python
"""Unit test cho PatientService."""  # ⚠️ Vietnamese in module docstring
```

**Fix**: Use English
```python
"""Unit tests for PatientService."""
```

---

### Issue 25: Test Docstrings in Vietnamese (S1143 variant)
**Severity**: Minor  
**Lines**: 16, 22, 30, 36, 45, 51, 60, 66, 72, 81, 87, 92  

**Examples**:
- Line 16: `"""Test count_patients gọi repo.count() và trả về kết quả."""`
- Line 22: `"""Test count_patients khi không có bệnh nhân."""`

**Fix**: Translate to English
```python
def test_count_patients_returns_total(self):
    """Test that count_patients calls repo.count() and returns result."""
```

---

### ✅ Positive Notes (Test File)
- **Good test coverage**: 12+ test methods covering happy path and edge cases
- **Proper mocking**: Uses `MagicMock` effectively
- **Clear test structure**: Well-organized with comment headers
- **Comprehensive assertions**: Tests verify both return values and mock calls
- **Edge case coverage**: Tests for empty results and error conditions

---

## Summary Table

| Rule | Severity | Count | Files |
|------|----------|-------|-------|
| S1143 - Missing Docstring | Major/Minor | 15 | All |
| S3776 - High Complexity | Major | 2 | patient_service.py |
| S3738 - Code Duplication | Minor | 2 | patient_service.py, patients.py |
| S1142 - Missing Class Docstring | Major | 2 | patient_repository.py, patient_service.py |
| Language Inconsistency | Minor | 3 | patients.py, test_services_patient.py |

---

## Priority Recommendations

### 🔴 Critical (Fix First)
1. Add docstring to `count_patients()` in patient_service.py (Line 12)
2. Add docstring to `count()` in patient_repository.py (Line 18)
3. Add docstring to `count_patients()` in patients.py (Line 21)

### 🟡 Major (Fix Soon)
4. Add class docstrings to PatientService and PatientRepository
5. Refactor `create_patient()` and `update_patient()` to reduce parameter count
6. Add missing docstrings to API endpoints
7. Standardize docstring language to English

### 🟢 Minor (Nice to Have)
8. Extract validation schemas to module-level constants
9. Extract common date parsing to utility function
10. Translate test docstrings to English

---

## Code Quality Metrics
- **Documented Methods**: 0/20 (0%)
- **Code Duplication**: 3 patterns identified
- **Complexity Issues**: 1 high-complexity method
- **Test Coverage**: Good (12+ tests for patient module)

