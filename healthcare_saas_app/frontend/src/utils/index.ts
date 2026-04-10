/**
 * Utility functions and helpers
 * This module contains reusable utility functions used throughout the application
 */

/**
 * Validates email format
 * @param value - The email string to validate
 * @returns True if email is valid, false otherwise
 */
export function validateEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Converts date format from MM/DD/YYYY to YYYY-MM-DD
 * @param dateString - Date string in MM/DD/YYYY format
 * @returns Date string in YYYY-MM-DD format or undefined
 */
export function convertDateFormat(dateString: string): string | undefined {
  if (!dateString) return undefined;
  
  const parts = dateString.split('/');
  if (parts.length === 3) {
    const month = parts[0].padStart(2, '0');
    const day = parts[1].padStart(2, '0');
    const year = parts[2];
    return `${year}-${month}-${day}`;
  }
  
  return undefined;
}

/**
 * Formats a date string for display
 * @param timeStr - The time string to format
 * @returns Formatted date string
 */
export function formatTime(timeStr: string): string {
  const date = new Date(timeStr);
  return date.toLocaleString('en-US', { 
    weekday: 'short', 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit'
  });
}

/**
 * Gets today's date in MM/DD/YYYY format
 * @returns Today's date formatted as MM/DD/YYYY
 */
export function getTodayFormatted(): string {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  const year = today.getFullYear();
  return `${month}/${day}/${year}`;
}

/**
 * Parses error messages from API responses
 * @param error - The error object or message
 * @returns Clean error message string
 */
export function parseErrorMessage(error: unknown): string {
  let errorMessage = "An error occurred";
  
  if (error instanceof Error) {
    errorMessage = error.message;
    // If it's still in JSON format, extract the detail
    if (errorMessage.startsWith("{")) {
      try {
        const errorData = JSON.parse(errorMessage);
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // Keep original message if parsing fails
      }
    }
  }
  
  return errorMessage;
}

/**
 * Creates a delay using setTimeout
 * @param ms - Milliseconds to delay
 * @returns Promise that resolves after the delay
 */
export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
