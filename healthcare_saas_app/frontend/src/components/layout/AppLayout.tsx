/**
 * AppLayout Component
 * Main application layout wrapper
 * Handles breadcrumbs, status messages, and content layout
 */

import React from "react";
import { useLocation } from "react-router-dom";
import { getRouteBreadcrumb } from "../../app/routeBreadcrumbs";
import { StatusMessage } from "../common/StatusMessage";
import type { SessionState } from "../../types/app";

interface AppLayoutProps {
  session: SessionState;
  status: string;
  children: React.ReactNode;
}

export function AppLayout({ session, status, children }: AppLayoutProps) {
  const location = useLocation();
  const breadcrumb = getRouteBreadcrumb(location.pathname);

  return (
    <div className="app-shell">
      <main className="content content-full">
        {location.pathname !== "/" && <div className="breadcrumbs">{breadcrumb}</div>}
        
        {status && (
          <div className={`status fade-out`}>
            {status}
            {session.role === "PATIENT" && session.userName && (
              <div className="session-details">
                {session.insuranceProvider && (
                  <div className="session-line">Insurance: {session.insuranceProvider}</div>
                )}
                {session.insurancePolicyId && (
                  <div className="session-line">Ins Id: {session.insurancePolicyId}</div>
                )}
              </div>
            )}
          </div>
        )}
        
        {children}
      </main>
    </div>
  );
}
