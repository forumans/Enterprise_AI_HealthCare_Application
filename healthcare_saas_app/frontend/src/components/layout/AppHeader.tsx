/**
 * AppHeader Component
 * Main application header with navigation, branding, and user actions
 * Handles the top navigation bar with menu dropdowns and user controls
 */

import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useNavigation } from "../../hooks/useNavigation";
import { getRouteBreadcrumb } from "../../app/routeBreadcrumbs";
import { menuItemLabel } from "../../config/menu";
import { RESCHEDULE_QUEUE_CHANGED_EVENT } from "../pages/SupportRescheduleQueuePage";
import type { MainMenu, SessionState } from "../../types/app";

interface AppHeaderProps {
  session: SessionState;
  onSignOut: () => void;
  tenantInfo?: { name: string; domain?: string | null } | null;
}

/** Hosts that are served over plain http (local development and test setups). */
const LOCAL_HOST = /^(localhost|127\.0\.0\.1|[^:]+\.(local|localhost|test))(:\d+)?$/i;

/**
 * The URL of a clinic's own site from its `tenants.domain` (e.g. "healthylife.com" → "https://healthylife.com").
 * Only a bare host name (with an optional port) is accepted, so the link can't point anywhere else.
 */
export function clinicSiteUrl(domain: string | null | undefined): string | null {
  const host = (domain ?? "").trim().replace(/^https?:\/\//i, "").replace(/\/+$/, "");
  if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*(:\d{1,5})?$/i.test(host)) return null;
  return `${LOCAL_HOST.test(host) ? "http" : "https"}://${host.toLowerCase()}`;
}

export function AppHeader({ session, onSignOut, tenantInfo }: AppHeaderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  // Support staff: how many appointments need rescheduling (menu badge), refreshed on every screen change
  const [rescheduleQueue, setRescheduleQueue] = useState(0);
  const isSupportStaff = session.role === "SUPPORT_STAFF" && !!session.accessToken;

  useEffect(() => {
    if (!isSupportStaff) {
      setRescheduleQueue(0);
      return;
    }
    let active = true;
    const refresh = () => {
      api.getRescheduleQueue(session.accessToken)
        .then(rows => { if (active) setRescheduleQueue(rows.length); })
        .catch(() => { if (active) setRescheduleQueue(0); });
    };
    refresh();
    window.addEventListener(RESCHEDULE_QUEUE_CHANGED_EVENT, refresh);
    return () => {
      active = false;
      window.removeEventListener(RESCHEDULE_QUEUE_CHANGED_EVENT, refresh);
    };
  }, [isSupportStaff, session.accessToken, location.pathname]);
  const tenantDisplayName = tenantInfo?.name?.trim() ?? "";
  const showTenantName = session.role !== "GUEST" && tenantDisplayName.length > 0;
  const clinicSite = clinicSiteUrl(tenantInfo?.domain);

  const { 
    navigationState, 
    submenuItems, 
    openMainMenu, 
    closeAllMenus, 
    isMainMenuActive,
    isMainMenuOpen 
  } = useNavigation(session);

  const breadcrumb = getRouteBreadcrumb(window.location.pathname);

  const mainMenus: MainMenu[] = ["Home", "Doctors", "Patients", "Support Staff", "Admin"];

  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo-container">
          <div className="logo">
            <div className="logo-icon">
              <div className="heart-emoji-container">
                <div className="heart-emoji">💖</div>
                <div className="heart-glow"></div>
                <div className="heart-shadow"></div>
              </div>
            </div>
          </div>
          <div className="brand-text">
            <div className="brand-name">Peteti</div>
            <div className="brand-tagline">Software Inc.</div>
          </div>
        </div>

        {/* In the header's flex flow next to the brand, so a long name can't slide under the menu */}
        {showTenantName && (clinicSite ? (
          // A new tab: the sign-in lives in this tab's memory, so leaving it would sign the user out
          <a
            className="topbar-tenant-name"
            href={clinicSite}
            target="_blank"
            rel="noopener noreferrer"
            title={`${tenantDisplayName} – ${clinicSite.replace(/^https?:\/\//, "")} (opens in a new tab)`}
          >
            {tenantDisplayName}
          </a>
        ) : (
          <span className="topbar-tenant-name" title={tenantDisplayName}>{tenantDisplayName}</span>
        ))}
      </div>

      <nav className="top-nav-links">
        {mainMenus.map((menuName) => (
          <div key={menuName} className="menu-item-container">
            <button
              type="button"
              className={isMainMenuActive(menuName) ? "top-menu-button active-main" : "top-menu-button"}
              onClick={() => {
                if (menuName === "Home") {
                  navigate("/");
                  closeAllMenus();
                } else {
                  openMainMenu(menuName);
                }
              }}
            >
              {menuName}
            </button>
            {menuName !== "Home" && isMainMenuOpen(menuName) && (
              <div className="floating-dropdown">
                {submenuItems
                  .map((item) => (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={window.location.pathname === item.to ? "submenu-link active-submenu" : "submenu-link"}
                      onClick={closeAllMenus}
                    >
                      {menuItemLabel(item, { rescheduleQueue })}
                    </Link>
                  ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      <div className="top-actions">
        <div className="search-pill">
          🔍 Search
        </div>
        🔔
        👤
        {session.role !== "GUEST" && (
          <button type="button" onClick={onSignOut}>Sign Out</button>
        )}
      </div>
    </header>
  );
}
