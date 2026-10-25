## ADDED Requirements

### Requirement: Range input and normalization
The system SHALL accept a range as a start and an end, each a clinic-local date and whole hour, sent as UTC ISO
datetimes. The range SHALL be half-open: a slot at time `t` is in the range when `start <= t < end`. The end
SHALL be after the start ("End must be after start.", 422). A start in the past SHALL be moved forward to the
next whole hour; a range that then has no future hours SHALL be refused ("Range is entirely in the past.", 400).
Only hours inside clinic office hours (8 AM–11 PM slot starts, clinic time) SHALL be affected.

#### Scenario: Half-open range
- **WHEN** a doctor blocks from Nov 3 9:00 AM to Nov 3 12:00 PM clinic time
- **THEN** the 9 AM, 10 AM and 11 AM slots are blocked and the 12 PM slot is not

#### Scenario: Multi-day range covers only office hours
- **WHEN** a doctor blocks from Nov 3 2:00 PM to Nov 5 10:00 AM
- **THEN** Nov 3 2 PM–11 PM, all of Nov 4 (8 AM–11 PM) and Nov 5 8 AM–9 AM slots are affected, and no slot is created outside office hours

#### Scenario: Start in the past is clamped
- **WHEN** at 10:20 AM a doctor blocks from 8:00 AM today to 1:00 PM today
- **THEN** only the 11 AM and 12 PM slots are affected and past slots are unchanged

#### Scenario: End before start
- **WHEN** the end is equal to or earlier than the start
- **THEN** the request fails with 422 "End must be after start." and nothing changes

### Requirement: Range horizon
A range block or unblock SHALL NOT reach more than 180 days ahead of now ("Cannot change slots beyond 180
days.", 400). Single-slot changes and booking keep their 30-day window.

#### Scenario: Block for a vacation five months away
- **WHEN** a doctor blocks a range ending 150 days from now
- **THEN** the block succeeds

#### Scenario: Range beyond the horizon
- **WHEN** a range ends more than 180 days from now
- **THEN** the request fails with 400 "Cannot change slots beyond 180 days." and nothing changes

### Requirement: Who may change a range
Range actions SHALL follow the same access rule as single-slot changes (`BR-SLOT-07`): a doctor may change only
their own slots; support staff may change any doctor's slots in their tenant; other roles get 403.

#### Scenario: Doctor targets another doctor
- **WHEN** a doctor sends a range block for a different doctor's id
- **THEN** the request fails with 403 "Not allowed to change another doctor's availability."

#### Scenario: Support staff blocks on a doctor's behalf
- **WHEN** support staff blocks a range for a doctor in their clinic
- **THEN** the block succeeds and the block record names the support staff user as its creator

### Requirement: Block reason
A range block SHALL require a reason category, one of Vacation, Conference, Sick, Personal, Administrative or
Other, and MAY carry a note of up to 500 characters. Category Other SHALL require a note. The reason SHALL be
stored on the block record and copied to each blocked slot's `block_reason`. Patients SHALL see only
"Unavailable" and never the reason.

#### Scenario: Missing category
- **WHEN** a block request has no reason category
- **THEN** the request fails with 422 and nothing changes

#### Scenario: Other without a note
- **WHEN** the category is Other and the note is empty
- **THEN** the request fails with 422 "Please describe the reason."

#### Scenario: Patient view hides the reason
- **WHEN** a patient views a blocked doctor's slots
- **THEN** the blocked hours are not offered and no reason text is returned to the patient

### Requirement: Block preview
Before a range block or unblock is applied, the system SHALL return a preview without changing anything. A
block preview SHALL report: slots to create, open slots to block, slots already blocked, and booked
appointments in the range (appointment id, clinic-local time, patient name, status). An unblock preview SHALL
report: blocked slots to open, booked appointments whose "Needs reschedule" flag will be cleared, and days to
fill with default slots. Each preview SHALL include a fingerprint computed from the affected slot ids, their
statuses and the appointment ids.

#### Scenario: Preview with booked appointments
- **WHEN** a doctor previews a block over a day with 16 slots, 3 of them booked and 2 already blocked
- **THEN** the preview reports 11 to block, 2 already blocked and lists the 3 appointments, and no slot changes

#### Scenario: Preview over days with no slots yet
- **WHEN** a doctor previews a block over two days that have no slots
- **THEN** the preview reports 32 slots to create (two full default days) and how many of them will be blocked

### Requirement: Confirm with fingerprint
Applying a range action SHALL require the fingerprint from its preview. The server SHALL recompute the
fingerprint inside the applying transaction; if it differs, it SHALL refuse with 409 "The schedule changed.
Review the changes again." and change nothing.

#### Scenario: A patient books between preview and confirm
- **WHEN** a patient books a slot in the range after the doctor previewed and before they confirmed
- **THEN** the confirm fails with 409 and the doctor sees a new preview that includes the new appointment

#### Scenario: Unchanged schedule
- **WHEN** nothing in the range changed since the preview
- **THEN** the action is applied exactly as previewed

### Requirement: Fill missing days before blocking
When a range touches a clinic-local day that has no slot for the doctor, the system SHALL first create the full
set of default office-hour slots for that day (future hours only), then apply the block. On a day that already
has slots, an hour inside the range that has no slot SHALL be created as `BLOCKED`; hours outside the range on
that day SHALL NOT be created.

#### Scenario: Partial-day block on a day 20 days out
- **WHEN** a doctor blocks 2 PM–4 PM on a day that has no slots
- **THEN** that day gets all 16 default slots, the 2 PM and 3 PM slots are `BLOCKED`, and the other 14 are `AVAILABLE`

#### Scenario: Day with a deleted hour
- **WHEN** a day has slots but the doctor deleted the 9 AM slot, and a block covers 8 AM–11 AM
- **THEN** the 8, 9 and 10 AM slots exist and are `BLOCKED`

### Requirement: Applying a block
Applying a block SHALL create one `schedule_blocks` record and, in one transaction: set every `AVAILABLE` slot
in the range to `BLOCKED` with the block's id and reason; leave already-`BLOCKED` slots with their existing
block and reason; and on every `BOOKED` slot in the range set the block's id and reason but keep it `BOOKED`.
No appointment SHALL be cancelled, moved or edited. The response SHALL report the counts and the number of
appointments now needing reschedule.

#### Scenario: Block over booked appointments
- **WHEN** a doctor blocks a range that contains 3 booked appointments
- **THEN** the 3 slots stay `BOOKED`, the 3 appointments are unchanged and are flagged "Needs reschedule", and every open slot in the range becomes `BLOCKED`

#### Scenario: Overlapping block
- **WHEN** a doctor blocks Nov 3–5 and then blocks Nov 4–6
- **THEN** Nov 4–5 slots keep the first block and reason, Nov 6 slots get the second block, and the second preview counted Nov 4–5 as already blocked

#### Scenario: Repeating the same block
- **WHEN** the same range is blocked twice
- **THEN** the second action blocks nothing new and no error is raised

### Requirement: Applying an unblock
Applying an unblock SHALL, in one transaction: set every `BLOCKED` slot in the range to `AVAILABLE` and clear
its `block_id` and `block_reason`, whether it was blocked by a range or a single-slot action; and on every
`BOOKED` slot in the range clear `block_id` and `block_reason` so it is no longer flagged. Appointments SHALL
NOT be changed. Days in the range with no slots SHALL be filled with default `AVAILABLE` slots. Hours missing
from a day that already has slots SHALL NOT be re-created.

#### Scenario: Unblock the whole range with appointments
- **WHEN** a doctor unblocks a range that was blocked over 3 booked appointments
- **THEN** the open hours become `AVAILABLE`, the 3 appointments stay booked with the same time and status, and they leave the "Needs reschedule" queue

#### Scenario: Partial unblock
- **WHEN** a doctor blocked Nov 3–7 and unblocks only Nov 5 10 AM–2 PM
- **THEN** only the Nov 5 10 AM–1 PM slots change, and the rest of the block stays in force

#### Scenario: Unblock after a patient was moved out
- **WHEN** support staff moved a patient out of a blocked hour (the hour became `BLOCKED`) and the doctor then unblocks that hour
- **THEN** the hour becomes `AVAILABLE`

#### Scenario: Unblock does not restore deleted hours
- **WHEN** a day has slots but the doctor deleted the 9 AM slot, and an unblock covers 8 AM–11 AM
- **THEN** no 9 AM slot is created

### Requirement: Block records and their state
Each block record SHALL keep doctor, tenant, start, end, reason category, note, creator and creation time.
Its state SHALL be derived from the slots that still reference it: Active when every in-range future slot still
references it, Partially released when some do, Released when none do. When the last slot is released the
record SHALL get `released_at` and `released_by`. `GET /doctor/availability/{doctor_id}/blocks` SHALL list
active and partially released blocks plus those released in the last 30 days, each with its state and counts.

#### Scenario: Unblock all from the list
- **WHEN** a doctor clicks "Unblock all" on an active block
- **THEN** an unblock is previewed for that block's range and, once confirmed, the block becomes Released

#### Scenario: Partially released block
- **WHEN** part of a block's range was unblocked
- **THEN** the list shows the block as Partially released with the number of hours still blocked

### Requirement: Single-slot changes follow the range rules
Blocking or unblocking one slot from the grid SHALL behave as a one-hour range: unblocking a slot clears its
`block_id`; blocking an open slot sets `BLOCKED` with the reason. A `BOOKED` slot SHALL still be refused for
single-slot changes ("Cannot modify a patient-booked slot."). The 30-day single-slot window SHALL stay.

#### Scenario: Unblock one hour of a range block from the grid
- **WHEN** a doctor unblocks one hour inside a range block from the grid
- **THEN** that hour becomes `AVAILABLE`, its `block_id` is cleared, and the block shows as Partially released

### Requirement: Concurrency safety
Range actions for a doctor SHALL be serialized per doctor, and SHALL lock the affected slot rows before
changing them. A booking that commits before the block's transaction SHALL be treated as a booked slot in the
range (flagged), never lost or double-booked. A booking attempted after the block commits SHALL be refused
because the slot is not `AVAILABLE`.

#### Scenario: Two staff block overlapping ranges at once
- **WHEN** two support staff confirm overlapping blocks for the same doctor at the same moment
- **THEN** one applies first; the other gets 409 "The schedule changed. Review the changes again."

#### Scenario: Booking races a block
- **WHEN** a patient's booking and a block on the same hour run at the same moment
- **THEN** either the booking succeeds and the slot ends up booked and flagged, or the block succeeds and the booking fails with "Requested slot is not available."

### Requirement: Clinic time zone and daylight saving
Ranges SHALL be interpreted and walked hour by hour in the clinic's IANA zone, and stored in UTC. A range
across a daylight-saving change SHALL affect each clinic-local office hour exactly once.

#### Scenario: Range across the autumn clock change
- **WHEN** a clinic in America/New_York blocks Nov 1 8 AM to Nov 2 8 AM across the DST change
- **THEN** each office hour on Nov 1 (8 AM–11 PM local) is blocked exactly once

### Requirement: Audit of range actions
Each applied range block or unblock SHALL write one audit entry on `schedule_blocks` with the actor, range,
reason category, counts and the ids of affected slots and appointments. Flagging or unflagging an appointment
SHALL write an audit entry on that appointment. Audit entries SHALL NOT include the patient's name or other
PHI beyond ids.

#### Scenario: Audit after a block with conflicts
- **WHEN** a block flags 3 appointments
- **THEN** there is one audit entry for the block and one for each of the 3 appointments, with ids only
