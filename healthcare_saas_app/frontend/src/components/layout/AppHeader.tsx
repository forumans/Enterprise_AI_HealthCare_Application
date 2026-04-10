/**
 * AppHeader Component
 * Main application header with navigation, branding, and user actions
 * Handles the top navigation bar with menu dropdowns and user controls
 */

import React from "react";
import { Bell, Search, UserCircle2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useNavigation } from "../../hooks/useNavigation";
import { getRouteBreadcrumb } from "../../app/routeBreadcrumbs";
import type { SessionState } from "../../types/app";

interface AppHeaderProps {
  session: SessionState;
  onSignOut: () => void;
  tenantInfo?: { name: string } | null;
}

export function AppHeader({ session, onSignOut, tenantInfo }: AppHeaderProps) {
  const navigate = useNavigate();
  const tenantDisplayName = tenantInfo?.name?.trim() ?? "";
  const showTenantName = session.role !== "GUEST" && tenantDisplayName.length > 0;
  
  const { 
    navigationState, 
    submenuItems, 
    openMainMenu, 
    closeAllMenus, 
    isMainMenuActive,
    isMainMenuOpen 
  } = useNavigation(session);

  const breadcrumb = getRouteBreadcrumb(window.location.pathname);

  const mainMenus: Array<"Home" | "Doctors" | "Patients" | "Admin"> = ["Home", "Doctors", "Patients", "Admin"];

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
      </div>

      {showTenantName && (
        <div className="topbar-tenant-name" title={tenantDisplayName}>
          {tenantDisplayName}
        </div>
      )}
      
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
                      {item.label}
                    </Link>
                  ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      <div className="top-actions">
        <div className="search-pill">
          <Search size={14} /> Search
        </div>
        <Bell size={16} />
        <UserCircle2 size={18} />
        {session.role !== "GUEST" && (
          <button type="button" onClick={onSignOut}>Sign Out</button>
        )}
      </div>
    </header>
  );
}
