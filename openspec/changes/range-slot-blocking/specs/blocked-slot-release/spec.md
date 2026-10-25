## ADDED Requirements

### Requirement: Slot release rule
Whenever a slot stops being held by an appointment, the system SHALL set its status to `BLOCKED` if the slot
has a `block_id`, and to `AVAILABLE` otherwise. This rule SHALL apply to every path that frees a slot:
cancelling an appointment, deleting an appointment row, and moving an appointment off the slot by rescheduling.
The change SHALL happen in the same transaction as the cancel, delete or reschedule, so the hour is never
visible as `AVAILABLE` in between.

#### Scenario: Patient cancels an appointment in a blocked range
- **WHEN** a patient cancels an appointment whose slot is in a block
- **THEN** the slot becomes `BLOCKED` with the block's reason and cannot be booked

#### Scenario: Support staff reschedules a flagged appointment
- **WHEN** support staff reschedules a flagged appointment to an open slot outside the block
- **THEN** the new slot becomes `BOOKED`, the old slot becomes `BLOCKED`, and the appointment leaves the "Needs reschedule" queue

#### Scenario: Cancel outside any block
- **WHEN** a patient cancels an appointment whose slot has no `block_id`
- **THEN** the slot becomes `AVAILABLE`, as before

#### Scenario: Nobody can grab a freed blocked hour
- **WHEN** a flagged appointment is cancelled and another patient immediately tries to book that hour
- **THEN** the booking fails with 409 "Requested slot is not available."

### Requirement: Database trigger applies the release rule
The `sync_doctor_availability` trigger SHALL apply the release rule when an appointment's status becomes
`CANCELLED` and when an appointment row is deleted, and SHALL keep setting the matching slot to `BOOKED` on
insert without clearing its `block_id`.

#### Scenario: Cancellation through the trigger
- **WHEN** an appointment's status is updated to `CANCELLED` and its slot has a `block_id`
- **THEN** the trigger sets the slot to `BLOCKED`

#### Scenario: Booking a slot keeps no stale block
- **WHEN** an appointment is inserted for an `AVAILABLE` slot with no `block_id`
- **THEN** the trigger sets the slot to `BOOKED` and `block_id` stays empty

### Requirement: Rescheduling cannot land in a blocked hour
Rescheduling SHALL only target `AVAILABLE` slots, so an appointment SHALL NOT be moved into another hour of a
blocked range.

#### Scenario: Move within the blocked range
- **WHEN** support staff tries to reschedule a flagged appointment to another hour inside the same block
- **THEN** the request fails with 409 "Requested slot is not available."

### Requirement: Clinic time-zone change keeps blocks
A blocked slot moved by a clinic time-zone change (`BR-TIME`) SHALL keep its `block_id` and reason. When a booked slot's hour is reopened in the new zone, it
SHALL be created `BLOCKED` with the block's id and reason if the original booked slot had a `block_id`, and
`AVAILABLE` otherwise.

#### Scenario: Zone change with a blocked range
- **WHEN** a clinic with a Nov 3 9 AM–5 PM block changes its zone
- **THEN** the slots at 9 AM–5 PM local time in the new zone are still `BLOCKED` under the same block

#### Scenario: Zone change with a flagged booked slot
- **WHEN** a clinic changes its zone and a flagged booked slot stays at its exact time
- **THEN** the reopened hour at the same local time in the new zone is `BLOCKED`, not `AVAILABLE`
