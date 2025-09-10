import uuid
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

# --- 1. Admission Models ---

class AdmissionBase(BaseModel):
    student_name: str
    date_of_birth: date
    gender: str
    contact_number: str
    email: str
    address: str
    course_applied: str
    department: str
    admission_status: str
    parent_guardian_name: str
    parent_guardian_contact: str
    nationality: str
    category: str
    remarks: Optional[str] = None

class AdmissionCreate(AdmissionBase):
    admission_id: str = Field(default_factory=lambda: f"ADM-{uuid.uuid4().hex[:6].upper()}")
    admission_date: date = Field(default_factory=date.today)

class Admission(AdmissionBase):
    admission_id: str
    admission_date: date

class AdmissionUpdate(BaseModel):
    student_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    course_applied: Optional[str] = None
    department: Optional[str] = None
    admission_status: Optional[str] = None
    parent_guardian_name: Optional[str] = None
    parent_guardian_contact: Optional[str] = None
    nationality: Optional[str] = None
    category: Optional[str] = None
    remarks: Optional[str] = None

# --- 2. Library Models ---

class BookBase(BaseModel):
    title: str
    author: str
    genre: str
    publisher: str
    edition_year: str
    isbn: Optional[str] = None
    shelf_location: str
    availability_status: str = "Available"
    issued_to: Optional[str] = None
    issue_date: Optional[date] = None
    return_date: Optional[date] = None
    fine_rate: float = 0.0
    fine_accrued: float = 0.0

class BookCreate(BookBase):
    book_id: str = Field(default_factory=lambda: f"BK-{uuid.uuid4().hex[:8].upper()}")

class Book(BookBase):
    book_id: str

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[str] = None
    publisher: Optional[str] = None
    edition_year: Optional[str] = None
    isbn: Optional[str] = None
    shelf_location: Optional[str] = None
    availability_status: Optional[str] = None
    issued_to: Optional[str] = None
    issue_date: Optional[date] = None
    return_date: Optional[date] = None
    fine_rate: Optional[float] = None
    fine_accrued: Optional[float] = None

# --- 3. Hostel Models ---

class HostelOccupancyBase(BaseModel):
    hostel_id: str
    room_type: str
    fee_status: str
    room_number: str
    occupied_beds: int
    vacant_beds: int
    student_id: str
    student_name: str
    check_in_date: date
    check_out_date: Optional[date] = None
    status: str

class HostelOccupancyCreate(HostelOccupancyBase):
    occupancy_id: str = Field(default_factory=lambda: f"HOC-{uuid.uuid4().hex[:6].upper()}")

class HostelOccupancy(HostelOccupancyBase):
    occupancy_id: str

class HostelOccupancyUpdate(BaseModel):
    hostel_id: Optional[str] = None
    room_type: Optional[str] = None
    fee_status: Optional[str] = None
    room_number: Optional[str] = None
    occupied_beds: Optional[int] = None
    vacant_beds: Optional[int] = None
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    status: Optional[str] = None

# --- 4. Fee Models ---

class FeeReceiptBase(BaseModel):
    student_id: str
    student_name: str
    course: str
    semester_year: str
    fee_type: str
    amount: float
    payment_mode: str
    transaction_id: Optional[str] = None
    status: str
    remarks: Optional[str] = None

class FeeReceiptCreate(FeeReceiptBase):
    receipt_id: str = Field(default_factory=lambda: f"RCPT-{uuid.uuid4().hex[:8].upper()}")
    payment_date: date = Field(default_factory=date.today)

class FeeReceipt(FeeReceiptBase):
    receipt_id: str
    payment_date: date

class FeeReceiptUpdate(BaseModel):
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    course: Optional[str] = None
    semester_year: Optional[str] = None
    fee_type: Optional[str] = None
    amount: Optional[float] = None
    payment_mode: Optional[str] = None
    transaction_id: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None

# --- 5. User Login Models ---

class AppUserBase(BaseModel):
    username: str
    role: str
    # Note: Storing plain text passwords is a security risk.
    # In a real database, this would be a hashed password.
    # For Google Sheets, this is a known limitation.
    password: str 

class AppUserCreate(AppUserBase):
    user_id: str = Field(default_factory=lambda: f"USR-{uuid.uuid4().hex[:6].upper()}")

class AppUser(AppUserBase):
    user_id: str

class AppUserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

