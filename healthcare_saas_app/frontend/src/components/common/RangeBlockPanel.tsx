/**
 * Range Block Panel
 * The "Block or Unblock a Time Range" card, its preview/confirm dialog and the "Active Blocks" list on
 * Manage Availability (doctors) and Doctor Availability (support staff, on the doctor's behalf).
 * Dates and hours are chosen in clinic time and sent as UTC; the range is half-open [from, to).
 */

import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { useClinicTimeZone } from "../../contexts/ClinicTimeZoneContext";
import type { BlockReasonCategory, RangePreview, ScheduleBlockRow } from "../../types";
import {
  WORKDAY_FIRST_SLOT_HOUR, WORKDAY_LAST_SLOT_HOUR, addDays, clinicToday, dayKey, formatInZone, parseErrorMessage, zonedTimeToDate,
  type CalendarDay,
} from "../../utils";
import { ClinicTimeNote } from "./ClinicTimeNote";

/** Range actions may reach this far ahead (single-slot changes and booking: 30 days). */
export const RANGE_HORIZON_DAYS = 180;
export const SCHEDULE_CHANGED = "The schedule changed. Review the changes again.";

export const REASON_CATEGORIES: Array<{ value: BlockReasonCategory; label: string }> = [
  { value: "VACATION", label: "Vacation" },
  { value: "CONFERENCE", label: "Conference" },
  { value: "SICK", label: "Sick" },
  { value: "PERSONAL", label: "Personal" },
  { value: "ADMINISTRATIVE", label: "Administrative" },
  { value: "OTHER", label: "Other" },
];

const STATE_LABELS: Record<ScheduleBlockRow["state"], string> = {
  ACTIVE: "Active",
  PARTIALLY_RELEASED: "Partially released",
  RELEASED: "Released",
};

export interface RangeForm {
  mode: "block" | "unblock";
  fromDate: string; // YYYY-MM-DD, clinic calendar
  fromHour: number;
  toDate: string;
  toHour: number; // 24 = midnight at the end of toDate
  allDay: boolean;
  category: BlockReasonCategory | "";
  note: string;
}

/** "9:00 AM" for 9, "12:00 AM (end of day)" for 24. */
export function hourLabel(hour: number): string {
  if (hour === 24) return "12:00 AM (end of day)";
  const suffix = hour < 12 ? "AM" : "PM";
  return `${hour % 12 === 0 ? 12 : hour % 12}:00 ${suffix}`;
}

function parseDay(value: string): CalendarDay | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) } : null;
}

/** The form's range as UTC instants. "All day" runs from 8 AM on the start date to the end of the end date. */
export function rangeToUtc(form: RangeForm, timeZone: string): { start: Date; end: Date } | null {
  const from = parseDay(form.fromDate);
  const to = parseDay(form.toDate);
  if (!from || !to) return null;
  const fromHour = form.allDay ? WORKDAY_FIRST_SLOT_HOUR : form.fromHour;
  const toHour = form.allDay ? 24 : form.toHour;
  const start = zonedTimeToDate(from, fromHour, timeZone);
  const end = toHour === 24 ? zonedTimeToDate(addDays(to, 1), 0, timeZone) : zonedTimeToDate(to, toHour, timeZone);
  return { start, end };
}

/** The first problem with the form (same rules and messages as the server), or "" when it can be previewed. */
export function rangeProblem(form: RangeForm, timeZone: string, now: Date = new Date()): string {
  const range = rangeToUtc(form, timeZone);
  if (!range) return "Choose a start and end date.";
  if (range.end <= range.start) return "End must be after start.";
  if (range.end <= now) return "Range is entirely in the past.";
  if (range.end.getTime() > now.getTime() + RANGE_HORIZON_DAYS * 86_400_000) return `Cannot change slots beyond ${RANGE_HORIZON_DAYS} days.`;
  if (form.mode === "block") {
    if (!form.category) return "Please choose a reason.";
    if (form.category === "OTHER" && !form.note.trim()) return "Please describe the reason.";
  }
  return "";
}

const labelStyle: React.CSSProperties = { fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' };
const inputStyle: React.CSSProperties = {
  padding: '9px 10px',
  borderRadius: '8px',
  border: '1px solid rgba(136, 194, 227, 0.36)',
  fontSize: '14px',
  backgroundColor: 'rgba(9, 35, 55, 0.82)',
  color: '#eef8ff'
};
const cellStyle: React.CSSProperties = { padding: '8px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const button = (color: string, disabled = false): React.CSSProperties => ({
  background: disabled ? '#94a3b8' : color,
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  padding: '8px 16px',
  fontSize: '14px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  fontWeight: '500'
});

interface RangeBlockPanelProps {
  doctorId: string;
  accessToken: string;
  /** Called after a block or unblock is applied (to reload the grid). */
  onChanged: () => void | Promise<void>;
}

type Pending = { mode: "block" | "unblock"; start: string; end: string; category?: BlockReasonCategory; note?: string };

export function RangeBlockPanel({ doctorId, accessToken, onChanged }: RangeBlockPanelProps) {
  const timeZone = useClinicTimeZone();
  const today = dayKey(clinicToday(timeZone));
  const [form, setForm] = useState<RangeForm>({
    mode: "block", fromDate: today, fromHour: 9, toDate: today, toHour: 17, allDay: false, category: "", note: "",
  });
  const [problem, setProblem] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [preview, setPreview] = useState<RangePreview | null>(null);
  const [dialogMessage, setDialogMessage] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [working, setWorking] = useState(false);
  const [result, setResult] = useState<{ text: string; error: boolean } | null>(null);
  const [blocks, setBlocks] = useState<ScheduleBlockRow[]>([]);

  const update = (changes: Partial<RangeForm>) => {
    setForm(prev => ({ ...prev, ...changes }));
    setProblem("");
  };

  const loadBlocks = async () => {
    try {
      setBlocks(await api.listScheduleBlocks(accessToken, doctorId));
    } catch (err) {
      console.error("Failed to load blocks:", err);
    }
  };

  useEffect(() => { loadBlocks(); }, [doctorId, accessToken]);

  const runPreview = async (next: Pending) => {
    setWorking(true);
    try {
      const body = { start: next.start, end: next.end };
      const data = next.mode === "block"
        ? await api.previewRangeBlock(accessToken, doctorId, { ...body, reason_category: next.category as BlockReasonCategory, reason_note: next.note || undefined })
        : await api.previewRangeUnblock(accessToken, doctorId, body);
      setPending(next);
      setPreview(data);
      setAcknowledged(false);
      return true;
    } catch (err) {
      setProblem(parseErrorMessage(err));
      return false;
    } finally {
      setWorking(false);
    }
  };

  const handlePreview = async () => {
    const issue = rangeProblem(form, timeZone);
    if (issue) {
      setProblem(issue);
      return;
    }
    const range = rangeToUtc(form, timeZone)!;
    setResult(null);
    setDialogMessage("");
    await runPreview({
      mode: form.mode,
      start: range.start.toISOString(),
      end: range.end.toISOString(),
      ...(form.mode === "block" && { category: form.category as BlockReasonCategory, note: form.note.trim() }),
    });
  };

  /** "Unblock all" on an active block: preview an unblock of the block's own range. */
  const handleUnblockAll = async (block: ScheduleBlockRow) => {
    setResult(null);
    setDialogMessage("");
    await runPreview({ mode: "unblock", start: block.start, end: block.end });
  };

  const closeDialog = () => {
    setPending(null);
    setPreview(null);
    setDialogMessage("");
  };

  const handleConfirm = async () => {
    if (!pending || !preview) return;
    setWorking(true);
    try {
      const body = { start: pending.start, end: pending.end, fingerprint: preview.fingerprint };
      if (pending.mode === "block") {
        const done = await api.applyRangeBlock(accessToken, doctorId, { ...body, reason_category: pending.category!, reason_note: pending.note || undefined });
        setResult({
          text: done.needs_reschedule > 0
            ? `${done.message} ${done.needs_reschedule} booked appointment(s) need rescheduling.`
            : done.message,
          error: false,
        });
      } else {
        const done = await api.applyRangeUnblock(accessToken, doctorId, body);
        setResult({ text: done.message, error: false });
      }
      closeDialog();
      await Promise.all([onChanged(), loadBlocks()]);
    } catch (err) {
      const message = parseErrorMessage(err);
      if (message === SCHEDULE_CHANGED) {
        // Someone changed the schedule since the preview: show the new impact and ask again
        setWorking(false);
        await runPreview(pending);
        setDialogMessage(SCHEDULE_CHANGED);
      } else {
        setDialogMessage(message);
      }
    } finally {
      setWorking(false);
    }
  };

  const hasConflicts = !!preview && preview.mode === "block" && preview.appointments.length > 0;
  const fromHours = Array.from({ length: WORKDAY_LAST_SLOT_HOUR - WORKDAY_FIRST_SLOT_HOUR + 1 }, (_, i) => WORKDAY_FIRST_SLOT_HOUR + i);
  const toHours = [...fromHours, 24];
  const shown = (iso: string) => formatInZone(iso, timeZone, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const visibleBlocks = blocks.filter(b => b.state !== "RELEASED");

  return (
    <>
      <div className="card" style={{ padding: '20px' }}>
        <h3 style={{ marginTop: 0 }}>Block or Unblock a Time Range</h3>
        <ClinicTimeNote />
        <div role="radiogroup" aria-label="Action" style={{ display: 'flex', gap: '16px', margin: '12px 0' }}>
          {(["block", "unblock"] as const).map(mode => (
            <label key={mode} style={{ color: '#eef8ff', cursor: 'pointer' }}>
              <input type="radio" name="range-mode" value={mode} checked={form.mode === mode} onChange={() => update({ mode })} />{" "}
              {mode === "block" ? "Block" : "Unblock"}
            </label>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', alignItems: 'end' }}>
          <div>
            <label htmlFor="range-from-date" style={labelStyle}>From date</label>
            <input id="range-from-date" type="date" value={form.fromDate} min={today}
              max={dayKey(addDays(clinicToday(timeZone), RANGE_HORIZON_DAYS))}
              onChange={e => update({ fromDate: e.target.value })} style={inputStyle} />
          </div>
          {!form.allDay && (
            <div>
              <label htmlFor="range-from-hour" style={labelStyle}>From hour</label>
              <select id="range-from-hour" value={form.fromHour} onChange={e => update({ fromHour: Number(e.target.value) })} style={inputStyle}>
                {fromHours.map(h => <option key={h} value={h}>{hourLabel(h)}</option>)}
              </select>
            </div>
          )}
          <div>
            <label htmlFor="range-to-date" style={labelStyle}>To date</label>
            <input id="range-to-date" type="date" value={form.toDate} min={today}
              max={dayKey(addDays(clinicToday(timeZone), RANGE_HORIZON_DAYS))}
              onChange={e => update({ toDate: e.target.value })} style={inputStyle} />
          </div>
          {!form.allDay && (
            <div>
              <label htmlFor="range-to-hour" style={labelStyle}>To hour (not included)</label>
              <select id="range-to-hour" value={form.toHour} onChange={e => update({ toHour: Number(e.target.value) })} style={inputStyle}>
                {toHours.map(h => <option key={h} value={h}>{hourLabel(h)}</option>)}
              </select>
            </div>
          )}
          <label style={{ color: '#eef8ff', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.allDay} onChange={e => update({ allDay: e.target.checked })} /> All day
          </label>
        </div>

        {form.mode === "block" && (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(200px, 1fr) 2fr', gap: '12px', marginTop: '12px' }}>
            <div>
              <label htmlFor="range-reason" style={labelStyle}>Reason <span style={{ color: '#ff90ab' }}>*</span></label>
              <select id="range-reason" value={form.category} onChange={e => update({ category: e.target.value as BlockReasonCategory | "" })} style={inputStyle}>
                <option value="">Choose a reason</option>
                {REASON_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="range-note" style={labelStyle}>Note{form.category === "OTHER" ? " *" : " (optional)"}</label>
              <input id="range-note" type="text" maxLength={500} value={form.note} onChange={e => update({ note: e.target.value })}
                placeholder="Shown to staff only, never to patients" style={{ ...inputStyle, width: '100%' }} />
            </div>
          </div>
        )}

        {problem && <p role="alert" style={{ color: '#ff90ab', margin: '12px 0 0 0' }}>{problem}</p>}
        {result && <p role="status" style={{ color: result.error ? '#ff90ab' : '#49d7c2', margin: '12px 0 0 0' }}>{result.text}</p>}
        <div style={{ marginTop: '16px' }}>
          <button onClick={handlePreview} disabled={working} style={button('#42b5f5', working)}>Preview</button>
        </div>
      </div>

      <div className="card" style={{ padding: '20px' }}>
        <h3 style={{ marginTop: 0 }}>Active Blocks</h3>
        {visibleBlocks.length === 0 ? (
          <p style={{ color: '#b4cce2', margin: 0 }}>No active blocks.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={cellStyle}>From</th>
                <th style={cellStyle}>To</th>
                <th style={cellStyle}>Reason</th>
                <th style={cellStyle}>State</th>
                <th style={cellStyle}>Hours blocked</th>
                <th style={cellStyle}>Needs reschedule</th>
                <th style={cellStyle}></th>
              </tr>
            </thead>
            <tbody>
              {visibleBlocks.map(block => (
                <tr key={block.id}>
                  <td style={cellStyle}>{shown(block.start)}</td>
                  <td style={cellStyle}>{shown(block.end)}</td>
                  <td style={cellStyle}>{block.reason_label}{block.reason_note ? `: ${block.reason_note}` : ""}</td>
                  <td style={cellStyle}>{STATE_LABELS[block.state]}</td>
                  <td style={cellStyle}>{block.blocked_hours}</td>
                  <td style={cellStyle}>{block.needs_reschedule}</td>
                  <td style={cellStyle}>
                    <button onClick={() => handleUnblockAll(block)} disabled={working} style={button('#f0a020', working)}>Unblock all</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pending && preview && (
        <div role="dialog" aria-modal="true" aria-labelledby="range-preview-title"
          style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(2, 12, 22, 0.75)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 16px', overflowY: 'auto', zIndex: 1000 }}>
          <div className="card" style={{ padding: '20px', width: '100%', maxWidth: '760px', backgroundColor: 'rgba(9, 35, 55, 0.98)' }}>
            <h3 id="range-preview-title" style={{ marginTop: 0, color: '#eaf5ff' }}>
              {preview.mode === "block" ? "Block" : "Unblock"} {shown(preview.start)} – {shown(preview.end)}
            </h3>
            {dialogMessage && <p role="alert" style={{ color: '#ff90ab' }}>{dialogMessage}</p>}
            <ul data-testid="range-counts" style={{ color: '#eef8ff', lineHeight: 1.7 }}>
              {preview.mode === "block" ? (
                <>
                  {preview.slots_to_create > 0 && <li>Slots to create: {preview.slots_to_create} ({preview.created_blocked} blocked)</li>}
                  <li>Open slots to block: {preview.to_block}</li>
                  <li>Already blocked: {preview.already_blocked}</li>
                  <li>Booked appointments in range: {preview.appointments.length}</li>
                </>
              ) : (
                <>
                  <li>Blocked slots to open: {preview.to_open}</li>
                  <li>Appointments to clear "Needs reschedule" from: {preview.to_unflag}</li>
                  {preview.days_to_fill > 0 && <li>Days to fill with default slots: {preview.days_to_fill}</li>}
                  <li>Deleted hours are not restored.</li>
                </>
              )}
            </ul>

            {preview.appointments.length > 0 && (
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '12px' }}>
                <thead>
                  <tr><th style={cellStyle}>Date &amp; Time</th><th style={cellStyle}>Patient</th><th style={cellStyle}>Status</th></tr>
                </thead>
                <tbody>
                  {preview.appointments.map(a => (
                    <tr key={a.appointment_id}>
                      <td style={cellStyle}>{shown(a.appointment_time)}</td>
                      <td style={cellStyle}>{a.patient_name}</td>
                      <td style={cellStyle}>{a.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {hasConflicts && (
              <label style={{ color: '#fbbf24', display: 'block', marginBottom: '12px', cursor: 'pointer' }}>
                <input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />{" "}
                These appointments stay booked and are marked "Needs reschedule". Support staff will contact the patients.
              </label>
            )}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button onClick={closeDialog} disabled={working} style={button('#64748b', working)}>Cancel</button>
              <button onClick={handleConfirm} disabled={working || (hasConflicts && !acknowledged)}
                style={button('#28a745', working || (hasConflicts && !acknowledged))}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
