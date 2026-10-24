/**
 * Forgot Password Page Component
 * Asks for the account email and requests a password reset link by email.
 * The reply is the same whether or not the email is registered.
 */

import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { parseErrorMessage, validateEmail } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sentMessage, setSentMessage] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!validateEmail(email.trim())) {
      setError("Please enter a valid email address.");
      return;
    }
    setSending(true);
    setError("");
    try {
      const result = await api.forgotPassword(email.trim());
      setSentMessage(result.message);
    } catch (err) {
      setError(parseErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <section>
      <h2>Forgot Password</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Enter the email you sign in with and we'll send you a link to choose a new password.
      </p>

      {sentMessage ? (
        <StatusMessage message={sentMessage} type="success" />
      ) : (
        <form onSubmit={handleSubmit} className="form-stack">
          <LabeledField
            id="forgot-email"
            label="Email"
            helpText="The email address you use to sign in"
            value={email}
            onChange={(value) => { setEmail(value); setError(""); }}
            type="email"
            placeholder="your.email@example.com"
            error={error}
            autoComplete="email"
          />
          <button type="submit" className="button-primary" disabled={sending || !email}>
            {sending ? 'Sending...' : 'Send Reset Link'}
          </button>
        </form>
      )}

      <div style={{ marginTop: '24px', textAlign: 'center' }}>
        <Link to="/" style={{ color: '#42b5f5' }}>Back to Home</Link>
      </div>
    </section>
  );
}
