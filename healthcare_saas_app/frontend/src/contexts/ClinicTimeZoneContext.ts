/**
 * Clinic Time Zone Context
 * The signed-in user's clinic's IANA time zone (from login). Every time on screen is shown in it.
 * AuthProvider supplies it; without a provider (e.g. in component tests) it is the default clinic zone.
 */

import { createContext, useContext } from "react";
import { DEFAULT_CLINIC_TIMEZONE } from "../utils";

export const ClinicTimeZoneContext = createContext<string>(DEFAULT_CLINIC_TIMEZONE);

export function useClinicTimeZone(): string {
  return useContext(ClinicTimeZoneContext);
}
