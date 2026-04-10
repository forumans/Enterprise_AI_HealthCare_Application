/**
 * Admin Reset Password Page Component
 * Allows admin to reset passwords for users by email and role
 */

import React, { useState, useEffect } from 'react';
import { LabeledField } from '../common/LabeledField';
import { api } from '../../api';

interface AdminResetPasswordPageProps {
  auth: any;
}

interface RoleOption {
  value: string;
  label: string;
}

export function AdminResetPasswordPage({ auth }: AdminResetPasswordPageProps) {
  const [formData, setFormData] = useState({
    role: '',
    email: '',
    newPassword: '',
    confirmPassword: ''
  });
  
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadRoles();
  }, []);

  const loadRoles = async () => {
    try {
      const rolesData = await api.getResetPasswordRoles(auth.session.accessToken);
      setRoles(rolesData);
    } catch (err) {
      console.error('Failed to load roles:', err);
      setError('Failed to load roles');
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear messages when user starts typing
    if (error) setError('');
    if (success) setSuccess('');
  };

  const validateForm = () => {
    if (!formData.role) {
      setError('Please select a role');
      return false;
    }
    
    if (!formData.email) {
      setError('Please enter an email address');
      return false;
    }
    
    if (!formData.newPassword) {
      setError('Please enter a new password');
      return false;
    }
    
    if (!formData.confirmPassword) {
      setError('Please confirm the new password');
      return false;
    }
    
    if (formData.newPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return false;
    }
    
    if (formData.newPassword !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Please enter a valid email address');
      return false;
    }
    
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      const result = await api.resetUserPassword(
        formData.email,
        formData.role,
        formData.newPassword,
        auth.session.accessToken
      );
      
      setSuccess(`Password reset successfully for ${result.user_email} (${result.user_role})`);
      
      // Reset form
      setFormData({
        role: '',
        email: '',
        newPassword: '',
        confirmPassword: ''
      });
      
    } catch (err: any) {
      console.error('Password reset failed:', err);
      if (err.message && err.message.includes('User not found')) {
        setError('User not found with the provided email and role combination');
      } else if (err.message && err.message.includes('Invalid role')) {
        setError('Invalid role selected');
      } else {
        setError('Failed to reset password. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px' }}>
      <h2 style={{ 
        color: '#eef8ff', 
        marginBottom: '8px',
        fontSize: '24px',
        fontWeight: '600'
      }}>
        Reset Password
      </h2>
      
      <p style={{ 
        color: '#b4cce2', 
        marginBottom: '32px',
        fontSize: '14px',
        lineHeight: '1.5'
      }}>
        Reset password for users by selecting their role and entering their email address.
      </p>
      
      {error && (
        <div style={{
          backgroundColor: 'rgba(255, 144, 171, 0.1)',
          border: '1px solid rgba(255, 144, 171, 0.3)',
          borderRadius: '8px',
          padding: '16px',
          marginBottom: '24px',
          color: '#ff90ab',
          fontSize: '14px'
        }}>
          {error}
        </div>
      )}
      
      {success && (
        <div style={{
          backgroundColor: 'rgba(66, 181, 245, 0.1)',
          border: '1px solid rgba(66, 181, 245, 0.3)',
          borderRadius: '8px',
          padding: '16px',
          marginBottom: '24px',
          color: '#42b5f5',
          fontSize: '14px'
        }}>
          {success}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="form-stack">
        <div style={{ marginBottom: '24px' }}>
          <label style={{
            display: 'block',
            color: '#eef8ff',
            marginBottom: '8px',
            fontSize: '14px',
            fontWeight: '500'
          }}>
            Role <span style={{ color: '#ff90ab', marginLeft: '4px' }}>*</span>
          </label>
          <select
            value={formData.role}
            onChange={(e) => handleInputChange('role', e.target.value)}
            required
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              backgroundColor: 'rgba(9, 35, 55, 0.82)',
              color: '#eef8ff',
              fontSize: '14px',
              fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
            }}
          >
            <option value="">Select a role</option>
            {roles.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>
        </div>

        <LabeledField
          id="email"
          label="Email Address"
          helpText="Enter the user's registered email address"
          value={formData.email}
          onChange={(value) => handleInputChange('email', value)}
          type="email"
          placeholder="user.email@example.com"
          required={true}
        />

        <LabeledField
          id="new-password"
          label="New Password"
          helpText="Enter the new password (minimum 8 characters)"
          value={formData.newPassword}
          onChange={(value) => handleInputChange('newPassword', value)}
          type="password"
          placeholder="Enter new password"
          required={true}
        />

        <LabeledField
          id="confirm-password"
          label="Confirm New Password"
          helpText="Re-enter the new password to confirm"
          value={formData.confirmPassword}
          onChange={(value) => handleInputChange('confirmPassword', value)}
          type="password"
          placeholder="Confirm new password"
          required={true}
        />

        <button
          type="submit"
          className="button-primary"
          disabled={loading}
          style={{
            width: '100%',
            padding: '14px 24px',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: loading ? '#6b7280' : '#42b5f5',
            color: '#ffffff',
            fontSize: '16px',
            fontWeight: '500',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            marginTop: '8px'
          }}
        >
          {loading ? 'Resetting Password...' : 'Reset Password'}
        </button>
      </form>
      
      <div style={{
        marginTop: '32px',
        padding: '16px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderRadius: '8px',
        border: '1px solid rgba(255, 255, 255, 0.1)'
      }}>
        <h4 style={{
          color: '#eef8ff',
          marginBottom: '12px',
          fontSize: '14px',
          fontWeight: '500'
        }}>
          Important Notes:
        </h4>
        <ul style={{
          color: '#b4cce2',
          fontSize: '13px',
          lineHeight: '1.6',
          margin: '0',
          paddingLeft: '20px'
        }}>
          <li>All fields are required to reset a password</li>
          <li>Password must be at least 8 characters long</li>
          <li>The system will verify the email and role combination</li>
          <li>Users will need to use their new password for next login</li>
        </ul>
      </div>
    </div>
  );
}
