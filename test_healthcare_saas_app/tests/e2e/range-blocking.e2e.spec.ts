import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

/**
 * Range blocking end to end (feature 08 BR-SLOT-17..19, feature 16 SUP-RQ):
 * a doctor blocks a range over a booked appointment → support staff reschedule it from Needs Reschedule →
 * the old hour stays blocked and isn't offered to a patient → the doctor partially unblocks → the remaining
 * appointment is untouched.
 *
 * Needs the local stack (backend with migration 010 applied, frontend) and three accounts of one clinic:
 *   DOCTOR_E2E_EMAIL / DOCTOR_E2E_PASSWORD, SUPPORT_E2E_EMAIL / SUPPORT_E2E_PASSWORD,
 *   PATIENT_E2E_EMAIL / PATIENT_E2E_PASSWORD (and API_BASE_URL if not http://localhost:8000).
 * It books, moves and cancels appointments of that doctor and patient 3 days ahead, so use test accounts.
 */

const apiBaseUrl = process.env.API_BASE_URL ?? 'http://localhost:8000';
const accounts = {
  doctor: [process.env.DOCTOR_E2E_EMAIL, process.env.DOCTOR_E2E_PASSWORD],
  support: [process.env.SUPPORT_E2E_EMAIL, process.env.SUPPORT_E2E_PASSWORD],
  patient: [process.env.PATIENT_E2E_EMAIL, process.env.PATIENT_E2E_PASSWORD],
} as const;

type Login = { access_token: string; clinic_timezone: string };

async function apiLogin(request: APIRequestContext, who: keyof typeof accounts): Promise<Login> {
  const [email, password] = accounts[who];
  const response = await request.post(`${apiBaseUrl}/auth/login`, { data: { email, password } });
  expect(response.ok(), `${who} API login`).toBeTruthy();
  return response.json();
}

const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

/** Parts of an instant as shown in `timeZone`. */
function zoned(date: Date, timeZone: string) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', { timeZone, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
      .formatToParts(date).filter(p => p.type !== 'literal').map(p => [p.type, Number(p.value)]),
  );
  return { year: parts.year, month: parts.month, day: parts.day, hour: parts.hour % 24, minute: parts.minute };
}

/** The instant `timeZone` shows y-m-d at `hour`:00 (same approach as the app's zonedTimeToDate). */
function clinicTime(y: number, m: number, d: number, hour: number, timeZone: string): Date {
  const wall = Date.UTC(y, m - 1, d, hour);
  let guess = wall;
  for (let i = 0; i < 2; i++) {
    const shown = zoned(new Date(guess), timeZone);
    guess += wall - Date.UTC(shown.year, shown.month - 1, shown.day, shown.hour, shown.minute);
  }
  return new Date(guess);
}

async function uiLogin(page: Page, path: string, who: keyof typeof accounts) {
  const [email, password] = accounts[who];
  await page.goto(path);
  await page.fill('input[type="email"]', email!);
  await page.fill('input[type="password"]', password!);
  await page.click('button[type="submit"]');
  // Each role lands on its own start page after signing in
  await page.waitForURL(url => !url.pathname.endsWith('/login'));
}

test.describe('Range blocking E2E', () => {
  test.skip(
    Object.values(accounts).some(([email, password]) => !email || !password),
    'Set DOCTOR_E2E_*, SUPPORT_E2E_* and PATIENT_E2E_* credentials to run the range blocking flow.',
  );

  test('block over a booking, reschedule from the queue, partial unblock', async ({ browser, request }) => {
    test.setTimeout(120_000);  // three signed-in browsers and several round trips
    const doctor = await apiLogin(request, 'doctor');
    const patient = await apiLogin(request, 'patient');
    const support = await apiLogin(request, 'support');
    const tz = doctor.clinic_timezone;
    const doctorId: string = (await (await request.get(`${apiBaseUrl}/doctors/me`, { headers: auth(doctor.access_token) })).json()).id;

    // A clinic day 3 days ahead (default slots exist for the next 7 days)
    const day = zoned(new Date(Date.now() + 3 * 86_400_000), tz);
    const at = (hour: number) => clinicTime(day.year, day.month, day.day, hour, tz);
    const mmdd = `${String(day.month).padStart(2, '0')}/${String(day.day).padStart(2, '0')}`;
    const isoDay = `${day.year}-${String(day.month).padStart(2, '0')}-${String(day.day).padStart(2, '0')}`;

    /** Cancel the test patient's appointments with this doctor that day and unblock the whole day. */
    const cleanDay = async () => {
      const mine: Array<{ id: string; doctor_id: string; appointment_time: string }> =
        await (await request.get(`${apiBaseUrl}/appointments`, { headers: auth(patient.access_token) })).json();
      for (const apt of mine) {
        const time = new Date(apt.appointment_time).getTime();
        if (apt.doctor_id === doctorId && time >= at(0).getTime() && time < at(24).getTime()) {
          await request.delete(`${apiBaseUrl}/appointments/${apt.id}`, { headers: auth(patient.access_token) });
        }
      }
      const range = { start: at(8).toISOString(), end: at(24).toISOString() };
      const preview = await (await request.post(`${apiBaseUrl}/doctor/availability/${doctorId}/unblock/preview`, { headers: auth(doctor.access_token), data: range })).json();
      await request.post(`${apiBaseUrl}/doctor/availability/${doctorId}/unblock`, { headers: auth(doctor.access_token), data: { ...range, fingerprint: preview.fingerprint } });
    };

    // Start clean (also after an earlier failed run) and make sure the slots exist
    await request.get(`${apiBaseUrl}/doctor/availability/${doctorId}/all?days=30`, { headers: auth(doctor.access_token) });
    await cleanDay();
    try {
      // The patient books 10 AM and 11 AM
      const book = async (hour: number) => {
        const response = await request.post(`${apiBaseUrl}/appointments`, {
          headers: auth(patient.access_token),
          data: { doctor_id: doctorId, slot: at(hour).toISOString(), reason: 'E2E range blocking check' },
        });
        expect(response.status(), `book ${hour}:00`).toBe(201);
        return (await response.json()).id as string;
      };
      const moved = await book(10);
      const kept = await book(11);

      // 1. The doctor blocks 9 AM–1 PM over both bookings
      const doctorPage = await (await browser.newContext()).newPage();
      await uiLogin(doctorPage, '/doctors/login', 'doctor');
      // The token lives in memory only, so move around through the menus (a reload signs out)
      await doctorPage.getByRole('button', { name: 'Doctors' }).click();
      await doctorPage.getByRole('link', { name: 'Manage Availability' }).click();
      await doctorPage.getByLabel('From date').fill(isoDay);
      await doctorPage.getByLabel('From hour').selectOption('9');
      await doctorPage.getByLabel('To date').fill(isoDay);
      await doctorPage.getByLabel('To hour (not included)').selectOption('13');
      await doctorPage.getByLabel(/^Reason/).selectOption('VACATION');
      await doctorPage.getByRole('button', { name: 'Preview' }).click();
      const dialog = doctorPage.getByRole('dialog');
      await expect(dialog.getByTestId('range-counts')).toContainText('Booked appointments in range: 2');
      await expect(dialog.getByRole('button', { name: 'Confirm' })).toBeDisabled();
      await dialog.getByRole('checkbox').check();
      await dialog.getByRole('button', { name: 'Confirm' }).click();
      await expect(doctorPage.getByRole('status')).toContainText('Range blocked. 2 booked appointment(s) need rescheduling.');

      // 2. Support staff see both in Needs Reschedule and move the 10 AM one to 4 PM
      const supportPage = await (await browser.newContext()).newPage();
      await uiLogin(supportPage, '/support/login', 'support');
      await supportPage.getByRole('button', { name: 'Support Staff' }).click();
      const queueLink = supportPage.getByRole('link', { name: /^Needs Reschedule \(\d+\)$/ });
      await expect(queueLink).toBeVisible();
      await queueLink.click();
      const row = supportPage.locator(`tr[data-appointment-id="${moved}"]`);
      await row.getByRole('button', { name: 'Reschedule' }).click();
      const modal = supportPage.getByRole('dialog');
      const headers = modal.locator('thead th');
      await expect(headers.first()).toBeVisible();
      const column = (await headers.allTextContents()).findIndex(text => text.includes(mmdd));
      expect(column, `day ${mmdd} in the reschedule calendar`).toBeGreaterThanOrEqual(0);
      await modal.locator('tbody td').nth(column).getByText('4:00 PM', { exact: true }).click();
      supportPage.once('dialog', d => d.accept());
      await modal.getByRole('button', { name: 'Confirm Reschedule' }).click();
      await expect(supportPage.locator(`tr[data-appointment-id="${moved}"]`)).toHaveCount(0);
      await expect(supportPage.locator(`tr[data-appointment-id="${kept}"]`)).toBeVisible();

      // 3. The old 10 AM hour stays blocked: a patient can't book it and it isn't offered
      const rebook = await request.post(`${apiBaseUrl}/appointments`, {
        headers: auth(patient.access_token),
        data: { doctor_id: doctorId, slot: at(10).toISOString(), reason: 'E2E try the freed hour' },
      });
      expect(rebook.status()).toBe(409);
      const patientView: Array<{ slot_time: string; status: string; block_reason?: string }> =
        await (await request.get(`${apiBaseUrl}/doctor/availability/${doctorId}/all?days=30`, { headers: auth(patient.access_token) })).json();
      const tenAm = patientView.find(s => new Date(s.slot_time).getTime() === at(10).getTime());
      expect(tenAm?.status).toBe('BLOCKED');
      expect(tenAm && 'block_reason' in tenAm).toBeFalsy();  // patients never see the reason

      // 4. The doctor unblocks only 12 PM–1 PM; the 11 AM appointment is untouched and still flagged
      const partial = { start: at(12).toISOString(), end: at(13).toISOString() };
      const preview = await (await request.post(`${apiBaseUrl}/doctor/availability/${doctorId}/unblock/preview`, { headers: auth(doctor.access_token), data: partial })).json();
      const unblocked = await request.post(`${apiBaseUrl}/doctor/availability/${doctorId}/unblock`, {
        headers: auth(doctor.access_token), data: { ...partial, fingerprint: preview.fingerprint },
      });
      expect(unblocked.ok()).toBeTruthy();
      const queue: Array<{ id: string; appointment_time: string; status: string }> =
        await (await request.get(`${apiBaseUrl}/support/reschedule-queue?doctor_id=${doctorId}`, { headers: auth(support.access_token) })).json();
      const stillQueued = queue.find(item => item.id === kept);
      expect(stillQueued).toBeTruthy();
      expect(new Date(stillQueued!.appointment_time).getTime()).toBe(at(11).getTime());
      expect(queue.some(item => item.id === moved)).toBeFalsy();
    } finally {
      // Cancel the test appointments and unblock the day, pass or fail
      await cleanDay();
    }
  });
});
