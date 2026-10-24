/**
 * Support Doctor Availability Page Component
 * Lets support staff find a doctor by name or phone and block/unblock (or add) slots on the
 * doctor's behalf, using the same grid doctors use on Manage Availability.
 */

import React, { useState } from "react";
import { SupportSearchPanel } from "../common/SupportSearchPanel";
import { ManageAvailabilityPage, type AvailabilityDoctor } from "./ManageAvailabilityPage";

interface SupportDoctorAvailabilityPageProps {
  auth: any;
}

export function SupportDoctorAvailabilityPage({ auth }: SupportDoctorAvailabilityPageProps) {
  const [doctor, setDoctor] = useState<AvailabilityDoctor | null>(null);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Doctor Availability</h2>
      <p style={{ color: '#b4cce2', margin: 0 }}>
        Block or unblock a doctor's slots on their behalf. Patient-booked slots can't be changed here.
      </p>

      <SupportSearchPanel
        kind="doctor"
        accessToken={auth.session.accessToken}
        selectedId={doctor?.id}
        onPick={(d) => setDoctor({ id: d.id, name: d.name, specialty: d.specialty, license_number: d.license_number })}
      />

      {doctor && <ManageAvailabilityPage key={doctor.id} auth={auth} doctor={doctor} />}
    </section>
  );
}
