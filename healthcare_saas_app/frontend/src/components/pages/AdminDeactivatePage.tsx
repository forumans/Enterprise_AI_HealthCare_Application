/**
 * Admin Deactivate Page Component
 * Admin picks a role, searches by name, email or phone, and deactivates (red) or re-activates (green)
 * accounts. Deactivated accounts can't log in. The server refuses deactivating your own account or
 * the last active admin.
 */

import React, { useState } from 'react';
import { api } from '../../api';
import { parseErrorMessage } from '../../utils';
import type { AdminUserSearchRow } from '../../types';
import { AdminUserSearch } from '../common/AdminUserSearch';

interface AdminDeactivatePageProps {
  auth: any;
}

/** Order of the role drop-down on this screen. */
const ROLE_ORDER = ['SUPPORT_STAFF', 'DOCTOR', 'PATIENT', 'ADMIN'];

const actionButton = (color: string, busy: boolean): React.CSSProperties => ({
  background: busy ? '#94a3b8' : color,
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  padding: '6px 14px',
  fontSize: '13px',
  fontWeight: '500',
  cursor: busy ? 'not-allowed' : 'pointer',
  whiteSpace: 'nowrap'
});

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: '999px',
      fontSize: '12px',
      fontWeight: '600',
      whiteSpace: 'nowrap',
      color: active ? '#49d7c2' : '#ff90ab',
      backgroundColor: active ? 'rgba(73, 215, 194, 0.15)' : 'rgba(255, 144, 171, 0.15)'
    }}>
      {active ? 'Active' : 'Deactivated'}
    </span>
  );
}

export function AdminDeactivatePage({ auth }: AdminDeactivatePageProps) {
  const token: string = auth.session.accessToken;
  const [results, setResults] = useState<AdminUserSearchRow[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  const showResults = (rows: AdminUserSearchRow[] | null) => {
    setResults(rows);
    setMessage(null);
  };

  const toggle = async (row: AdminUserSearchRow) => {
    const activating = !row.is_active;
    const question = activating
      ? `Activate ${row.name} (${row.email})? They will be able to log in again.`
      : `Deactivate ${row.name} (${row.email})? They will no longer be able to log in.`;
    if (!window.confirm(question)) return;

    setBusyId(row.user_id);
    setMessage(null);
    try {
      await api.adminSetUserActive(token, row.user_id, activating);
      setResults(prev => prev?.map(r => (r.user_id === row.user_id ? { ...r, is_active: activating } : r)) ?? prev);
      setMessage({ kind: 'success', text: `${row.name} has been ${activating ? 'activated' : 'deactivated'}.` });
    } catch (err) {
      console.error('Account status change failed:', err);
      setMessage({ kind: 'error', text: parseErrorMessage(err) });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1100px', margin: '0 auto', width: '100%' }}>
      <h2 style={{ color: '#eef8ff', margin: 0, fontSize: '24px', fontWeight: '600' }}>Deactivate / Activate Accounts</h2>
      <p style={{ color: '#b4cce2', margin: 0, fontSize: '14px', lineHeight: '1.5' }}>
        Select a role and search by name, email or phone number. Deactivated accounts can't log in until they are activated again.
      </p>

      {message && (
        <div style={{
          padding: '12px 16px',
          borderRadius: '8px',
          fontSize: '14px',
          color: message.kind === 'error' ? '#ff90ab' : '#49d7c2',
          backgroundColor: message.kind === 'error' ? 'rgba(255, 144, 171, 0.1)' : 'rgba(73, 215, 194, 0.1)',
          border: `1px solid ${message.kind === 'error' ? 'rgba(255, 144, 171, 0.3)' : 'rgba(73, 215, 194, 0.3)'}`
        }}>
          {message.text}
        </div>
      )}

      <AdminUserSearch
        accessToken={token}
        results={results}
        onResults={showResults}
        roleOrder={ROLE_ORDER}
        extraColumns={[
          { header: 'Status', render: (row) => <StatusBadge active={row.is_active} /> },
          {
            header: 'Action',
            render: (row) =>
              row.is_self ? (
                <span style={{ color: '#94a3b8', fontSize: '13px', whiteSpace: 'nowrap' }}>Your account</span>
              ) : (
                <button
                  type="button"
                  onClick={() => toggle(row)}
                  disabled={busyId === row.user_id}
                  style={actionButton(row.is_active ? '#dc3545' : '#28a745', busyId === row.user_id)}
                >
                  {busyId === row.user_id ? 'Saving...' : row.is_active ? 'Deactivate' : 'Activate'}
                </button>
              ),
          },
        ]}
      />

      <div style={{ padding: '16px', backgroundColor: 'rgba(255, 255, 255, 0.05)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <h4 style={{ color: '#eef8ff', margin: '0 0 12px 0', fontSize: '14px', fontWeight: '500' }}>Important Notes:</h4>
        <ul style={{ color: '#b4cce2', fontSize: '13px', lineHeight: '1.6', margin: 0, paddingLeft: '20px' }}>
          <li>Deactivated users can't log in; their records and appointments are kept</li>
          <li>You can't deactivate your own account</li>
          <li>At least one admin account must always stay active</li>
          <li>Someone already signed in is signed out on their next action</li>
        </ul>
      </div>
    </section>
  );
}
