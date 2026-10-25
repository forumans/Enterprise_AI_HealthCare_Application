/**
 * Support Search Panel
 * Search box + results table for support staff to find a patient or a doctor by name, email or phone.
 * Clicking a full name picks that person. Used by the support staff appointment and availability screens.
 */

import React, { useState } from "react";
import { api } from "../../api";
import { parseErrorMessage, searchQueryProblem } from "../../utils";
import type { SupportDoctorRow, SupportPatientRow } from "../../types";

type SearchProps =
  | { kind: "patient"; onPick: (row: SupportPatientRow) => void }
  | { kind: "doctor"; onPick: (row: SupportDoctorRow) => void };

type SupportSearchPanelProps = SearchProps & {
  accessToken: string;
  /** Id of the person currently picked; their row is highlighted. */
  selectedId?: string;
  /** Render without the card frame, for use inside another card. */
  embedded?: boolean;
};

const cellStyle: React.CSSProperties = { padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const headStyle: React.CSSProperties = { padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: '11px 12px',
  borderRadius: '10px',
  border: '1px solid rgba(136, 194, 227, 0.36)',
  fontSize: '14px',
  backgroundColor: 'rgba(9, 35, 55, 0.82)',
  color: '#eef8ff'
};

/** "1985-03-07" -> "03/07/1985" without a Date round-trip (which would shift by the time zone). */
export const formatIsoDate = (value: string) => {
  const [year, month, day] = value.split('-');
  return year && month && day ? `${month}/${day}/${year}` : '—';
};

const dash = (value: string) => value || '—';

const COLUMNS = {
  patient: {
    headers: ["Phone", "Email", "Date of Birth", "Gender", "Insurance", "City / State"],
    cells: (p: SupportPatientRow) => [dash(p.phone), dash(p.email), formatIsoDate(p.date_of_birth), dash(p.gender), dash(p.insurance_provider), dash([p.city, p.state].filter(Boolean).join(', '))],
  },
  doctor: {
    headers: ["Phone", "Email", "Specialty", "License Number"],
    cells: (d: SupportDoctorRow) => [dash(d.phone), dash(d.email), d.specialty || 'General Practice', dash(d.license_number)],
  },
};

export function SupportSearchPanel(props: SupportSearchPanelProps) {
  const { kind, accessToken, selectedId, embedded } = props;
  const [searchText, setSearchText] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [results, setResults] = useState<Array<SupportPatientRow | SupportDoctorRow> | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  const noun = kind === "patient" ? "patient" : "doctor";

  const handleSearch = async (event: React.FormEvent) => {
    event.preventDefault();
    const q = searchText.trim();
    const problem = searchQueryProblem(q, "a name, email or phone number");
    if (problem) {
      setError(problem);
      return;
    }
    setSearching(true);
    setError("");
    try {
      setResults(kind === "patient" ? await api.supportSearchPatients(accessToken, q) : await api.supportSearchDoctors(accessToken, q));
      setLastQuery(q);
    } catch (err) {
      console.error(`${noun} search failed:`, err);
      setError(parseErrorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  const pick = (row: SupportPatientRow | SupportDoctorRow) => {
    if (props.kind === "patient") props.onPick(row as SupportPatientRow);
    else props.onPick(row as SupportDoctorRow);
  };

  const columns = COLUMNS[kind];
  const cellsFor = (row: SupportPatientRow | SupportDoctorRow) =>
    kind === "patient" ? COLUMNS.patient.cells(row as SupportPatientRow) : COLUMNS.doctor.cells(row as SupportDoctorRow);

  return (
    <div className={embedded ? undefined : "card"} style={embedded ? undefined : { padding: '16px' }}>
      <form onSubmit={handleSearch}>
        <label htmlFor={`support-${noun}-search`} style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>
          Find {kind === "patient" ? "Patient" : "Doctor"}
        </label>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <input
            id={`support-${noun}-search`}
            type="search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Enter a name, email or phone number, or * for everyone"
            autoComplete="off"
            style={inputStyle}
          />
          <button
            type="submit"
            disabled={searching}
            style={{
              background: searching ? '#94a3b8' : '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '10px',
              padding: '11px 20px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: searching ? 'not-allowed' : 'pointer'
            }}
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>
      {error && <div style={{ color: '#ff90ab', fontSize: '12px', marginTop: '6px' }}>{error}</div>}

      {results && (
        <div style={{ marginTop: '16px' }}>
          {results.length === 0 ? (
            <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px', margin: 0 }}>{lastQuery === "*" ? `No ${noun}s found` : `No ${noun}s match "${lastQuery}"`}</p>
          ) : (
            <>
              <p style={{ color: '#b4cce2', fontSize: '13px', margin: '0 0 8px 0' }}>
                {results.length} {noun}{results.length === 1 ? '' : 's'} found. Click a name to continue.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                      <th style={{ ...headStyle, textAlign: 'right', width: '1%', whiteSpace: 'nowrap' }}>#</th>
                      <th style={headStyle}>Full Name</th>
                      {columns.headers.map(h => <th key={h} style={headStyle}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((row, index) => (
                      <tr key={row.id} style={{ backgroundColor: row.id === selectedId ? 'rgba(66, 181, 245, 0.18)' : 'rgba(9, 32, 52, 0.82)' }}>
                        <td style={{ ...cellStyle, textAlign: 'right', color: '#b4cce2' }}>{index + 1}</td>
                        <td style={cellStyle}>
                          <button
                            type="button"
                            onClick={() => pick(row)}
                            style={{ background: 'none', border: 'none', padding: 0, color: '#42b5f5', textDecoration: 'underline', cursor: 'pointer', fontSize: '14px', fontWeight: '500', textAlign: 'left' }}
                          >
                            {row.name}
                          </button>
                          {kind === "doctor" && (row as SupportDoctorRow).is_active === false && (
                            <span style={{ marginLeft: '8px', color: '#94a3b8', fontSize: '12px' }}>(inactive)</span>
                          )}
                        </td>
                        {cellsFor(row).map((value, i) => <td key={columns.headers[i]} style={cellStyle}>{value}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
