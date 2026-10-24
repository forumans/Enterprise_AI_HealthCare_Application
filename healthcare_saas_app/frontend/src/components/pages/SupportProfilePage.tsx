/**
 * Support Profile Page Component
 * Lets support staff update their own name and phone; the email (their login) is shown read-only
 * Mirrors the doctor and patient Update Profile pages
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { parseErrorMessage } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";

interface SupportProfilePageProps {
  auth: any;
}

interface FieldErrors {
  fullName?: string;
  phone?: string;
}

const HOME = "/support/patient-appointments";

export function SupportProfilePage({ auth }: SupportProfilePageProps) {
  const navigate = useNavigate();
  const { status, setStatus } = useAuthContext();

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Clear any existing status messages when navigating to profile page
  useEffect(() => {
    setStatus("");
  }, [setStatus]);

  useEffect(() => {
    if (!auth.session.accessToken) return;
    api.getSupportProfile(auth.session.accessToken)
      .then((data) => {
        setFullName(data.full_name || "");
        setPhone(data.phone || "");
        setEmail(data.email || "");
      })
      .catch((error) => {
        console.error("Failed to load support staff profile:", error);
        setStatus(parseErrorMessage(error));
      });
  }, [auth.session.accessToken, setStatus]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitAttempted(true);

    const nextErrors: FieldErrors = {};
    if (fullName.trim().length < 3) {
      nextErrors.fullName = "Name must be at least 3 characters.";
    }
    if (!/^\+?[0-9\-\s]{10,15}$/.test(phone.trim())) {
      nextErrors.phone = "Phone should be 10-15 digits.";
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setLoading(true);
    try {
      await api.updateSupportProfile(auth.session.accessToken, { full_name: fullName.trim(), phone: phone.trim() });
      setStatus("Profile updated successfully!");
      setTimeout(() => {
        setStatus("");
        navigate(HOME);
      }, 1500);
    } catch (error) {
      console.error("Failed to update profile:", error);
      setStatus(parseErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  const buttonStyle = (color: string): React.CSSProperties => ({
    flex: '1',
    padding: '12px 24px',
    fontSize: '16px',
    fontWeight: '500',
    background: loading ? '#94a3b8' : color,
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.6 : 1
  });

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Update Profile</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Update your contact information
      </p>

      {status && (
        <StatusMessage
          message={status}
          type={status.includes("success") ? 'success' : 'error'}
        />
      )}

      <form onSubmit={handleSubmit} className="form-stack">
        <LabeledField
          id="support-profile-full-name"
          label="Full Name"
          helpText="Name must be 3-80 characters."
          value={fullName}
          onChange={setFullName}
          error={submitAttempted ? errors.fullName : undefined}
          autoComplete="off"
        />

        <LabeledField
          id="support-profile-phone"
          label="Phone"
          helpText="Use 10-15 digits. Country code allowed."
          value={phone}
          onChange={setPhone}
          error={submitAttempted ? errors.phone : undefined}
          autoComplete="off"
        />

        <div>
          <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Email</label>
          <p style={{ margin: 0, fontSize: '14px', color: '#e8f6ff' }}>{email || '—'}</p>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>Your login email. Ask an administrator to change it.</p>
        </div>

        <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
          <button type="submit" disabled={loading} style={buttonStyle('#42b5f5')}>
            {loading ? 'Updating...' : 'Update Profile'}
          </button>
          <button type="button" onClick={() => navigate(HOME)} disabled={loading} style={buttonStyle('#94a3b8')}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
