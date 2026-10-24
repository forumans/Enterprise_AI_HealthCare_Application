/**
 * Admin User Search
 * Role drop-down + search box (name, email or phone; "*" for everyone) + numbered results table.
 * Shared by the admin Reset Password / Email and Deactivate screens; the page owns the results
 * so it can update rows after acting on them.
 */

import React, { useEffect, useState } from 'react';
import { api } from '../../api';
import { parseErrorMessage, searchQueryProblem } from '../../utils';
import type { AdminUserSearchRow } from '../../types';
import { formatIsoDate } from './SupportSearchPanel';

interface RoleOption {
  value: string;
  label: string;
}

export interface AdminUserColumn {
  header: string;
  render: (row: AdminUserSearchRow) => React.ReactNode;
}

interface AdminUserSearchProps {
  accessToken: string;
  results: AdminUserSearchRow[] | null;
  onResults: (rows: AdminUserSearchRow[] | null) => void;
  /** Role values in the order to list them; defaults to the server's order. */
  roleOrder?: string[];
  /** When given, full names are links that pick the row. */
  onPick?: (row: AdminUserSearchRow) => void;
  /** Row to highlight. */
  selectedId?: string;
  /** Columns appended after the standard ones (e.g. status and an action button). */
  extraColumns?: AdminUserColumn[];
  /** Line shown above the results, after the count. */
  resultsHint?: string;
}

const labelStyle: React.CSSProperties = { display: 'block', color: '#eef8ff', marginBottom: '8px', fontSize: '14px', fontWeight: '500' };
const fieldStyle: React.CSSProperties = {
  width: '100%',
  padding: '12px',
  borderRadius: '8px',
  border: '1px solid rgba(255, 255, 255, 0.2)',
  backgroundColor: 'rgba(9, 35, 55, 0.82)',
  color: '#eef8ff',
  fontSize: '14px',
  fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
};
export const adminCellStyle: React.CSSProperties = { padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)', verticalAlign: 'top' };
const headStyle: React.CSSProperties = { padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };

const dash = (value: string) => value || '—';

/** DOB for patients, specialty for doctors. */
const detailsFor = (row: AdminUserSearchRow) =>
  [row.specialty, row.date_of_birth ? `DOB ${formatIsoDate(row.date_of_birth)}` : ''].filter(Boolean).join(' · ') || '—';

export function AdminUserSearch({ accessToken, results, onResults, roleOrder, onPick, selectedId, extraColumns = [], resultsHint }: AdminUserSearchProps) {
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [role, setRole] = useState('');
  const [query, setQuery] = useState('');
  const [lastQuery, setLastQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getResetPasswordRoles(accessToken)
      .then((rows) => {
        const rank = (value: string) => (roleOrder ? roleOrder.indexOf(value) : 0);
        setRoles(roleOrder ? rows.filter(r => roleOrder.includes(r.value)).sort((a, b) => rank(a.value) - rank(b.value)) : rows);
      })
      .catch((err) => {
        console.error('Failed to load roles:', err);
        setError('Failed to load roles');
      });
  }, [accessToken]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!role) {
      setError('Please select a role');
      return;
    }
    const problem = searchQueryProblem(query, 'a name, email or phone number');
    if (problem) {
      setError(problem);
      return;
    }
    setSearching(true);
    setError('');
    try {
      onResults(await api.adminSearchUsers(accessToken, role, query.trim()));
      setLastQuery(query.trim());
    } catch (err) {
      console.error('User search failed:', err);
      setError(parseErrorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  const roleLabel = roles.find(r => r.value === role)?.label ?? 'users';

  return (
    <form onSubmit={handleSearch} className="card" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ flex: '0 1 220px' }}>
          <label htmlFor="account-role" style={labelStyle}>Role <span style={{ color: '#ff90ab', marginLeft: '4px' }}>*</span></label>
          <select
            id="account-role"
            value={role}
            onChange={(e) => { setRole(e.target.value); onResults(null); setError(''); }}
            style={fieldStyle}
          >
            <option value="">Select a role</option>
            {roles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <div style={{ flex: '1 1 300px' }}>
          <label htmlFor="account-search" style={labelStyle}>Search</label>
          <input
            id="account-search"
            type="search"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setError(''); }}
            placeholder="Name, email or phone number, or * for everyone"
            autoComplete="off"
            style={fieldStyle}
          />
        </div>
        <button
          type="submit"
          disabled={searching}
          style={{
            padding: '12px 28px',
            borderRadius: '8px',
            border: 'none',
            background: searching ? '#6b7280' : '#42b5f5',
            color: '#ffffff',
            fontSize: '15px',
            fontWeight: '500',
            cursor: searching ? 'not-allowed' : 'pointer'
          }}
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
      </div>
      {error && (
        <div style={{ marginTop: '12px', padding: '12px 16px', borderRadius: '8px', backgroundColor: 'rgba(255, 144, 171, 0.1)', border: '1px solid rgba(255, 144, 171, 0.3)', color: '#ff90ab', fontSize: '14px' }}>
          {error}
        </div>
      )}

      {results && (
        <div style={{ marginTop: '16px' }}>
          {results.length === 0 ? (
            <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px', margin: 0 }}>
              {lastQuery === '*' ? `No ${roleLabel.toLowerCase()} found` : `No ${roleLabel.toLowerCase()} match "${lastQuery}"`}
            </p>
          ) : (
            <>
              <p style={{ color: '#b4cce2', fontSize: '13px', margin: '0 0 8px 0' }}>
                {results.length} found.{resultsHint ? ` ${resultsHint}` : ''}
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                      <th style={{ ...headStyle, textAlign: 'right', width: '1%', whiteSpace: 'nowrap' }}>#</th>
                      {['Full Name', 'Email', 'Phone', 'Address', 'Details', ...extraColumns.map(c => c.header)].map(h => <th key={h} style={headStyle}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((row, index) => (
                      <tr key={row.user_id} style={{ backgroundColor: row.user_id === selectedId ? 'rgba(66, 181, 245, 0.18)' : 'rgba(9, 32, 52, 0.82)' }}>
                        <td style={{ ...adminCellStyle, textAlign: 'right', color: '#b4cce2' }}>{index + 1}</td>
                        <td style={adminCellStyle}>
                          {onPick ? (
                            <button
                              type="button"
                              onClick={() => onPick(row)}
                              style={{ background: 'none', border: 'none', padding: 0, color: '#42b5f5', textDecoration: 'underline', cursor: 'pointer', fontSize: '14px', fontWeight: '500', textAlign: 'left' }}
                            >
                              {row.name}
                            </button>
                          ) : (
                            row.name
                          )}
                        </td>
                        <td style={adminCellStyle}>{row.email}</td>
                        <td style={adminCellStyle}>{dash(row.phone)}</td>
                        <td style={adminCellStyle}>{dash(row.address)}</td>
                        <td style={adminCellStyle}>{detailsFor(row)}</td>
                        {extraColumns.map(c => <td key={c.header} style={adminCellStyle}>{c.render(row)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </form>
  );
}
