/**
 * Admin Reset Password Page Component
 * Admin picks a role, searches for a person by name, email or phone, clicks their name, and then
 * changes that user's login email and/or resets their password (by user id).
 */

import React, { useState } from 'react';
import { LabeledField } from '../common/LabeledField';
import { AdminUserSearch } from '../common/AdminUserSearch';
import { api } from '../../api';
import { parseErrorMessage } from '../../utils';
import type { AdminUserSearchRow } from '../../types';

interface AdminResetPasswordPageProps {
  auth: any;
}

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;
const ROLE_LABELS: Record<string, string> = { PATIENT: 'Patient', DOCTOR: 'Doctor', SUPPORT_STAFF: 'Support Staff', ADMIN: 'Admin' };

const cardStyle: React.CSSProperties = { padding: '20px' };
const messageStyle = (kind: 'error' | 'success'): React.CSSProperties => ({
  backgroundColor: kind === 'error' ? 'rgba(255, 144, 171, 0.1)' : 'rgba(66, 181, 245, 0.1)',
  border: `1px solid ${kind === 'error' ? 'rgba(255, 144, 171, 0.3)' : 'rgba(66, 181, 245, 0.3)'}`,
  borderRadius: '8px',
  padding: '12px 16px',
  marginBottom: '16px',
  color: kind === 'error' ? '#ff90ab' : '#42b5f5',
  fontSize: '14px'
});
const submitStyle = (busy: boolean): React.CSSProperties => ({
  width: '100%',
  padding: '12px 24px',
  borderRadius: '8px',
  border: 'none',
  background: busy ? '#6b7280' : '#42b5f5',
  color: '#ffffff',
  fontSize: '15px',
  fontWeight: '500',
  cursor: busy ? 'not-allowed' : 'pointer',
  marginTop: '8px'
});

const dash = (value: string) => value || '—';

/**
 * Plain text input for a *new* email. Browsers treat an email-type field near password fields as a
 * login form and pre-fill a saved login (e.g. the support staff email you signed in with earlier),
 * which then gets submitted as the "new" email. A text input with no login-like name/autocomplete
 * hints and password-manager opt-outs keeps it empty until the admin types.
 */
function NewEmailInput({ id, value, onChange, placeholder }: { id: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <input
      id={id}
      name={`${id}-value`}
      type="text"
      inputMode="email"
      autoComplete="off"
      autoCapitalize="none"
      spellCheck={false}
      data-lpignore="true"
      data-1p-ignore="true"
      data-form-type="other"
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      required
    />
  );
}

/** One action form (change email or reset password) for the picked user: a value typed twice. */
function ConfirmedValueForm({ title, description, current, label, helpText, inputType, placeholder, submitLabel, busyLabel, validate, onSubmit }: {
  title: string;
  description: string;
  /** Highlighted above the inputs so it isn't mistaken for a field, e.g. the current email. */
  current?: { label: string; value: string };
  label: string;
  helpText: string;
  inputType: 'email' | 'password';
  placeholder: string;
  submitLabel: string;
  busyLabel: string;
  validate: (value: string) => string;
  /** Resolves to the success message, or null if the admin cancelled. */
  onSubmit: (value: string) => Promise<string | null>;
}) {
  const [value, setValue] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const edit = (setter: (v: string) => void) => (v: string) => {
    setter(v);
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validate(value) || (value.trim() !== confirm.trim() ? `The two ${label.toLowerCase()} entries do not match` : '');
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const message = await onSubmit(value.trim());
      if (message !== null) {
        setSuccess(message);
        setValue('');
        setConfirm('');
      }
    } catch (err) {
      setError(parseErrorMessage(err) || `Failed: ${title}. Please try again.`);
    } finally {
      setBusy(false);
    }
  };

  const id = title.toLowerCase().replace(/\s+/g, '-');
  return (
    <form onSubmit={handleSubmit} className="card form-stack" style={{ ...cardStyle, flex: '1 1 320px' }}>
      <h3 style={{ margin: '0 0 6px 0', color: '#eaf5ff' }}>{title}</h3>
      <p style={{ margin: '0 0 16px 0', color: '#b4cce2', fontSize: '13px' }}>{description}</p>
      {current && (
        <div style={{
          margin: '0 0 16px 0',
          padding: '10px 14px',
          borderRadius: '8px',
          borderLeft: '4px solid #f0a020',
          backgroundColor: 'rgba(240, 160, 32, 0.12)'
        }}>
          <div style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.6px', textTransform: 'uppercase', color: '#f0a020', marginBottom: '4px' }}>
            {current.label}
          </div>
          <div style={{ fontSize: '15px', fontWeight: '600', color: '#ffd28a', wordBreak: 'break-all' }}>{current.value}</div>
        </div>
      )}
      {error && <div style={messageStyle('error')}>{error}</div>}
      {success && <div style={messageStyle('success')}>{success}</div>}
      {inputType === 'email' ? (
        <>
          <LabeledField id={`${id}-new`} label={label} helpText={helpText} value={value} onChange={edit(setValue)} required={true}>
            <NewEmailInput id={`${id}-new`} value={value} onChange={edit(setValue)} placeholder={placeholder} />
          </LabeledField>
          <LabeledField id={`${id}-confirm`} label={`Confirm ${label}`} helpText={`Re-enter the ${label.toLowerCase()} to confirm`} value={confirm} onChange={edit(setConfirm)} required={true}>
            <NewEmailInput id={`${id}-confirm`} value={confirm} onChange={edit(setConfirm)} placeholder={placeholder} />
          </LabeledField>
        </>
      ) : (
        <>
          <LabeledField id={`${id}-new`} label={label} helpText={helpText} value={value} onChange={edit(setValue)} type={inputType} placeholder={placeholder} required={true} autoComplete="new-password" />
          <LabeledField id={`${id}-confirm`} label={`Confirm ${label}`} helpText={`Re-enter the ${label.toLowerCase()} to confirm`} value={confirm} onChange={edit(setConfirm)} type={inputType} placeholder={placeholder} required={true} autoComplete="new-password" />
        </>
      )}
      <button type="submit" disabled={busy} style={submitStyle(busy)}>{busy ? busyLabel : submitLabel}</button>
    </form>
  );
}

export function AdminResetPasswordPage({ auth }: AdminResetPasswordPageProps) {
  const token: string = auth.session.accessToken;
  const [results, setResults] = useState<AdminUserSearchRow[] | null>(null);
  const [selected, setSelected] = useState<AdminUserSearchRow | null>(null);

  const showResults = (rows: AdminUserSearchRow[] | null) => {
    setResults(rows);
    setSelected(null);
  };

  const changeEmail = async (newEmail: string) => {
    if (!selected) return null;
    if (!window.confirm(`Change ${selected.name}'s login email from ${selected.email} to ${newEmail}? They must sign in with the new email from now on.`)) {
      return null;
    }
    const result = await api.adminChangeEmailById(token, selected.user_id, newEmail);
    const updated = { ...selected, email: result.new_email };
    setSelected(updated);
    setResults(prev => prev?.map(r => (r.user_id === updated.user_id ? updated : r)) ?? prev);
    return `Email changed from ${result.old_email} to ${result.new_email}`;
  };

  const resetPassword = async (newPassword: string) => {
    if (!selected) return null;
    const result = await api.adminResetPasswordById(token, selected.user_id, newPassword);
    return `Password reset for ${selected.name} (${result.user_email})`;
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1100px', margin: '0 auto', width: '100%' }}>
      <h2 style={{ color: '#eef8ff', margin: 0, fontSize: '24px', fontWeight: '600' }}>Reset Password / Change Email</h2>
      <p style={{ color: '#b4cce2', margin: 0, fontSize: '14px', lineHeight: '1.5' }}>
        Select a role and search by name, email or phone number. Click a name to change that person's login email or reset their password.
      </p>

      <AdminUserSearch
        accessToken={token}
        results={results}
        onResults={showResults}
        onPick={setSelected}
        selectedId={selected?.user_id}
        resultsHint="Click a name to manage that account."
      />

      {/* Actions for the picked user */}
      {selected && (
        <>
          <div className="card" style={cardStyle}>
            <h3 style={{ margin: '0 0 12px 0', color: '#eaf5ff' }}>Selected Account</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', color: '#e8f6ff', fontSize: '14px' }}>
              <div><strong>Name:</strong> {selected.name}</div>
              <div><strong>Role:</strong> {ROLE_LABELS[selected.role] ?? selected.role}</div>
              <div><strong>Email:</strong> {selected.email}</div>
              <div><strong>Phone:</strong> {dash(selected.phone)}</div>
            </div>
          </div>

          <div key={selected.user_id} style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
            <ConfirmedValueForm
              title="Change Email"
              description="Type the new email in both boxes. The user signs in with it from now on; their password stays the same."
              current={{ label: 'Current (old) email', value: selected.email }}
              label="New Email"
              helpText="Must not be used by any other account"
              inputType="email"
              placeholder="new.email@example.com"
              submitLabel="Change Email"
              busyLabel="Changing Email..."
              validate={(v) =>
                !EMAIL_REGEX.test(v.trim()) ? 'Please enter a valid email address'
                  : v.trim().toLowerCase() === selected.email.toLowerCase() ? `The new email (${v.trim()}) is the same as the current one (${selected.email})`
                  : ''}
              onSubmit={changeEmail}
            />
            <ConfirmedValueForm
              title="Reset Password"
              description="Type the new password in both boxes. The user signs in with it from their next login."
              label="New Password"
              helpText="Minimum 8 characters"
              inputType="password"
              placeholder="Enter new password"
              submitLabel="Reset Password"
              busyLabel="Resetting Password..."
              validate={(v) => (v.length < MIN_PASSWORD_LENGTH ? `Password must be at least ${MIN_PASSWORD_LENGTH} characters long` : '')}
              onSubmit={resetPassword}
            />
          </div>
        </>
      )}

      <div style={{ padding: '16px', backgroundColor: 'rgba(255, 255, 255, 0.05)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <h4 style={{ color: '#eef8ff', margin: '0 0 12px 0', fontSize: '14px', fontWeight: '500' }}>Important Notes:</h4>
        <ul style={{ color: '#b4cce2', fontSize: '13px', lineHeight: '1.6', margin: 0, paddingLeft: '20px' }}>
          <li>Changes apply to the account you clicked, identified by its unique id</li>
          <li>Passwords must be at least 8 characters long</li>
          <li>An email already used by another account can't be assigned</li>
          <li>Changing the email keeps the password, and resetting the password keeps the email</li>
        </ul>
      </div>
    </section>
  );
}
