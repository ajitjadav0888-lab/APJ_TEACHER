from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from pydantic import BaseModel
import os
from pathlib import Path

DATABASE_URL = os.getenv("APJ_DATABASE_URL", "sqlite:///./apj.db")
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    students = relationship("Student", back_populates="school")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)

class ClassRoom(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)
    standard = Column(String, nullable=False)
    division = Column(String, nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    school = relationship("School", back_populates="students")

Base.metadata.create_all(bind=engine)
from migrations import apply_migrations
apply_migrations(engine)

app = FastAPI(title="APJ V1.0 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv('APJ_CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

from auth import AuthCredential
Base.metadata.create_all(bind=engine)

from auth_api import router as auth_router
from auth import current_user, require_roles, require_school_access
app.include_router(auth_router)

class SchoolIn(BaseModel):
    name: str
    code: str

class UserIn(BaseModel):
    school_id: int
    name: str
    role: str

class StudentIn(BaseModel):
    school_id: int
    name: str
    standard: str
    division: str
    class_id: int | None = None

@app.get("/")
def root():
    return {"app": "APJ V1.0", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "database": "connected"}

@app.get("/download/apj-teacher-debug.apk", include_in_schema=False)
def download_debug_apk():
    apk_path = Path(__file__).resolve().parents[2] / "APJ-Teacher-debug.apk"
    if not apk_path.is_file():
        raise HTTPException(404, "DEBUG APK is not available")
    return FileResponse(
        apk_path,
        media_type="application/vnd.android.package-archive",
        filename="APJ-Teacher-debug.apk",
    )

@app.post("/schools")
def create_school(data: SchoolIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN'))):
    if session.query(School).filter_by(code=data.code).first():
        raise HTTPException(409, "School code already exists")
    school = School(name=data.name, code=data.code)
    session.add(school)
    session.commit()
    session.refresh(school)
    return {"id": school.id, "name": school.name, "code": school.code}

@app.get("/schools")
def list_schools(session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN'))):
    return [{"id": s.id, "name": s.name, "code": s.code}
            for s in session.query(School).order_by(School.id).all()]

@app.post("/users")
def create_user(data: UserIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    target_school = user.school_id if user.role != 'SUPER_ADMIN' else data.school_id
    if not session.get(School, target_school):
        raise HTTPException(404, "School not found")
    if data.role not in {"SUPER_ADMIN", "ADMIN", "TEACHER", "STUDENT", "PARENT", "STAFF"}:
        raise HTTPException(400, "Invalid role")
    # Only the platform-level SUPER_ADMIN may provision another SUPER_ADMIN.
    # A school ADMIN must never be able to self-escalate privileges.
    if user.role != 'SUPER_ADMIN' and data.role == 'SUPER_ADMIN':
        raise HTTPException(403, 'Only SUPER_ADMIN can create SUPER_ADMIN users')
    new_user_data = data.model_dump(); new_user_data['school_id'] = target_school
    new_user = User(**new_user_data)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {"id": new_user.id, "name": new_user.name, "role": new_user.role, "school_id": new_user.school_id}

@app.post("/students")
def create_student(data: StudentIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    target_school = user.school_id if user.role != 'SUPER_ADMIN' else data.school_id
    if not session.get(School, target_school):
        raise HTTPException(404, "School not found")
    student_data = data.model_dump(); student_data['school_id'] = target_school
    if student_data.get('class_id') is not None:
        cls = session.get(ClassRoom, student_data['class_id'])
        if not cls or cls.school_id != target_school:
            raise HTTPException(404, 'Class not found in school')
    student = Student(**student_data)
    session.add(student)
    session.commit()
    session.refresh(student)
    return {
        "id": student.id,
        "school_id": student.school_id,
        "name": student.name,
        "standard": student.standard,
        "division": student.division,
    }

@app.get("/students")
def list_students(school_id: int, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF'))):
    require_school_access(user, school_id)
    students = session.query(Student).filter_by(school_id=school_id).order_by(Student.id).all()
    return [
        {"id": s.id, "name": s.name, "standard": s.standard, "division": s.division}
        for s in students
    ]

# --- APJ Academic Core v1: attendance, homework, exams, marks, results ---
from datetime import date
from pydantic import BaseModel, Field
from sqlalchemy import Date, UniqueConstraint

class AcademicYear(Base):
    __tablename__ = 'academic_years'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default='ACTIVE')

class ParentChild(Base):
    __tablename__ = 'parent_child_links'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    __table_args__ = (UniqueConstraint('parent_id','student_id', name='uq_parent_student'),)

class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    attendance_date = Column(Date, nullable=False)
    status = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('student_id','attendance_date', name='uq_student_attendance_date'),)

class Homework(Base):
    __tablename__ = 'homework'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    title = Column(String, nullable=False)
    due_date = Column(Date, nullable=False)

class Exam(Base):
    __tablename__ = 'exams'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    name = Column(String, nullable=False)
    exam_date = Column(Date, nullable=False)

class Mark(Base):
    __tablename__ = 'marks'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    marks = Column(Integer, nullable=False)
    max_marks = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

class AcademicYearIn(BaseModel):
    school_id: int
    name: str
    status: str = 'ACTIVE'

class AttendanceIn(BaseModel):
    school_id: int
    student_id: int
    attendance_date: date
    status: str

class HomeworkIn(BaseModel):
    school_id: int
    class_id: int
    subject_id: int
    title: str
    due_date: date

class ExamIn(BaseModel):
    school_id: int
    name: str
    exam_date: date

class MarkIn(BaseModel):
    school_id: int
    exam_id: int
    student_id: int
    subject_id: int
    marks: int = Field(ge=0)
    max_marks: int = Field(gt=0)

@app.post('/api/v1/academic-years')
def create_academic_year(data: AcademicYearIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    require_school_access(user, data.school_id)
    if not session.get(School, data.school_id):
        raise HTTPException(404, 'School not found')
    item = AcademicYear(**data.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

def ensure_teacher_student_access(user, student, subject_id=None, session=None):
    if user.role != 'TEACHER':
        return
    if student.class_id is None:
        raise HTTPException(403, 'Teacher assignment cannot be verified for this student')
    q = session.query(TeacherAssignment).filter_by(school_id=user.school_id, teacher_id=user.id, class_id=student.class_id)
    if subject_id is not None:
        q = q.filter_by(subject_id=subject_id)
    if not q.first():
        raise HTTPException(403, 'Teacher is not assigned to this student/class/subject')

def ensure_parent_child_access(user, student, session):
    if user.role != 'PARENT':
        return
    link = session.query(ParentChild).filter_by(school_id=user.school_id, parent_id=user.id, student_id=student.id).first()
    if not link:
        raise HTTPException(403, 'Parent is not linked to this student')

@app.post('/api/v1/parent-links')
def create_parent_link(data: dict, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    parent_id = int(data.get('parent_id', 0)); student_id = int(data.get('student_id', 0)); school_id = int(data.get('school_id', 0))
    require_school_access(user, school_id)
    parent = session.get(User, parent_id); student = session.get(Student, student_id)
    if not parent or parent.role != 'PARENT' or parent.school_id != school_id: raise HTTPException(404, 'Parent not found in school')
    if not student or student.school_id != school_id: raise HTTPException(404, 'Student not found in school')
    if session.query(ParentChild).filter_by(parent_id=parent_id, student_id=student_id).first(): raise HTTPException(409, 'Link already exists')
    link=ParentChild(school_id=school_id,parent_id=parent_id,student_id=student_id); session.add(link); session.commit(); session.refresh(link)
    return {'id':link.id,'parent_id':parent_id,'student_id':student_id,'school_id':school_id}

@app.post('/api/v1/attendance')
def create_attendance(data: AttendanceIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','TEACHER'))):
    require_school_access(user, data.school_id)
    if data.status not in {'PRESENT','ABSENT','LATE'}:
        raise HTTPException(400, 'Invalid attendance status')
    student = session.get(Student, data.student_id)
    if not student or student.school_id != data.school_id:
        raise HTTPException(404, 'Student not found in school')
    ensure_teacher_student_access(user, student, session=session)
    if session.query(Attendance).filter_by(student_id=data.student_id, attendance_date=data.attendance_date).first():
        raise HTTPException(409, 'Attendance already recorded for this date')
    item = Attendance(**data.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

@app.post('/api/v1/homework')
def create_homework(data: HomeworkIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','TEACHER'))):
    require_school_access(user, data.school_id)
    cls = session.get(ClassRoom, data.class_id); subject = session.get(Subject, data.subject_id)
    if not session.get(School, data.school_id) or not cls or cls.school_id != data.school_id or not subject or subject.school_id != data.school_id:
        raise HTTPException(404, 'School, class or subject not found in school')
    if user.role == 'TEACHER' and not session.query(TeacherAssignment).filter_by(school_id=user.school_id, teacher_id=user.id, class_id=data.class_id, subject_id=data.subject_id).first():
        raise HTTPException(403, 'Teacher is not assigned to this class/subject')
    item = Homework(**data.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

@app.post('/api/v1/exams')
def create_exam(data: ExamIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    require_school_access(user, data.school_id)
    if not session.get(School, data.school_id):
        raise HTTPException(404, 'School not found')
    item = Exam(**data.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

@app.post('/api/v1/marks')
def create_mark(data: MarkIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','TEACHER'))):
    require_school_access(user, data.school_id)
    if data.marks > data.max_marks:
        raise HTTPException(400, 'Marks cannot exceed maximum marks')
    student = session.get(Student, data.student_id)
    exam = session.get(Exam, data.exam_id)
    subject = session.get(Subject, data.subject_id)
    if not student or student.school_id != data.school_id:
        raise HTTPException(404, 'Student not found in school')
    if not exam or exam.school_id != data.school_id:
        raise HTTPException(404, 'Exam not found in school')
    if not subject or subject.school_id != data.school_id:
        raise HTTPException(404, 'Subject not found in school')
    ensure_teacher_student_access(user, student, subject_id=data.subject_id, session=session)
    item = Mark(**data.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

@app.get('/api/v1/results/student/{student_id}')
def student_result(student_id: int, exam_id: int, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF','PARENT'))):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(404, 'Student not found')
    require_school_access(user, student.school_id)
    exam = session.get(Exam, exam_id)
    if not exam or exam.school_id != student.school_id:
        raise HTTPException(404, 'Exam not found in school')
    ensure_parent_child_access(user, student, session)
    rows = session.query(Mark).filter_by(student_id=student_id, exam_id=exam_id).all()
    total = sum(r.marks for r in rows); maximum = sum(r.max_marks for r in rows)
    percentage = round(total * 100 / maximum, 2) if maximum else 0
    return {'student_id': student_id, 'exam_id': exam_id, 'subjects': len(rows), 'total': total, 'max_total': maximum, 'percentage': percentage}

# --- APJ Operations Core v1: teacher assignment, timetable, report card, fees, library ---
from sqlalchemy import Time, Float

class TeacherAssignment(Base):
    __tablename__ = 'teacher_assignments'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)

class Timetable(Base):
    __tablename__ = 'timetables'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    weekday = Column(Integer, nullable=False)  # 1=Mon ... 7=Sun
    period = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    __table_args__ = (
        UniqueConstraint('school_id','class_id','weekday','period', name='uq_class_timetable_slot'),
        UniqueConstraint('school_id','teacher_id','weekday','period', name='uq_teacher_timetable_slot'),
    )

class FeeInvoice(Base):
    __tablename__ = 'fee_invoices'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    title = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    paid = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False, default='UNPAID')

class LibraryBook(Base):
    __tablename__ = 'library_books'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    total_copies = Column(Integer, nullable=False, default=1)
    available_copies = Column(Integer, nullable=False, default=1)

class LibraryIssue(Base):
    __tablename__ = 'library_issues'
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
    book_id = Column(Integer, ForeignKey('library_books.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    issue_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    status = Column(String, nullable=False, default='ISSUED')

Base.metadata.create_all(bind=engine)

class TeacherAssignmentIn(BaseModel):
    school_id: int; teacher_id: int; class_id: int; subject_id: int

class TimetableIn(BaseModel):
    school_id: int; class_id: int; subject_id: int; teacher_id: int
    weekday: int = Field(ge=1, le=7); period: int = Field(gt=0)
    start_time: str; end_time: str

class FeeIn(BaseModel):
    school_id: int; student_id: int; title: str
    amount: float = Field(gt=0); paid: float = Field(ge=0, default=0)

class BookIn(BaseModel):
    school_id: int; title: str; author: str | None = None
    total_copies: int = Field(gt=0, default=1)

class IssueIn(BaseModel):
    school_id: int; book_id: int; student_id: int; issue_date: date

@app.post('/api/v1/teacher-assignments')
def create_teacher_assignment(data: TeacherAssignmentIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    require_school_access(user, data.school_id)
    school = session.get(School, data.school_id); teacher = session.get(User, data.teacher_id)
    cls = session.get(ClassRoom, data.class_id); subject = session.get(Subject, data.subject_id)
    if not school or not teacher or teacher.school_id != data.school_id or teacher.role != 'TEACHER':
        raise HTTPException(404, 'Teacher not found in school')
    if not cls or cls.school_id != data.school_id or not subject or subject.school_id != data.school_id:
        raise HTTPException(404, 'Class or subject not found in school')
    item = TeacherAssignment(**data.model_dump()); session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

@app.post('/api/v1/timetable')
def create_timetable(data: TimetableIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    require_school_access(user, data.school_id)
    from datetime import time
    try:
        sh, sm = map(int, data.start_time.split(':')); eh, em = map(int, data.end_time.split(':'))
        start, end = time(sh, sm), time(eh, em)
    except Exception:
        raise HTTPException(400, 'Time must be HH:MM')
    if start >= end: raise HTTPException(400, 'End time must be after start time')
    teacher = session.get(User, data.teacher_id); cls = session.get(ClassRoom, data.class_id); subject = session.get(Subject, data.subject_id)
    if not teacher or teacher.school_id != data.school_id or teacher.role != 'TEACHER': raise HTTPException(404, 'Teacher not found in school')
    if not cls or cls.school_id != data.school_id or not subject or subject.school_id != data.school_id: raise HTTPException(404, 'Class or subject not found in school')
    class_conflict = session.query(Timetable).filter_by(school_id=data.school_id, class_id=data.class_id, weekday=data.weekday, period=data.period).first()
    teacher_conflict = session.query(Timetable).filter_by(school_id=data.school_id, teacher_id=data.teacher_id, weekday=data.weekday, period=data.period).first()
    if class_conflict or teacher_conflict: raise HTTPException(409, 'Timetable slot already occupied')
    item = Timetable(school_id=data.school_id, class_id=data.class_id, subject_id=data.subject_id, teacher_id=data.teacher_id, weekday=data.weekday, period=data.period, start_time=start, end_time=end)
    session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump()}

@app.get('/api/v1/report-card/{student_id}')
def report_card(student_id: int, exam_id: int, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF','PARENT'))):
    student = session.get(Student, student_id)
    exam = session.get(Exam, exam_id)
    if not student or not exam or student.school_id != exam.school_id: raise HTTPException(404, 'Student or exam not found')
    require_school_access(user, student.school_id)
    ensure_parent_child_access(user, student, session)
    rows = session.query(Mark).filter_by(student_id=student_id, exam_id=exam_id).all()
    total = sum(r.marks for r in rows); maximum = sum(r.max_marks for r in rows)
    percentage = round(total * 100 / maximum, 2) if maximum else 0
    grade = 'A' if percentage >= 80 else 'B' if percentage >= 64 else 'C' if percentage >= 50 else 'D' if percentage >= 35 else 'E'
    return {'student': {'id': student.id, 'name': student.name, 'standard': student.standard, 'division': student.division}, 'exam': {'id': exam.id, 'name': exam.name}, 'subjects': [{'subject_id': r.subject_id, 'marks': r.marks, 'max_marks': r.max_marks} for r in rows], 'total': total, 'max_total': maximum, 'percentage': percentage, 'grade': grade, 'result': 'PASS' if percentage >= 35 else 'NEEDS_IMPROVEMENT'}

@app.post('/api/v1/fees')
def create_fee(data: FeeIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN'))):
    require_school_access(user, data.school_id)
    student = session.get(Student, data.student_id)
    if not student or student.school_id != data.school_id: raise HTTPException(404, 'Student not found in school')
    if data.paid > data.amount: raise HTTPException(400, 'Paid amount cannot exceed invoice amount')
    status = 'PAID' if data.paid == data.amount else 'PARTIAL' if data.paid > 0 else 'UNPAID'
    item = FeeInvoice(**data.model_dump(), status=status); session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump(), 'status': status, 'outstanding': round(data.amount-data.paid, 2)}

@app.get('/api/v1/fees/student/{student_id}')
def student_fees(student_id: int, school_id: int, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF'))):
    student = session.get(Student, student_id)
    require_school_access(user, school_id)
    if not student or student.school_id != school_id: raise HTTPException(404, 'Student not found in school')
    rows = session.query(FeeInvoice).filter_by(student_id=student_id, school_id=school_id).all()
    return {'student_id': student_id, 'invoices': [{'id': r.id, 'title': r.title, 'amount': r.amount, 'paid': r.paid, 'outstanding': round(r.amount-r.paid,2), 'status': r.status} for r in rows]}

@app.post('/api/v1/library/books')
def create_book(data: BookIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF'))):
    require_school_access(user, data.school_id)
    if not session.get(School, data.school_id): raise HTTPException(404, 'School not found')
    item = LibraryBook(**data.model_dump(), available_copies=data.total_copies); session.add(item); session.commit(); session.refresh(item)
    return {'id': item.id, **data.model_dump(), 'available_copies': item.available_copies}

@app.post('/api/v1/library/issue')
def issue_book(data: IssueIn, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF'))):
    require_school_access(user, data.school_id)
    book = session.get(LibraryBook, data.book_id); student = session.get(Student, data.student_id)
    if not book or book.school_id != data.school_id: raise HTTPException(404, 'Book not found in school')
    if not student or student.school_id != data.school_id: raise HTTPException(404, 'Student not found in school')
    if book.available_copies <= 0: raise HTTPException(409, 'No copies available')
    issue = LibraryIssue(**data.model_dump()); book.available_copies -= 1
    session.add(issue); session.commit(); session.refresh(issue)
    return {'id': issue.id, **data.model_dump(), 'status': issue.status}

@app.post('/api/v1/library/return/{issue_id}')
def return_book(issue_id: int, school_id: int, return_date: date, session: Session = Depends(db), user=Depends(require_roles('SUPER_ADMIN','ADMIN','STAFF'))):
    require_school_access(user, school_id)
    issue = session.get(LibraryIssue, issue_id); book = session.get(LibraryBook, issue.book_id) if issue else None
    if not issue or issue.school_id != school_id: raise HTTPException(404, 'Issue not found in school')
    if issue.status == 'RETURNED': raise HTTPException(409, 'Book already returned')
    issue.status = 'RETURNED'; issue.return_date = return_date
    if book: book.available_copies = min(book.total_copies, book.available_copies + 1)
    session.commit()
    return {'id': issue.id, 'status': issue.status, 'return_date': issue.return_date}
