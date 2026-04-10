/**
 * System Dashboard Page Component
 * Admin dashboard for system management and overview
 * Displays system statistics and admin functions
 */

import React, { useState, useEffect } from "react";
import type { AdminUserRow, AppointmentMetrics } from "../../types/app";
import { useNavigate } from "react-router-dom";
import {
  buildSystemStats,
  defaultAppointmentMetrics,
  type SystemStats,
} from "./systemDashboardStats";

interface SystemDashboardPageProps {
  auth: any;
  userData: any;
}

export function SystemDashboardPage({ auth, userData }: SystemDashboardPageProps) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const tenantName = userData.tenantInfo?.name || auth.session.tenantId || "-";
  const [systemStats, setSystemStats] = useState<SystemStats>({
    totalDoctors: 0,
    totalPatients: 0,
    totalAppointmentsToDate: 0,
    totalAppointmentsYearToDate: 0,
    totalAppointmentsThisMonth: 0,
    totalAppointmentsThisWeek: 0,
    totalAppointmentsToday: 0,
  });

  useEffect(() => {
    const loadDashboardData = async () => {
      setLoading(true);
      try {
        const dashboardData = await userData.loadAdminDashboard();
        const users: AdminUserRow[] = dashboardData?.adminUsers ?? userData.adminUsers ?? [];
        const appointmentMetrics: AppointmentMetrics =
          dashboardData?.appointmentMetrics ??
          userData.appointmentMetrics ??
          defaultAppointmentMetrics;

        setSystemStats(buildSystemStats(users, appointmentMetrics));
      } catch (error) {
        console.error("Failed to load dashboard data:", error);
      } finally {
        setLoading(false);
      }
    };

    if (auth.session.accessToken) {
      loadDashboardData();
    }
  }, [auth.session.accessToken]);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>System Dashboard</h2>
      
      {/* Admin Information */}
      <div className="card" style={{ padding: '16px' }}>
        <h3 style={{ margin: '0 0 12px 0', color: '#dff2ff' }}>Administrator</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
          <div>
            <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Name</label>
            <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>
              {auth.session.userName || 'System Administrator'}
            </p>
          </div>
          <div>
            <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Role</label>
            <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>Administrator</p>
          </div>
          <div>
            <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Tenant Name</label>
            <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>
              {tenantName}
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: '#b4cce2' }}>
          Loading dashboard data...
        </div>
      ) : (
        <>
          {/* System Statistics */}
          <div className="card" style={{ padding: '16px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>System Overview</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(66, 181, 245, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#42b5f5', marginBottom: '8px' }}>
                  {systemStats.totalDoctors}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Total Doctors</div>
              </div>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(73, 215, 194, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#49d7c2', marginBottom: '8px' }}>
                  {systemStats.totalPatients}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Total Patients</div>
              </div>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(255, 144, 171, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#ff90ab', marginBottom: '8px' }}>
                  {systemStats.totalAppointmentsToDate}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Appointments (To Date)</div>
              </div>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(255, 193, 7, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#ffc107', marginBottom: '8px' }}>
                  {systemStats.totalAppointmentsYearToDate}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Appointments YTD</div>
              </div>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(181, 66, 245, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#b542f5', marginBottom: '8px' }}>
                  {systemStats.totalAppointmentsThisMonth}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Appointments This Month</div>
              </div>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(66, 245, 166, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#42f5a6', marginBottom: '8px' }}>
                  {systemStats.totalAppointmentsThisWeek}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Appointments This Week</div>
              </div>
              <div style={{ textAlign: 'center', padding: '20px', backgroundColor: 'rgba(245, 129, 66, 0.1)', borderRadius: '8px' }}>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#f58142', marginBottom: '8px' }}>
                  {systemStats.totalAppointmentsToday}
                </div>
                <div style={{ fontSize: '14px', color: '#b4cce2', textTransform: 'uppercase' }}>Appointments Today</div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card" style={{ padding: '16px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>Quick Actions</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
              <button
                onClick={() => navigate('/admin/register-doctor')}
                style={{
                  background: '#42b5f5',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '12px 16px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                Register New Doctor
              </button>
              <button
                onClick={() => navigate('/admin/register-patient')}
                style={{
                  background: '#49d7c2',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '12px 16px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                Register New Patient
              </button>
              <button
                onClick={() => navigate('/admin/register-admin')}
                style={{
                  background: '#ff90ab',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '12px 16px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                Register New Admin
              </button>
            </div>
          </div>

          {/* Recent Users */}
          {userData.adminUsers && userData.adminUsers.length > 0 && (
            <div className="card" style={{ padding: '16px' }}>
              <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>
                Recent Users ({userData.adminUsers.length})
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(136, 194, 227, 0.36)' }}>
                      <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px' }}>Name</th>
                      <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px' }}>Email</th>
                      <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px' }}>Role</th>
                      <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {userData.adminUsers.slice(0, 10).map((user: AdminUserRow, index: number) => (
                      <tr key={user.id} style={{ borderBottom: '1px solid rgba(136, 194, 227, 0.2)' }}>
                        <td style={{ padding: '12px', color: '#eef8ff', fontSize: '14px' }}>{user.name}</td>
                        <td style={{ padding: '12px', color: '#eef8ff', fontSize: '14px' }}>{user.email}</td>
                        <td style={{ padding: '12px', color: '#eef8ff', fontSize: '14px' }}>{user.role}</td>
                        <td style={{ padding: '12px' }}>
                          <span style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: '500',
                            backgroundColor: user.is_deleted ? '#ff90ab' : '#49d7c2',
                            color: 'white'
                          }}>
                            {user.is_deleted ? 'Inactive' : 'Active'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
