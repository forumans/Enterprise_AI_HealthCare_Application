/**
 * PatientDetailsCard Component
 * Displays patient information in a card format
 * Used for showing patient details on various pages
 */

import React from "react";
import type { SessionState } from "../../types/app";

interface PatientDetailsCardProps {
  patientDetails: any;
  showOnHome?: boolean;
}

export function PatientDetailsCard({ patientDetails, showOnHome = false }: PatientDetailsCardProps) {
  if (!patientDetails) return null;

  const cardStyle = {
    marginBottom: '16px',
    padding: '20px'
  };

  const titleStyle = {
    margin: '0 0 16px 0',
    color: '#eaf5ff'
  };

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '12px'
  };

  const labelStyle = {
    fontSize: '14px',
    fontWeight: '700',
    color: '#d6ebfb',
    display: 'block',
    marginBottom: '4px'
  };

  const valueStyle = {
    margin: '0',
    fontSize: '14px',
    color: '#e8f6ff'
  };

  return (
    <div className="card" style={cardStyle}>
      <h3 style={titleStyle}>Patient Details</h3>
      <div style={gridStyle}>
        <div>
          <label style={labelStyle}>Name</label>
          <p style={valueStyle}>{patientDetails.name}</p>
        </div>
        <div>
          <label style={labelStyle}>Email</label>
          <p style={valueStyle}>{patientDetails.email}</p>
        </div>
        <div>
          <label style={labelStyle}>Phone</label>
          <p style={valueStyle}>{patientDetails.phone}</p>
        </div>
        {patientDetails.date_of_birth && (
          <div>
            <label style={labelStyle}>Date of Birth</label>
            <p style={valueStyle}>{new Date(patientDetails.date_of_birth).toLocaleDateString()}</p>
          </div>
        )}
        {patientDetails.insurance_provider && (
          <div>
            <label style={labelStyle}>Insurance Provider</label>
            <p style={valueStyle}>{patientDetails.insurance_provider}</p>
          </div>
        )}
        {patientDetails.insurance_policy_number && (
          <div>
            <label style={labelStyle}>Policy Number</label>
            <p style={valueStyle}>{patientDetails.insurance_policy_number}</p>
          </div>
        )}
        {patientDetails.address && (
          <div style={{ gridColumn: '1 / -1' }}>
            <label style={labelStyle}>Address</label>
            <p style={valueStyle}>{patientDetails.address}</p>
          </div>
        )}
        {patientDetails.emergency_contact && (
          <div>
            <label style={labelStyle}>Emergency Contact</label>
            <p style={valueStyle}>{patientDetails.emergency_contact}</p>
          </div>
        )}
        {patientDetails.emergency_phone && (
          <div>
            <label style={labelStyle}>Emergency Phone</label>
            <p style={valueStyle}>{patientDetails.emergency_phone}</p>
          </div>
        )}
      </div>
    </div>
  );
}
