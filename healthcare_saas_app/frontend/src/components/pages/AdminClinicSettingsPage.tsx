/**
 * Admin Clinic Settings Page Component
 * Lets an admin set their clinic's time zone. Office hours (8 AM - 11 PM), "today", weeks and every time
 * shown in the app follow it. Changing it keeps doctors' open and blocked slots at the same local hours;
 * booked appointments keep their exact time.
 */

import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { browserTimeZone, formatInZone, parseErrorMessage, supportedTimeZones, timeZoneAbbreviation } from "../../utils";
import { StatusMessage } from "../common/StatusMessage";

interface AdminClinicSettingsPageProps {
  auth: any;
}

const labelStyle: React.CSSProperties = { fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '6px' };
const selectStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: '420px',
  padding: '11px 12px',
  borderRadius: '10px',
  border: '1px solid rgba(136, 194, 227, 0.36)',
  fontSize: '14px',
  backgroundColor: 'rgba(9, 35, 55, 0.82)',
  color: '#eef8ff'
};
const noteStyle: React.CSSProperties = { color: '#b4cce2', fontSize: '13px', margin: '8px 0 0 0' };

/** "Thu, Oct 22, 9:41 AM PDT" - the current time in a zone. */
const nowIn = (timeZone: string) =>
  formatInZone(new Date(), timeZone, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });

export function AdminClinicSettingsPage({ auth }: AdminClinicSettingsPageProps) {
  const token: string = auth.session.accessToken;
  const [clinicName, setClinicName] = useState("");
  const [savedZone, setSavedZone] = useState("");
  const [zone, setZone] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api.getCurrentTenant(token)
      .then(tenant => {
        setClinicName(tenant.name);
        setSavedZone(tenant.timezone);
        setZone(tenant.timezone);
      })
      .catch(err => setError(parseErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!zone || zone === savedZone) return;
    if (!window.confirm(
      `Change the clinic's time zone from ${savedZone} to ${zone}?\n\n` +
      "Doctors' open and blocked slots keep their local hours (a 9 AM slot stays 9 AM). " +
      "Booked appointments keep their exact time, so they will show at a different local hour."
    )) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.updateCurrentTenant(token, { timezone: zone });
      setSavedZone(result.timezone);
      // Every screen shows times in the clinic's zone: switch this session over straight away
      auth.setSession((prev: any) => ({ ...prev, clinicTimezone: result.timezone }));
      setSuccess(`Clinic time zone set to ${result.timezone}. ${result.slots_moved} upcoming slot(s) kept their local hours.`);
    } catch (err) {
      setError(parseErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const browserZone = browserTimeZone();
  const zones = supportedTimeZones(savedZone || browserZone);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Clinic Settings</h2>
      {error && <StatusMessage message={error} type="error" />}
      {success && <StatusMessage message={success} type="success" />}

      {loading ? (
        <p style={{ color: '#b4cce2' }}>Loading clinic settings...</p>
      ) : savedZone && (
        <div className="card" style={{ padding: '20px' }}>
          <h3 style={{ margin: '0 0 6px 0', color: '#eaf5ff' }}>{clinicName}</h3>
          <p style={{ ...noteStyle, marginBottom: '20px' }}>
            Office hours (8 AM - 11 PM), today's and weekly schedules, and every time in the app use the clinic's time zone,
            whatever time zone a patient or staff member is in.
          </p>

          <form onSubmit={handleSave}>
            <label htmlFor="clinic-timezone" style={labelStyle}>Clinic Time Zone</label>
            <select id="clinic-timezone" value={zone} onChange={e => { setZone(e.target.value); setSuccess(""); }} style={selectStyle} disabled={saving}>
              {zones.map(name => (
                <option key={name} value={name}>{name.replace(/_/g, ' ')}</option>
              ))}
            </select>
            <p style={noteStyle}>
              Clinic time now: {nowIn(zone)} ({timeZoneAbbreviation(zone)})
            </p>
            {browserZone !== zone && (
              <p style={noteStyle}>
                Your computer is set to {browserZone.replace(/_/g, ' ')}.{' '}
                <button type="button" onClick={() => setZone(browserZone)} disabled={saving} style={{ background: 'none', border: 'none', padding: 0, color: '#42b5f5', textDecoration: 'underline', cursor: 'pointer', fontSize: '13px' }}>
                  Use it
                </button>
              </p>
            )}
            {zone !== savedZone && (
              <p style={{ ...noteStyle, color: '#f0c674' }}>
                Doctors' open and blocked slots will keep their local hours. Booked appointments keep their exact time, so they
                will show at a different local hour; reschedule any that no longer suit.
              </p>
            )}
            <button type="submit" className="button-primary" disabled={saving || zone === savedZone} style={{ marginTop: '16px' }}>
              {saving ? 'Saving...' : 'Save Time Zone'}
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
