/**
 * StatusMessage Component
 * A reusable component for displaying success or error messages
 * Used throughout the application for consistent user feedback
 */

import React from "react";
import type { StatusMessageProps } from "../../types/app";

export function StatusMessage({ message, type = 'error' }: StatusMessageProps) {
  if (!message) return null;
  
  const baseStyles = {
    padding: '12px',
    margin: '0 0 16px 0',
    borderRadius: '6px',
    border: '1px solid'
  };
  
  const typeStyles = type === 'success' 
    ? {
        backgroundColor: '#49d7c220',
        color: '#49d7c2',
        borderColor: '#49d7c2'
      }
    : {
        backgroundColor: '#ff90ab20',
        color: '#ff90ab',
        borderColor: '#ff90ab'
      };
  
  return (
    <div style={{ ...baseStyles, ...typeStyles }}>
      {message}
    </div>
  );
}
