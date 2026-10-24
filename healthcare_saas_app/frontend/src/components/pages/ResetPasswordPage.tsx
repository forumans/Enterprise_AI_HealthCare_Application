/**
 * Reset Password Page Component
 * Opened from the link in a password reset email (/reset-password?token=...); sets a new password.
 */

import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import { parseErrorMessage } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";

const MIN_PASSWORD_LENGTH = 8;

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [doneMessage, setDoneMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters long.`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await api.resetPassword(token, password);
      setDoneMessage(result.message);
    } catch (err) {
      setError(parseErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <h2>Choose a New Password</h2>

      {!token ? (
        <>
          <StatusMessage message="This page needs the link from your password reset email." type="error" />
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <Link to="/forgot-password" style={{ color: '#42b5f5' }}>Request a new reset link</Link>
          </div>
        </>
      ) : doneMessage ? (
        <>
          <StatusMessage message={doneMessage} type="success" />
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <Link to="/" style={{ color: '#42b5f5' }}>Go to sign in</Link>
          </div>
        </>
      ) : (
        <>
          <p style={{ color: '#b4cce2', marginBottom: '24px' }}>Type your new password in both boxes.</p>
          {error && <StatusMessage message={error} type="error" />}
          <form onSubmit={handleSubmit} className="form-stack">
            <LabeledField
              id="reset-new-password"
              label="New Password"
              helpText={`Minimum ${MIN_PASSWORD_LENGTH} characters`}
              value={password}
              onChange={(value) => { setPassword(value); setError(""); }}
              type="password"
              autoComplete="new-password"
            />
            <LabeledField
              id="reset-confirm-password"
              label="Confirm New Password"
              helpText="Re-enter the new password"
              value={confirm}
              onChange={(value) => { setConfirm(value); setError(""); }}
              type="password"
              autoComplete="new-password"
            />
            <button type="submit" className="button-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Set New Password'}
            </button>
          </form>
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <Link to="/forgot-password" style={{ color: '#42b5f5' }}>Link expired? Request a new one</Link>
          </div>
        </>
      )}
    </section>
  );
}
