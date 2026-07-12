import pathlib

files = [
    'app/services/doctor_document_service.py',
    'app/services/doctor_statistics_service.py',
    'app/services/doctor_service.py',
    'app/services/department_service.py',
    'app/common/scope.py',
    'app/common/roles.py',
    'app/middleware/auth.py',
    'app/models/department.py',
    'app/models/doctor.py',
    'app/repositories/department_repository.py',
    'app/api/v1/departments.py',
]
for rel in files:
    p = pathlib.Path(rel)
    data = p.read_bytes()
    if data[:2] == b'\xff\xfe':
        # UTF-16 LE BOM
        text = data.decode('utf-16-le').lstrip('\ufeff')
        p.write_bytes(b'\xef\xbb\xbf' + text.encode('utf-8'))
        print(rel, ': UTF-16 LE -> UTF-8 BOM')
    elif data[:3] == b'\xef\xbb\xbf':
        # UTF-8 with BOM
        text = data[3:].decode('utf-8')
        p.write_bytes(b'\xef\xbb\xbf' + text.encode('utf-8'))
        print(rel, ': UTF-8 BOM (clean re-write)')
    else:
        print(rel, ': plain UTF-8')