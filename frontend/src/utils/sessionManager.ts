/**
 * Session Management Utility for Ko-Merge
 * 
 * Handles session persistence across browser refreshes using localStorage
 * and provides automatic session validation and restoration.
 */

import { apiBasePath } from '../config/deployment';

// Session storage key in localStorage
const SESSION_STORAGE_KEY = 'ko-merge-session-id';

export interface SessionInfo {
  session_id: string;
  created_at: string;
  last_accessed: string;
  expires_at: string;
  is_expired: boolean;
  session_remaining_minutes: number;
  file_cleanup_remaining_minutes: number;
  upload_db: string;
  upload_file_exists: boolean;
  fixed_db?: string;
  processed_file_exists: boolean;
  merge_groups_count: number;
  merge_groups: Array<[number, number[]]>;
}

export interface SessionValidationResult {
  valid: boolean;
  session_id: string;
  expires_at: string;
  session_remaining_minutes: number;
  file_cleanup_remaining_minutes: number;
  message: string;
}

/**
 * Store session ID in localStorage for persistence across browser refreshes
 */
export function storeSessionId(sessionId: string): void {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    console.log(`[SessionManager] Stored session ID: ${sessionId}`);
  } catch (error) {
    console.error('[SessionManager] Failed to store session ID:', error);
  }
}

/**
 * Retrieve stored session ID from localStorage
 */
export function getStoredSessionId(): string | null {
  try {
    const sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (sessionId) {
      console.log(`[SessionManager] Retrieved stored session ID: ${sessionId}`);
    }
    return sessionId;
  } catch (error) {
    console.error('[SessionManager] Failed to retrieve session ID:', error);
    return null;
  }
}

/**
 * Clear stored session ID from localStorage
 */
export function clearStoredSessionId(): void {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    console.log('[SessionManager] Cleared stored session ID');
  } catch (error) {
    console.error('[SessionManager] Failed to clear session ID:', error);
  }
}

/**
 * Validate and extend an existing session
 * 
 * This function checks if a session is still valid on the backend and extends
 * its timeout by another 2 hours. Returns session validation result.
 */
export async function validateSession(sessionId: string): Promise<SessionValidationResult | null> {
  try {
    console.log(`[SessionManager] Validating session: ${sessionId}`);
    
    const response = await fetch(`${apiBasePath}/validate-session/${sessionId}`);
    
    if (response.ok) {
      const result: SessionValidationResult = await response.json();
      console.log(`[SessionManager] Session validated successfully:`, {
        session_id: result.session_id,
        session_remaining_minutes: result.session_remaining_minutes,
        file_cleanup_remaining_minutes: result.file_cleanup_remaining_minutes
      });
      return result;
    } else if (response.status === 404) {
      console.log(`[SessionManager] Session not found: ${sessionId}`);
      clearStoredSessionId();
      return null;
    } else if (response.status === 410) {
      console.log(`[SessionManager] Session expired: ${sessionId}`);
      clearStoredSessionId();
      return null;
    } else {
      console.error(`[SessionManager] Session validation failed: ${response.status} ${response.statusText}`);
      return null;
    }
  } catch (error) {
    console.error('[SessionManager] Error validating session:', error);
    return null;
  }
}

/**
 * Get detailed session information without extending the session
 */
export async function getSessionInfo(sessionId: string): Promise<SessionInfo | null> {
  try {
    console.log(`[SessionManager] Getting session info: ${sessionId}`);
    
    const response = await fetch(`${apiBasePath}/session-info/${sessionId}`);
    
    if (response.ok) {
      const sessionInfo: SessionInfo = await response.json();
      console.log(`[SessionManager] Session info retrieved:`, {
        session_id: sessionInfo.session_id,
        is_expired: sessionInfo.is_expired,
        merge_groups_count: sessionInfo.merge_groups_count,
        upload_file_exists: sessionInfo.upload_file_exists,
        processed_file_exists: sessionInfo.processed_file_exists
      });
      return sessionInfo;
    } else if (response.status === 404) {
      console.log(`[SessionManager] Session not found: ${sessionId}`);
      clearStoredSessionId();
      return null;
    } else {
      console.error(`[SessionManager] Failed to get session info: ${response.status} ${response.statusText}`);
      return null;
    }
  } catch (error) {
    console.error('[SessionManager] Error getting session info:', error);
    return null;
  }
}

/**
 * Attempt to restore a session from localStorage
 * 
 * This function checks if there's a stored session ID, validates it with the backend,
 * and returns the session information if valid. This enables seamless session
 * restoration after browser refreshes.
 */
export async function restoreSession(): Promise<{
  sessionId: string;
  sessionInfo: SessionInfo;
} | null> {
  const storedSessionId = getStoredSessionId();
  
  if (!storedSessionId) {
    console.log('[SessionManager] No stored session ID found');
    return null;
  }
  
  console.log(`[SessionManager] Attempting to restore session: ${storedSessionId}`);
  
  // First validate the session (this also extends it)
  const validationResult = await validateSession(storedSessionId);
  
  if (!validationResult || !validationResult.valid) {
    console.log('[SessionManager] Session restoration failed - session invalid');
    return null;
  }
  
  // Get detailed session information
  const sessionInfo = await getSessionInfo(storedSessionId);
  
  if (!sessionInfo) {
    console.log('[SessionManager] Session restoration failed - could not get session info');
    return null;
  }
  
  console.log(`[SessionManager] Session restored successfully:`, {
    session_id: sessionInfo.session_id,
    merge_groups_count: sessionInfo.merge_groups_count,
    session_remaining_minutes: validationResult.session_remaining_minutes
  });
  
  return {
    sessionId: storedSessionId,
    sessionInfo
  };
}

/**
 * Check if session restoration should be attempted
 * 
 * This is a quick check that can be used to determine if the app should
 * attempt session restoration without making network requests.
 */
export function shouldAttemptRestore(): boolean {
  return getStoredSessionId() !== null;
}

/**
 * Format remaining time for display
 */
export function formatRemainingTime(minutes: number): string {
  if (minutes <= 0) {
    return 'Expired';
  } else if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? '' : 's'}`;
  } else {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (remainingMinutes === 0) {
      return `${hours} hour${hours === 1 ? '' : 's'}`;
    } else {
      return `${hours}h ${remainingMinutes}m`;
    }
  }
}

/**
 * Clean up session on logout or session end
 */
export async function cleanupSession(sessionId: string): Promise<boolean> {
  try {
    console.log(`[SessionManager] Cleaning up session: ${sessionId}`);
    
    const response = await fetch(`${apiBasePath}/cleanup/${sessionId}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      console.log('[SessionManager] Session cleaned up successfully');
      clearStoredSessionId();
      return true;
    } else {
      console.error(`[SessionManager] Failed to cleanup session: ${response.status} ${response.statusText}`);
      // Clear localStorage anyway since the session might be invalid
      clearStoredSessionId();
      return false;
    }
  } catch (error) {
    console.error('[SessionManager] Error cleaning up session:', error);
    clearStoredSessionId();
    return false;
  }
}
