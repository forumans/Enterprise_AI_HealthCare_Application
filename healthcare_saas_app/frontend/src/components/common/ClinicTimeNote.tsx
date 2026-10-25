/**
 * Clinic Time Note
 * "All times are clinic time: PDT (America/Los Angeles)" - shown under the heading of every calendar, so
 * patients, doctors and support staff in any time zone know which zone the times are in.
 */

import React from "react";
import { useClinicTimeZone } from "../../contexts/ClinicTimeZoneContext";
import { clinicTimeNote } from "../../utils";

export function ClinicTimeNote({ style }: { style?: React.CSSProperties }) {
  const timeZone = useClinicTimeZone();
  return (
    <div data-testid="clinic-time-note" style={{ fontSize: '12px', fontWeight: '400', color: '#b4cce2', marginTop: '4px', ...style }}>
      {clinicTimeNote(timeZone)}
    </div>
  );
}
