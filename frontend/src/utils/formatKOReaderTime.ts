/**
 * Formats KOReader reading time in the specific format: "HH:MM (x days HH hours mm minutes)"
 * @param seconds - Total reading time in seconds
 * @returns Formatted time string
 */
export function formatKOReaderTime(seconds: number): string {
  try {
    const totalSeconds = Math.floor(seconds);
    
    // Calculate time components
    const days = Math.floor(totalSeconds / (24 * 3600));
    const hours = Math.floor((totalSeconds % (24 * 3600)) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    
    // Format HH:MM part
    const totalHours = Math.floor(totalSeconds / 3600);
    const totalMinutes = Math.floor((totalSeconds % 3600) / 60);
    const hhMM = `${totalHours.toString().padStart(2, '0')}:${totalMinutes.toString().padStart(2, '0')}`;
    
    // Format detailed breakdown
    let breakdown = '';
    if (days > 0) {
      breakdown += `${days} day${days !== 1 ? 's' : ''} `;
    }
    if (hours > 0) {
      breakdown += `${hours} hour${hours !== 1 ? 's' : ''} `;
    }
    if (minutes > 0) {
      breakdown += `${minutes} minute${minutes !== 1 ? 's' : ''}`;
    }
    
    // Clean up trailing space
    breakdown = breakdown.trim();
    
    // If no breakdown (less than a minute), show "0 minutes"
    if (!breakdown) {
      breakdown = '0 minutes';
    }
    
    return `${hhMM} (${breakdown})`;
  } catch {
    return '00:00 (0 minutes)';
  }
}
