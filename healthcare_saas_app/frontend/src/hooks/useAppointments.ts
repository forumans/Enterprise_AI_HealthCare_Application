/**
 * Appointments Hook
 * Manages appointment booking, cancellation, and data retrieval
 * Provides centralized appointment management logic for patients and doctors
 */

import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api";
import { parseErrorMessage, getTodayFormatted, convertDateFormat } from "../utils";
import type {
  AppointmentRow,
  DoctorAppointmentRow,
  PatientSearchRow,
  SessionState,
} from "../types/app";

export function useAppointments(session: SessionState) {
  const [appointments, setAppointments] = useState<AppointmentRow[]>([]);
  const [doctorAppointments, setDoctorAppointments] = useState<DoctorAppointmentRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchRows, setSearchRows] = useState<PatientSearchRow[]>([]);

  // Explicit week start chosen by the caller; empty means today in clinic time (resolved when used)
  const [fromDate, setFromDate] = useState("");
  const location = useLocation();

  // Clear search results when navigating away from search page
  useEffect(() => {
    if (!location.pathname.includes("/doctors/search-patients")) {
      setSearchRows([]);
      setSearchQuery("");
    }
  }, [location.pathname]);

  /**
   * Loads all appointments for the current patient
   */
  async function loadPatientAppointments() {
    try {
      // Cancelled visits too, so the patient sees them under Past
      const rows = await api.listAllAppointments(session.accessToken, true);
      setAppointments(rows);
    } catch (error) {
      throw new Error(parseErrorMessage(error));
    }
  }

  /**
   * Loads doctor appointments for a specific date
   */
  async function loadDoctorDataWithDate(dateString: string) {
    try {
      const formattedDate = convertDateFormat(dateString);
      const rows = await api.doctorAllAppointments(session.accessToken, formattedDate);
      setDoctorAppointments(rows);
    } catch (error) {
      throw new Error(parseErrorMessage(error));
    }
  }

  /**
   * Loads doctor appointments (uses fromDate, else today in clinic time, if no date provided)
   */
  async function loadDoctorData(dateString?: string) {
    const dateToUse = dateString || fromDate || getTodayFormatted(session.clinicTimezone);
    return loadDoctorDataWithDate(dateToUse);
  }

  /**
   * Searches for patients based on query
   */
  async function searchPatients() {
    if (searchQuery.trim().length < 2) {
      setSearchRows([]);
      return;
    }
    try {
      const rows = await api.searchPatients(session.accessToken, searchQuery);
      setSearchRows(rows);
    } catch (error) {
      throw new Error(parseErrorMessage(error));
    }
  }

  /**
   * Marks an appointment as completed
   */
  async function completeAppointment(appointmentId: string) {
    try {
      await api.completeAppointment(appointmentId, session.accessToken);
    } catch (error) {
      throw new Error(parseErrorMessage(error));
    }
  }

  /**
   * Gets appointment details
   */
  async function getAppointmentDetails(appointmentId: string) {
    try {
      return await api.getAppointmentDetails(appointmentId, session.accessToken);
    } catch (error) {
      throw new Error(parseErrorMessage(error));
    }
  }

  /**
   * Gets today's appointments for doctors
   */
  async function getTodayAppointments() {
    try {
      return await api.getTodayAppointments(session.accessToken);
    } catch (error) {
      throw new Error(parseErrorMessage(error));
    }
  }

  return {
    // State
    appointments,
    doctorAppointments,
    searchQuery,
    searchRows,
    fromDate,

    // Actions
    setAppointments,
    setDoctorAppointments,
    setSearchQuery,
    setSearchRows,
    setFromDate,

    // API functions (booking and cancelling are done by the pages through api.ts)
    loadPatientAppointments,
    loadDoctorData,
    loadDoctorDataWithDate,
    searchPatients,
    completeAppointment,
    getAppointmentDetails,
    getTodayAppointments,
  };
}
