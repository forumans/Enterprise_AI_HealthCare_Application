/**
 * Main Healthcare Application Component
 * Uses modular architecture with separated concerns for better maintainability
 * Provides a clean, scalable structure for the healthcare SaaS platform
 */

import React from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";

// Import modular components and hooks
import { 
  AppHeader, 
  AppLayout, 
  ConsultationForm, 
  PatientDetailsCard, 
  LoginPage,
  ProtectedRoute,
  StatusMessage
} from "./components";
import { 
  DoctorAppointmentsPage 
} from "./components/pages/DoctorAppointmentsPage";
import { 
  DoctorRegistrationPage 
} from "./components/pages/DoctorRegistrationPage";
import { 
  ManageAvailabilityPage 
} from "./components/pages/ManageAvailabilityPage";
import { 
  SearchPatientsPage 
} from "./components/pages/SearchPatientsPage";
import { 
  DoctorProfilePage 
} from "./components/pages/DoctorProfilePage";
import { 
  TodayAppointmentsPage 
} from "./components/pages/TodayAppointmentsPage";
import { 
  PatientAppointmentsPage 
} from "./components/pages/PatientAppointmentsPage";
import { 
  PatientProfilePage 
} from "./components/pages/PatientProfilePage";
import { 
  PatientPrescriptionsPage 
} from "./components/pages/PatientPrescriptionsPage";
import { 
  PatientRegistrationPage 
} from "./components/pages/PatientRegistrationPage";
import { 
  SystemDashboardPage 
} from "./components/pages/SystemDashboardPage";
import { 
  AdminResetPasswordPage 
} from "./components/pages/AdminResetPasswordPage";
import { 
  AdminRegistrationPage 
} from "./components/pages/AdminRegistrationPage";
import { 
  AdminRegisterPatientPage 
} from "./components/pages/AdminRegisterPatientPage";
import { 
  AdminRegisterDoctorPage 
} from "./components/pages/AdminRegisterDoctorPage";
import { 
  useAppointments, 
  useUserData, 
  useNavigation 
} from "./hooks";
import { 
  AuthProvider,
  useAuthContext 
} from "./contexts/AuthContext";
import { 
  getRouteBreadcrumb
} from "./app/routeBreadcrumbs";
import { 
  requireRole 
} from "./app/access";
import { 
  useMedicalNewsAgent 
} from "./hooks";
import type { Role } from "./types/app";

/**
 * Main Healthcare Application Component
 * Orchestrates all application functionality using modular hooks and components
 */
function AppContent() {
  // Custom hooks for different concerns
  const auth = useAuthContext();
  const appointments = useAppointments(auth.session);
  const userData = useUserData(auth.session);
  const navigation = useNavigation(auth.session);
  const medicalNewsAgent = useMedicalNewsAgent();

  // Handle sign out
  const handleSignOut = () => {
    auth.handleLogout();
    userData.clearUserData();
    appointments.setAppointments([]);
    appointments.setDoctorAppointments([]);
    appointments.setSearchRows([]);
  };

  // Handle login route clearing
  React.useEffect(() => {
    if (window.location.pathname.includes("/login")) {
      if (auth.session.role !== "GUEST") {
        handleSignOut();
      }
      auth.resetLoginForm();
    }
  }, [window.location.pathname]);

  // Handle register route clearing
  React.useEffect(() => {
    if (window.location.pathname.includes("/register")) {
      auth.resetLoginForm();
      auth.resetPatientRegistration();
    }
  }, [window.location.pathname]);

  return (
    <div className="app-shell">
      <AppHeader session={auth.session} onSignOut={handleSignOut} tenantInfo={userData.tenantInfo} />
      
      <main className="content content-full">
        <Routes>
          {/* Home route */}
          <Route path="/" element={<AppLayout session={auth.session} status={auth.status}><HomePage auth={auth} userData={userData} /></AppLayout>} />
          
          {/* Login routes - not wrapped in AppLayout */}
          <Route path="/patients/login" element={<LoginPage role="PATIENT" />} />
          <Route path="/doctors/login" element={<LoginPage role="DOCTOR" />} />
          <Route path="/admin/login" element={<LoginPage role="ADMIN" />} />
          
          {/* Public routes - no authentication required */}
          <Route path="/patients/register" element={<AppLayout session={auth.session} status={auth.status}><PatientRegistrationPage /></AppLayout>} />
          
          {/* Protected routes - wrapped in AppLayout */}
          <Route 
            path="/patients/appointments" 
            element={
              <ProtectedRoute allowed={["PATIENT"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <PatientAppointmentsPage 
                    auth={auth}
                    appointments={appointments}
                    userData={userData}
                  />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/patients/prescriptions" 
            element={
              <ProtectedRoute allowed={["PATIENT"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <PatientPrescriptionsPage auth={auth} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/patients/billing" 
            element={
              <ProtectedRoute allowed={["PATIENT"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <BillingPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/patients/profile" 
            element={
              <ProtectedRoute allowed={["PATIENT"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <PatientProfilePage auth={auth} userData={userData} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Doctor routes */}
          <Route 
            path="/doctors/register" 
            element={
              <AppLayout session={auth.session} status={auth.status}>
                <DoctorRegistrationPage auth={auth} />
              </AppLayout>
            } 
          />
          <Route 
            path="/doctors/appointments" 
            element={
              <ProtectedRoute allowed={["DOCTOR"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <DoctorAppointmentsPage 
                    auth={auth}
                    appointments={appointments}
                  />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/doctors/today-appointments" 
            element={
              <ProtectedRoute allowed={["DOCTOR"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <TodayAppointmentsPage 
                    auth={auth}
                    appointments={appointments}
                    userData={userData}
                  />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/doctors/search-patients" 
            element={
              <ProtectedRoute allowed={["DOCTOR"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <SearchPatientsPage 
                    auth={auth}
                    appointments={appointments}
                  />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/doctors/manage-availability" 
            element={
              <ProtectedRoute allowed={["DOCTOR"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <ManageAvailabilityPage auth={auth} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/doctors/profile" 
            element={
              <ProtectedRoute allowed={["DOCTOR"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <DoctorProfilePage auth={auth} userData={userData} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/doctors/consultation/:appointmentId" 
            element={
              <ProtectedRoute allowed={["DOCTOR"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <ConsultationForm 
                    session={auth.session} 
                    appointmentId={window.location.pathname.split('/').pop() || ''} 
                  />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Admin routes */}
          <Route 
            path="/admin/register-doctor" 
            element={
              <ProtectedRoute allowed={["ADMIN"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <AdminRegisterDoctorPage auth={auth} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin/register-patient" 
            element={
              <ProtectedRoute allowed={["ADMIN"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <AdminRegisterPatientPage auth={auth} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin/register-admin" 
            element={
              <ProtectedRoute allowed={["ADMIN"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <AdminRegistrationPage auth={auth} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin/system-dashboard" 
            element={
              <ProtectedRoute allowed={["ADMIN"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <SystemDashboardPage auth={auth} userData={userData} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin/reset-password" 
            element={
              <ProtectedRoute allowed={["ADMIN"]} role={auth.session.role}>
                <AppLayout session={auth.session} status={auth.status}>
                  <AdminResetPasswordPage auth={auth} />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

// Page components (these will be moved to separate files in the future)
function HomePage({ auth, userData }: any) {
  const newsQuery = useMedicalNewsAgent();
  const navigate = useNavigate();
  
  return (
    <section>
      <h1>Smart Healthcare Management Platform</h1>
      <p className="lead-text">Manage doctors, patients, appointments, prescriptions, and billing from a single unified platform.</p>
      <div className="hero-actions">
        {auth.session.role !== "PATIENT" && (
          <button onClick={() => navigate("/patients/login")}>Patient Login</button>
        )}
        <button onClick={() => navigate("/doctors/login")}>Doctor Login</button>
      </div>
      <h2>Latest Medical Breakthroughs</h2>
      <div className="card-grid">
        {newsQuery.isLoading
          ? Array.from({ length: 5 }).map((_, index) => <article className="skeleton-card" key={index} />)
          : newsQuery.data?.map((item) => (
              <article className="card" key={item.id}>
                <div className="card-icon">🔬</div>
                <h3>{item.headline}</h3>
                <p className="muted">
                  <span className="source-icon">📰</span>
                  {item.source}
                </p>
                <p>{item.summary}</p>
                <a 
                  href={`https://www.google.com/search?q=${encodeURIComponent(item.headline + ' ' + item.source)}`}
                  target="_blank" 
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    e.preventDefault();
                    const searchQuery = encodeURIComponent(item.headline + ' ' + item.source);
                    window.open(`https://www.google.com/search?q=${searchQuery}`, '_blank', 'noopener,noreferrer');
                  }}
                >
                  Read more <span className="arrow">→</span>
                </a>
              </article>
            ))}
      </div>
    </section>
  );
}

function BillingPage() {
  return <div>Billing Page - To be implemented</div>;
}

function AdminRegisterAdminPage({ auth, userData }: any) {
  return <div>Admin Register Admin Page - To be implemented</div>;
}
