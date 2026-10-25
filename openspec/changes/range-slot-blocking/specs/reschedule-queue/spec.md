## ADDED Requirements

### Requirement: Needs reschedule flag
An appointment SHALL be considered "Needs reschedule" when it is live (`SCHEDULED` or `CONFIRMED`, not deleted),
in the future, and its slot is `BOOKED` with a `block_id`. The flag SHALL be derived from the slot, not stored
on the appointment, so it clears as soon as the slot is unblocked or the appointment is cancelled or moved.

#### Scenario: Flag appears after a block
- **WHEN** a doctor blocks a range that contains a confirmed appointment
- **THEN** that appointment is "Needs reschedule"

#### Scenario: Flag clears after unblock
- **WHEN** the doctor unblocks the hour of a flagged appointment
- **THEN** the appointment is no longer "Needs reschedule" and is otherwise unchanged

#### Scenario: Past or completed appointments are not flagged
- **WHEN** a block range is created and an appointment in the clinic's past or with status `COMPLETED` falls inside it
- **THEN** that appointment is not "Needs reschedule"

### Requirement: Support staff reschedule queue
Support staff SHALL have a "Needs Reschedule" screen (`/support/needs-reschedule`; its endpoint also allows
admins) listing every "Needs reschedule" appointment in
their tenant: clinic-local date and time, doctor, patient, patient phone and email, block reason category,
appointment status, and actions "Reschedule" and "Cancel" (the existing dialogs and confirmations). The list
SHALL be sorted by appointment time, with appointments in the next 24 hours marked "Urgent" and listed first.
It SHALL be filterable by doctor. Patients and doctors SHALL NOT access it (403).

#### Scenario: Support staff works the queue
- **WHEN** support staff reschedules a queued appointment to an open slot outside the block
- **THEN** the appointment leaves the queue and its old hour stays `BLOCKED`

#### Scenario: Urgent items first
- **WHEN** the queue holds an appointment 6 hours away and one 5 days away
- **THEN** the 6-hour one is listed first and marked "Urgent"

#### Scenario: Patient cannot see the queue
- **WHEN** a patient calls the queue endpoint
- **THEN** the request fails with 403

#### Scenario: Tenant isolation
- **WHEN** support staff in clinic A opens the queue
- **THEN** no appointment from clinic B is listed

### Requirement: Queue badge in the menu
The support staff menu entry "Needs Reschedule" SHALL show the number of queued appointments when it is above
zero.

#### Scenario: Badge after a block
- **WHEN** a doctor blocks a range over 3 appointments and support staff loads any support screen
- **THEN** the menu entry shows "Needs Reschedule (3)"

### Requirement: Grid shows flagged slots
On Manage Availability and Doctor Availability, a booked slot with a `block_id` SHALL be labeled "Booked –
Needs reschedule" in a distinct warning style, and remain disabled for single-slot changes. Hovering or focusing
it SHALL show the block reason to doctors and support staff.

#### Scenario: Doctor sees affected appointments in the grid
- **WHEN** a doctor views a week containing 2 flagged appointments
- **THEN** those 2 cells read "Booked – Needs reschedule" and are not clickable

### Requirement: Patients are not told the reason
Patient screens SHALL NOT show the block, the reason or the "Needs reschedule" flag. Contacting patients is done
by support staff in this phase; the system SHALL NOT send automatic messages about blocks.

#### Scenario: Patient's appointment list after a block
- **WHEN** a patient whose appointment is flagged views their appointments
- **THEN** the appointment shows its normal status and time, with no block information
