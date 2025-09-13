/**
 * Cover Refresh System for Ko-Merge
 * 
 * Provides real-time cover updates and refresh mechanisms to ensure
 * book covers are updated when new covers are downloaded or cached.
 */

// Event system for cover updates
type CoverUpdateListener = (bookKey: string, coverUrl: string) => void;

class CoverRefreshManager {
  private listeners: Set<CoverUpdateListener> = new Set();
  private refreshIntervals: Map<string, NodeJS.Timeout> = new Map();

  /**
   * Subscribe to cover update events
   */
  subscribe(listener: CoverUpdateListener): () => void {
    this.listeners.add(listener);
    
    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Notify all listeners of a cover update
   */
  notifyCoverUpdate(bookKey: string, coverUrl: string): void {
    console.log(`[CoverRefresh] Notifying cover update for: ${bookKey}`);
    this.listeners.forEach(listener => {
      try {
        listener(bookKey, coverUrl);
      } catch (error) {
        console.error('[CoverRefresh] Error in cover update listener:', error);
      }
    });
  }

  /**
   * Start periodic refresh for a specific book
   * 
   * This will periodically check if new covers are available for a book
   * and notify listeners if covers are found.
   */
  startPeriodicRefresh(
    title: string, 
    author: string, 
    intervalMs: number = 30000 // 30 seconds default
  ): string {
    const bookKey = this.generateBookKey(title, author);
    
    // Clear existing interval if any
    this.stopPeriodicRefresh(bookKey);
    
    const interval = setInterval(async () => {
      try {
        await this.checkForNewCovers(title, author);
      } catch (error) {
        console.error(`[CoverRefresh] Error checking covers for ${bookKey}:`, error);
      }
    }, intervalMs);
    
    this.refreshIntervals.set(bookKey, interval);
    console.log(`[CoverRefresh] Started periodic refresh for: ${bookKey}`);
    
    return bookKey;
  }

  /**
   * Stop periodic refresh for a specific book
   */
  stopPeriodicRefresh(bookKey: string): void {
    const interval = this.refreshIntervals.get(bookKey);
    if (interval) {
      clearInterval(interval);
      this.refreshIntervals.delete(bookKey);
      console.log(`[CoverRefresh] Stopped periodic refresh for: ${bookKey}`);
    }
  }

  /**
   * Stop all periodic refreshes
   */
  stopAllRefreshes(): void {
    this.refreshIntervals.forEach((interval, bookKey) => {
      clearInterval(interval);
      console.log(`[CoverRefresh] Stopped refresh for: ${bookKey}`);
    });
    this.refreshIntervals.clear();
  }

  /**
   * Manually trigger a cover refresh for a specific book
   */
  async refreshCover(title: string, author: string): Promise<boolean> {
    try {
      console.log(`[CoverRefresh] Manual refresh for: "${title}" by "${author}"`);
      return await this.checkForNewCovers(title, author);
    } catch (error) {
      console.error('[CoverRefresh] Error in manual refresh:', error);
      return false;
    }
  }

  /**
   * Refresh covers for multiple books
   */
  async refreshMultipleCovers(books: Array<{title: string, authors?: string}>): Promise<number> {
    let refreshedCount = 0;
    
    for (const book of books) {
      try {
        const wasRefreshed = await this.refreshCover(book.title, book.authors || '');
        if (wasRefreshed) {
          refreshedCount++;
        }
        
        // Small delay to avoid overwhelming the server
        await new Promise(resolve => setTimeout(resolve, 100));
      } catch (error) {
        console.error(`[CoverRefresh] Error refreshing ${book.title}:`, error);
      }
    }
    
    console.log(`[CoverRefresh] Refreshed ${refreshedCount} out of ${books.length} books`);
    return refreshedCount;
  }

  /**
   * Check for new covers for a specific book
   */
  private async checkForNewCovers(title: string, author: string): Promise<boolean> {
    const bookKey = this.generateBookKey(title, author);
    
    try {
      // Import API dynamically to avoid circular dependencies
      const { apiBasePath } = await import('../config/deployment');
      
      // Check if there are stored covers for this book
      const response = await fetch(`${apiBasePath}/cover-preference?title=${encodeURIComponent(title)}&author=${encodeURIComponent(author)}`);
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.success && data.stored_covers && data.stored_covers.length > 0) {
          const coverUrl = `${apiBasePath}/covers/${data.stored_covers[0].image_hash}`;
          
          // Notify listeners of the new cover
          this.notifyCoverUpdate(bookKey, coverUrl);
          return true;
        }
      }
      
      return false;
    } catch (error) {
      console.error(`[CoverRefresh] Error checking covers for ${bookKey}:`, error);
      return false;
    }
  }

  /**
   * Generate a consistent book key for tracking
   */
  private generateBookKey(title: string, author: string): string {
    return `${title.toLowerCase().trim()}-${author.toLowerCase().trim()}`.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
  }

  /**
   * Get the number of active refresh intervals
   */
  getActiveRefreshCount(): number {
    return this.refreshIntervals.size;
  }

  /**
   * Get all active refresh book keys
   */
  getActiveRefreshKeys(): string[] {
    return Array.from(this.refreshIntervals.keys());
  }
}

// Create singleton instance
export const coverRefreshManager = new CoverRefreshManager();

// Cleanup on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    coverRefreshManager.stopAllRefreshes();
  });
}

// Export types and utilities
export type { CoverUpdateListener };

/**
 * Hook-like function for subscribing to cover updates in React components
 */
export function useCoverRefresh(
  _onCoverUpdate: CoverUpdateListener,
  _dependencies: any[] = []
): {
  refreshCover: (title: string, author: string) => Promise<boolean>;
  startPeriodicRefresh: (title: string, author: string, intervalMs?: number) => string;
  stopPeriodicRefresh: (bookKey: string) => void;
} {
  // This would typically use useEffect in a real React hook
  // For now, we'll provide the functions directly
  
  return {
    refreshCover: coverRefreshManager.refreshCover.bind(coverRefreshManager),
    startPeriodicRefresh: coverRefreshManager.startPeriodicRefresh.bind(coverRefreshManager),
    stopPeriodicRefresh: coverRefreshManager.stopPeriodicRefresh.bind(coverRefreshManager)
  };
}

/**
 * Utility function to trigger a manual refresh of all visible book covers
 */
export async function refreshAllVisibleCovers(books: Array<{title: string, authors?: string}>): Promise<number> {
  return await coverRefreshManager.refreshMultipleCovers(books);
}

/**
 * Utility function to notify when a cover has been manually selected/saved
 */
export function notifyManualCoverUpdate(title: string, author: string, coverUrl: string): void {
  const bookKey = coverRefreshManager['generateBookKey'](title, author);
  coverRefreshManager.notifyCoverUpdate(bookKey, coverUrl);
}
