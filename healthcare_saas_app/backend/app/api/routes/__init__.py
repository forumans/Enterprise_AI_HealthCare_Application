"""API route registry."""

from fastapi import APIRouter

from .admin import router as admin_router
from .admin_password_reset import router as admin_password_reset_router
from .appointments import router as appointments_router
from .audit_logs import router as audit_router
from .auth import router as auth_router
from .documents import router as documents_router
from .doctor import router as doctor_router
from .medical_records import router as medical_records_router
from .patient import router as patient_router
from .patients import router as patients_router
from .prescriptions import router as prescriptions_router
from .support import router as support_router
from .tenants import router as tenants_router
from .users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(tenants_router, tags=["tenants"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(patient_router, tags=["patient"])
api_router.include_router(patients_router, tags=["patients"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(doctor_router, tags=["doctor"])
api_router.include_router(appointments_router, tags=["appointments"])
api_router.include_router(medical_records_router, tags=["medical-records"])
api_router.include_router(prescriptions_router, tags=["prescriptions"])
api_router.include_router(support_router, tags=["support"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(admin_password_reset_router, prefix="/admin", tags=["admin-password-reset"])
api_router.include_router(audit_router, tags=["audit-logs"])
