export function formatTime(seconds: number): string {
  try {
    const sec = Math.floor(seconds);
    const hours = Math.floor(sec / 3600);
    const minutes = Math.floor((sec % 3600) / 60);
    const remainingSeconds = sec % 60;
    
    return `${hours.toString().padStart(2, '0')}h:${minutes
      .toString()
      .padStart(2, '0')}m:${remainingSeconds.toString().padStart(2, '0')}s`;
  } catch {
    return '00h:00m:00s';
  }
}
