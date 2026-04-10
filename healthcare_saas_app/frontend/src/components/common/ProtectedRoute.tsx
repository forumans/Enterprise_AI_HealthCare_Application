/**
 * ProtectedRoute Component
 * A route protection component that ensures only users with specified roles can access certain routes
 * Used throughout the application to implement role-based access control
 */

import React from "react";
import { Navigate } from "react-router-dom";
import type { ProtectedRouteProps } from "../../types/app";

export function ProtectedRoute(props: ProtectedRouteProps) {
  if (!props.allowed.includes(props.role)) {
    return <Navigate to="/" replace />;
  }
  return props.children;
}
