/**
 * Admin Setup Page Component
 * First-time setup (/admin/setup): creates the very first administrator of a new deployment.
 * Once any administrator exists the server refuses, and this page says so instead of showing the form.
 */

import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { browserTimeZone, parseErrorMessage, supportedTimeZones, validateEmail } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";

const MIN_PASSWORD_LENGTH = 8;

export function AdminSetupPage() {
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  // The clinic's time zone; the person setting up is most likely at the clinic
  const [timezone, setTimezone] = useState(browserTimeZone);
  const [error, setError] = useState("");
  const [doneMessage, setDoneMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getAdminSetupStatus()
      .then(result => setSetupRequired(result.setup_required))
      .catch(() => setSetupRequired(false));
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const problem =
      fullName.trim().length < 3 ? "Name must be at least 3 characters." :
      !validateEmail(email.trim()) ? "Please provide a valid email address." :
      password.length < MIN_PASSWORD_LENGTH ? `Password must be at least ${MIN_PASSWORD_LENGTH} characters long.` :
      password !== confirm ? "The two passwords do not match." : "";
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await api.bootstrapAdmin({ full_name: fullName.trim(), email: email.trim(), password, timezone });
      setDoneMessage(result.message);
    } catch (err) {
      setError(parseErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const edit = (setter: (value: string) => void) => (value: string) => { setter(value); setError(""); };

  return (
    <section>
      <h2>First-Time Setup</h2>

      {setupRequired === null ? (
        <p style={{ color: '#b4cce2' }}>Checking setup status...</p>
      ) : doneMessage ? (
        <>
          <StatusMessage message={doneMessage} type="success" />
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <Link to="/admin/login" style={{ color: '#42b5f5' }}>Go to Admin Login</Link>
          </div>
        </>
      ) : !setupRequired ? (
        <>
          <StatusMessage message="This system is already set up. Administrator accounts are created by an existing administrator." type="error" />
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <Link to="/admin/login" style={{ color: '#42b5f5' }}>Go to Admin Login</Link>
          </div>
        </>
      ) : (
        <>
          <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
            Create the first administrator account. This page works only until an administrator exists.
          </p>
          {error && <StatusMessage message={error} type="error" />}
          <form onSubmit={handleSubmit} className="form-stack">
            <LabeledField id="setup-name" label="Full Name" helpText="Name must be 3-80 characters." value={fullName} onChange={edit(setFullName)} required={true} />
            <LabeledField id="setup-email" label="Email" helpText="Use a valid email format, e.g., name@example.com." value={email} onChange={edit(setEmail)} type="email" autoComplete="email" required={true} />
            <LabeledField id="setup-password" label="Password" helpText={`Minimum ${MIN_PASSWORD_LENGTH} characters`} value={password} onChange={edit(setPassword)} type="password" autoComplete="new-password" required={true} />
            <LabeledField id="setup-confirm" label="Confirm Password" helpText="Re-enter the password" value={confirm} onChange={edit(setConfirm)} type="password" autoComplete="new-password" required={true} />
            <div>
              <label htmlFor="setup-timezone" style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '6px' }}>Clinic Time Zone</label>
              <select
                id="setup-timezone"
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
                style={{ width: '100%', padding: '11px 12px', borderRadius: '10px', border: '1px solid rgba(136, 194, 227, 0.36)', fontSize: '14px', backgroundColor: 'rgba(9, 35, 55, 0.82)', color: '#eef8ff' }}
              >
                {supportedTimeZones(timezone).map(name => <option key={name} value={name}>{name.replace(/_/g, ' ')}</option>)}
              </select>
              <p style={{ color: '#b4cce2', fontSize: '12px', margin: '6px 0 0 0' }}>Office hours and every time in the app use this zone. Admins can change it later under Clinic Settings.</p>
            </div>
            <button type="submit" className="button-primary" disabled={saving}>
              {saving ? 'Creating...' : 'Create Administrator'}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
