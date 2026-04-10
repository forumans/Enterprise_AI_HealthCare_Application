/**
 * Navigation Hook
 * Manages navigation state, menu interactions, and routing logic
 * Provides centralized navigation management for the application
 */

import { useState, useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { submenuMap, getMainMenuFromPath } from "../config/menu";
import type { MainMenu, NavigationState, SessionState, Role } from "../types/app";

export function useNavigation(session: SessionState) {
  const location = useLocation();
  
  const [navigationState, setNavigationState] = useState<NavigationState>({
    activeMainMenu: getMainMenuFromPath(location.pathname),
    openMainMenu: null
  });

  // Update active menu when pathname changes
  useEffect(() => {
    setNavigationState(prev => ({
      ...prev,
      activeMainMenu: getMainMenuFromPath(location.pathname)
    }));
  }, [location.pathname]);

  // Handle clicking outside menu to close it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (navigationState.openMainMenu && !(event.target as Element).closest('.menu-item-container')) {
        setNavigationState(prev => ({ ...prev, openMainMenu: null }));
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [navigationState.openMainMenu]);

  // Filter submenu items based on authentication and role
  const submenuItems = useMemo(() => {
    const items = submenuMap[navigationState.openMainMenu ?? navigationState.activeMainMenu];
    return items.filter(item => {
      if (item.requiresAuth && !session.accessToken) return false;
      if (item.role && session.role !== item.role) return false;
      if (item.hideWhenAuth && session.accessToken) return false;
      return true;
    });
  }, [navigationState.openMainMenu, navigationState.activeMainMenu, session]);

  /**
   * Opens a main menu
   */
  function openMainMenu(menuName: MainMenu) {
    setNavigationState(prev => ({
      ...prev,
      openMainMenu: prev.openMainMenu === menuName ? null : menuName
    }));
  }

  /**
   * Closes all menus
   */
  function closeAllMenus() {
    setNavigationState(prev => ({ ...prev, openMainMenu: null }));
  }

  /**
   * Sets the active main menu
   */
  function setActiveMainMenu(menuName: MainMenu) {
    setNavigationState(prev => ({
      ...prev,
      activeMainMenu: menuName
    }));
  }

  /**
   * Checks if a menu item is currently active
   */
  function isMenuItemActive(itemPath: string): boolean {
    return location.pathname === itemPath;
  }

  /**
   * Checks if a main menu is currently active
   */
  function isMainMenuActive(menuName: MainMenu): boolean {
    return navigationState.activeMainMenu === menuName;
  }

  /**
   * Checks if a main menu is currently open
   */
  function isMainMenuOpen(menuName: MainMenu): boolean {
    return navigationState.openMainMenu === menuName;
  }

  return {
    // State
    navigationState,
    submenuItems,
    
    // Actions
    openMainMenu,
    closeAllMenus,
    setActiveMainMenu,
    
    // Getters
    isMenuItemActive,
    isMainMenuActive,
    isMainMenuOpen,
  };
}
