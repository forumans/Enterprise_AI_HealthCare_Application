/**
 * User Data Hook
 * Manages user data fetching and state management
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import type { SessionState } from '../types/app';

interface UserDataState {
  users: any[];
  adminUsers: any[];
  reports: any;
  appointmentMetrics: any;
  patientDetails: any;
  tenantInfo: any;
  loading: boolean;
  error: string | null;
}

export function useUserData(session: SessionState) {
  const [state, setState] = useState<UserDataState>({
    users: [],
    adminUsers: [],
    reports: {},
    appointmentMetrics: {},
    patientDetails: null,
    tenantInfo: null,
    loading: false,
    error: null
  });

  const loadUsers = async () => {
    if (!session.accessToken || session.role !== 'ADMIN') {
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const users = await api.getUsers(session.accessToken);
      setState(prev => ({
        ...prev,
        users,
        loading: false,
        error: null
      }));
    } catch (error) {
      console.error('Failed to load users:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load users'
      }));
    }
  };

  const loadAdminDashboard = async () => {
    if (!session.accessToken || session.role !== 'ADMIN') {
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      // Load admin users, reports, and appointment metrics
      const [adminUsers, reports, appointmentMetrics] = await Promise.all([
        api.getUsers(session.accessToken),
        api.getAdminReports(session.accessToken),
        api.getAdminAppointmentMetrics(session.accessToken),
      ]);
      
      setState(prev => ({
        ...prev,
        adminUsers,
        reports,
        appointmentMetrics,
        loading: false,
        error: null
      }));

      return { adminUsers, reports, appointmentMetrics };
    } catch (error) {
      console.error('Failed to load admin dashboard:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load admin dashboard'
      }));

      return undefined;
    }
  };

  const loadPatientDetails = async () => {
    if (!session.accessToken || session.role !== 'PATIENT') {
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const patientDetails = await api.getPatientProfile(session.accessToken);
      setState(prev => ({
        ...prev,
        patientDetails,
        loading: false,
        error: null
      }));
    } catch (error) {
      console.error('Failed to load patient details:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load patient details'
      }));
    }
  };

  const loadTenantInfo = async () => {
    if (!session.accessToken) {
      console.log('No access token, skipping tenant info load');
      return;
    }

    console.log('Loading tenant info with token:', session.accessToken ? 'Token present' : 'No token');
    
    try {
      // First, debug what identity we have
      const debugInfo = await api.debugTenantInfo(session.accessToken);
      console.log('Debug info:', debugInfo);
      
      // Then get the actual tenant info
      const tenantInfo = await api.getCurrentTenant(session.accessToken);
      console.log('Tenant info loaded:', tenantInfo);
      setState(prev => ({
        ...prev,
        tenantInfo
      }));
    } catch (error) {
      console.error('Failed to load tenant info:', error);
      console.error('Error details:', error.response?.data || error.message);
      // Don't set error state for tenant info failure as it's not critical
    }
  };

  const clearUserData = () => {
    setState({
      users: [],
      adminUsers: [],
      reports: {},
      appointmentMetrics: {},
      patientDetails: null,
      tenantInfo: null,
      loading: false,
      error: null
    });
  };

  // Load users when session changes
  useEffect(() => {
    console.log('useUserData useEffect triggered:', { 
      hasAccessToken: !!session.accessToken, 
      role: session.role,
      fullSession: session
    });
    
    if (session.accessToken && session.role === 'ADMIN') {
      loadUsers();
    } else {
      setState(prev => ({ ...prev, users: [], adminUsers: [] }));
    }

    // Load tenant info for all authenticated users
    if (session.accessToken) {
      console.log('Calling loadTenantInfo...');
      loadTenantInfo();
    } else {
      console.log('No access token found in session');
    }
  }, [session.accessToken, session.role]);

  return {
    ...state,
    loadUsers,
    loadAdminDashboard,
    loadPatientDetails,
    loadTenantInfo,
    clearUserData
  };
}
