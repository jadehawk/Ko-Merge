// cSpell:ignore WRWNW
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { BookMetadata, CoverOptionsResponse } from '../types';
import { formatKOReaderTime } from '../utils/formatKOReaderTime';
import { 
  getCachedBookData, 
  setCachedBookData, 
  getCachedCoverForBook,
  cacheSelectedCoverImage,
  assessMetadataQuality,
  CoverWithMetadata,
  generateCacheKey
} from '../utils/bookCache';
import { apiBasePath } from '../config/deployment';

interface BookCoverProps {
  title: string;
  authors?: string;
  className?: string;
  bookId?: number;
  sessionId?: string;
  md5?: string;
  total_read_time?: number;
  onCoverUpdate?: (coverUrl: string) => void;
}

/**
 * BookCover component with on-demand cover search and local caching
 * Features instant cached cover display and progressive metadata loading
 */
function BookCover({ title, authors, className = '', md5, total_read_time, onCoverUpdate }: BookCoverProps) {
  const [imageError, setImageError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  
  // Cached data state
  const [cachedCover, setCachedCover] = useState<string | null>(null);
  const [cachedMetadata, setCachedMetadata] = useState<BookMetadata | null>(null);
  
  // Cover search state
  const [searchingCovers, setSearchingCovers] = useState(false);
  const [availableCovers, setAvailableCovers] = useState<CoverWithMetadata[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  
  // Progressive loading state
  const [searchingAmazon, setSearchingAmazon] = useState(false);
  const [amazonSearchComplete, setAmazonSearchComplete] = useState(false);
  const [fastSearchComplete, setFastSearchComplete] = useState(false);
  
  // Queue state for this book
  const [queueStatus, setQueueStatus] = useState<'not-queued' | 'queued' | 'processing' | 'timeout-retry' | 'success' | 'failed-permanent'>('not-queued');
  const [queuePosition, setQueuePosition] = useState<number>(0);
  
  // Cover selection state
  const [selectedCoverUrl, setSelectedCoverUrl] = useState<string | null>(null);
  const [savingCover, setSavingCover] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  
  // ISBN/ASIN search state
  const [showIsbnSearch, setShowIsbnSearch] = useState(false);
  const [isbnValue, setIsbnValue] = useState('');
  const [asinValue, setAsinValue] = useState('');
  const [searchingByCode, setSearchingByCode] = useState(false);

  // Enhanced global lazy loading queue with state management
  interface QueueItem {
    id: string;
    title: string;
    authors: string;
    callback: (coverUrl: string | null, metadata?: BookMetadata | null) => void;
    timestamp: number;
    status: 'queued' | 'processing' | 'timeout-retry' | 'success' | 'failed-permanent';
    retryCount: number;
    position: number;
  }

  const lazyLoadQueue: QueueItem[] = (window as any).__coverLazyLoadQueue || [];
  const queueStats = (window as any).__coverQueueStats || {
    totalBooks: 0,
    processed: 0,
    successful: 0,
    failed: 0,
    retryPending: 0,
    isProcessing: false,
    isPaused: false
  };
  
  if (!(window as any).__coverLazyLoadQueue) {
    (window as any).__coverLazyLoadQueue = lazyLoadQueue;
    (window as any).__coverQueueStats = queueStats;
  }

  // Timeout configuration
  const QUEUE_TIMEOUTS = {
    primary: 15000,    // 15 seconds first try
    retry: 10000,      // 10 seconds retry
    maxRetries: 1,     // Only retry once
    queuePause: 1000   // 1 second between books
  };

  /**
   * Add this book to the lazy loading queue for automatic cover fetching
   */
  const addToLazyLoadQueue = (): void => {
    if (!title || !authors) return;

    const id = `${title}-${authors}`.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();
    
    // Don't add duplicates
    if (lazyLoadQueue.some(item => item.id === id)) {
      console.log(`[BookCover] Already in lazy load queue: ${title}`);
      return;
    }

    // Calculate position based on DOM order (sequential processing)
    const bookElements = document.querySelectorAll('[data-book-id]');
    let domPosition = 1;
    
    // Find this book's position in the DOM
    for (let i = 0; i < bookElements.length; i++) {
      const element = bookElements[i];
      const elementTitle = element.getAttribute('data-book-title');
      const elementAuthor = element.getAttribute('data-book-author');
      
      if (elementTitle === title && elementAuthor === authors) {
        domPosition = i + 1;
        break;
      }
    }

    const queueItem: QueueItem = {
      id,
      title,
      authors,
      callback: (coverUrl: string | null, metadata?: BookMetadata | null) => {
        if (coverUrl) {
          console.log(`[BookCover] Lazy loaded cover for: ${title}`);
          setSelectedCoverUrl(coverUrl);
          setQueueStatus('success');
          
          // Cache the result with metadata if available
          setCachedBookData(title, authors, {
            coverUrls: [{
              url: coverUrl,
              source: 'google_books' as const,
              size: 'medium'
            }],
            sources: metadata ? { google_books: metadata } : {}
          });

          // Update cached metadata if available
          if (metadata) {
            setCachedMetadata(metadata);
          }
        } else {
          // No cover found
          setQueueStatus('failed-permanent');
        }
      },
      timestamp: Date.now(),
      status: 'queued',
      retryCount: 0,
      position: domPosition // Use DOM position for sequential processing
    };

    lazyLoadQueue.push(queueItem);
    queueStats.totalBooks = Math.max(queueStats.totalBooks, lazyLoadQueue.length);
    
    // Set initial queue state for this component
    setQueueStatus('queued');
    setQueuePosition(queueItem.position);
    
    console.log(`[BookCover] Added to lazy load queue: ${title} (DOM position: ${domPosition}, queue length: ${lazyLoadQueue.length})`);

    // Start processing if not already running
    if (!queueStats.isProcessing) {
      processLazyLoadQueue();
    }
  };

  /**
   * Enhanced queue processing with timeout protection and sequential ordering
   */
  const processLazyLoadQueue = async (): Promise<void> => {
    if (queueStats.isProcessing || queueStats.isPaused || lazyLoadQueue.length === 0) {
      return;
    }

    queueStats.isProcessing = true;
    console.log(`[BookCover] Starting enhanced lazy load processing (${lazyLoadQueue.length} items)`);

    // Sort queue by position to ensure sequential processing
    lazyLoadQueue.sort((a, b) => a.position - b.position);

    // Primary processing phase
    await processQueuePhase('primary');

    // Retry phase for failed items
    const retryItems = lazyLoadQueue.filter(item => item.status === 'timeout-retry');
    if (retryItems.length > 0) {
      console.log(`[BookCover] Starting retry phase for ${retryItems.length} items`);
      await processQueuePhase('retry');
    }

    queueStats.isProcessing = false;
    console.log(`[BookCover] Queue processing completed. Success: ${queueStats.successful}, Failed: ${queueStats.failed}`);
  };

  /**
   * Process a specific phase of the queue (primary or retry)
   */
  const processQueuePhase = async (phase: 'primary' | 'retry'): Promise<void> => {
    const timeout = phase === 'primary' ? QUEUE_TIMEOUTS.primary : QUEUE_TIMEOUTS.retry;
    
    while (lazyLoadQueue.length > 0) {
      if (queueStats.isPaused) {
        console.log(`[BookCover] Queue processing paused`);
        break;
      }

      const item = lazyLoadQueue.shift()!;
      
      // Skip items that don't match current phase
      if (phase === 'retry' && item.status !== 'timeout-retry') {
        continue;
      }

      // Update item status and notify components
      item.status = 'processing';
      updateQueueItemStatus(item.id, 'processing');
      console.log(`[BookCover] Processing ${phase}: ${item.title} (${lazyLoadQueue.length} remaining)`);

      try {
        // Create timeout promise
        const timeoutPromise = new Promise<never>((_, reject) => {
          setTimeout(() => reject(new Error('Timeout')), timeout);
        });

        // Create fetch promise
        const fetchPromise = fetchCoverWithMetadata(item);

        // Race between fetch and timeout
        const result = await Promise.race([fetchPromise, timeoutPromise]);
        
        // Success
        item.status = 'success';
        queueStats.successful++;
        queueStats.processed++;
        updateQueueItemStatus(item.id, 'success');
        
        // Call callback with result
        item.callback(result.coverUrl, result.metadata);
        
        console.log(`[BookCover] Successfully processed: ${item.title}`);

      } catch (error) {
        console.error(`[BookCover] Error processing ${item.title}:`, error);
        
        if (error instanceof Error && error.message === 'Timeout') {
          if (phase === 'primary' && item.retryCount < QUEUE_TIMEOUTS.maxRetries) {
            // Mark for retry
            item.status = 'timeout-retry';
            item.retryCount++;
            queueStats.retryPending++;
            updateQueueItemStatus(item.id, 'timeout-retry');
            lazyLoadQueue.push(item); // Add back to queue for retry
            console.log(`[BookCover] Timeout: ${item.title} marked for retry`);
          } else {
            // Permanent failure
            item.status = 'failed-permanent';
            queueStats.failed++;
            queueStats.processed++;
            updateQueueItemStatus(item.id, 'failed-permanent');
            item.callback(null, null);
            console.log(`[BookCover] Permanent failure: ${item.title}`);
          }
        } else {
          // Network or other error
          item.status = 'failed-permanent';
          queueStats.failed++;
          queueStats.processed++;
          updateQueueItemStatus(item.id, 'failed-permanent');
          item.callback(null, null);
        }
      }

      // Rate limiting between requests
      if (lazyLoadQueue.length > 0) {
        await new Promise(resolve => setTimeout(resolve, QUEUE_TIMEOUTS.queuePause));
      }
    }
  };

  /**
   * Update queue item status and notify components
   */
  const updateQueueItemStatus = (itemId: string, status: QueueItem['status']): void => {
    // Dispatch custom event to notify components of status changes
    const event = new CustomEvent('queueItemStatusUpdate', {
      detail: { itemId, status }
    });
    window.dispatchEvent(event);
  };

  /**
   * Fetch cover and metadata for a queue item with automatic source selection
   */
  const fetchCoverWithMetadata = async (item: QueueItem): Promise<{coverUrl: string | null, metadata: BookMetadata | null}> => {
    // First, get API configuration to determine the best source to use
    let defaultSource = 'openlibrary'; // Safe fallback
    try {
      const configResponse = await fetch(`${apiBasePath}/config`);
      if (configResponse.ok) {
        const configData = await configResponse.json();
        if (configData.success && configData.config) {
          defaultSource = configData.config.default_source;
          console.log(`[BookCover] Using ${defaultSource} as default source (Google Books available: ${configData.config.google_books_available})`);
        }
      }
    } catch (error) {
      console.warn(`[BookCover] Failed to get API config, using OpenLibrary fallback:`, error);
    }

    // Fetch cover options using the determined source
    const coverParams = new URLSearchParams({
      title: item.title,
      author: item.authors,
      source: defaultSource
    });

    const coverResponse = await fetch(`${apiBasePath}/cover-options?${coverParams}`);
    const coverData: CoverOptionsResponse = await coverResponse.json();

    let coverUrl: string | null = null;
    
    if (coverData.success && coverData.covers && coverData.covers.length > 0) {
      // Try the default source first
      const primaryCover = coverData.covers.find(cover => cover.source === defaultSource);
      if (primaryCover && primaryCover.url) {
        coverUrl = primaryCover.url;
      } else {
        // Fallback to any available cover
        const anyCover = coverData.covers.find(cover => cover.url);
        if (anyCover && anyCover.url) {
          coverUrl = anyCover.url;
        }
      }
    }

    // If no covers found and we tried Google Books, try OpenLibrary as fallback
    if (!coverUrl && defaultSource === 'google_books') {
      console.log(`[BookCover] No Google Books cover found for ${item.title}, trying OpenLibrary fallback`);
      const fallbackParams = new URLSearchParams({
        title: item.title,
        author: item.authors,
        source: 'openlibrary'
      });

      try {
        const fallbackResponse = await fetch(`${apiBasePath}/cover-options?${fallbackParams}`);
        const fallbackData: CoverOptionsResponse = await fallbackResponse.json();
        
        if (fallbackData.success && fallbackData.covers && fallbackData.covers.length > 0) {
          const openLibraryCover = fallbackData.covers.find(cover => cover.source === 'openlibrary');
          if (openLibraryCover && openLibraryCover.url) {
            coverUrl = openLibraryCover.url;
            console.log(`[BookCover] Found OpenLibrary fallback cover for ${item.title}`);
          }
        }
      } catch (error) {
        console.warn(`[BookCover] OpenLibrary fallback failed for ${item.title}:`, error);
      }
    }

    // Fetch metadata using the backend's automatic fallback logic
    let metadata: BookMetadata | null = null;
    if (coverUrl) {
      try {
        const metadataResponse = await fetch(`${apiBasePath}/book-details`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: item.title,
            authors: item.authors,
            source: defaultSource // Backend will automatically fallback if needed
          })
        });

        const metadataData = await metadataResponse.json();
        if (metadataData.success && metadataData.metadata) {
          metadata = metadataData.metadata;
        }
      } catch (error) {
        console.warn(`[BookCover] Failed to fetch metadata for ${item.title}:`, error);
        // Continue without metadata
      }
    }

    return { coverUrl, metadata };
  };

  /**
   * Load cached data and stored covers when component mounts
   * Includes rate-limited lazy loading for uncached books
   */
  useEffect(() => {
    if (!title || !authors) return;

    console.log(`[BookCover] Loading cached data for: "${title}" by "${authors}"`);
    
    let hasExistingCover = false;
    
    // First, try to load from localStorage cache
    const cached = getCachedBookData(title, authors);
    if (cached) {
      console.log(`[BookCover] Found localStorage cache:`, {
        hasSelectedCoverImage: !!cached.selectedCoverImage,
        hasSelectedCoverUrl: !!cached.selectedCoverUrl,
        coverUrlsCount: cached.coverUrls?.length || 0,
        sourcesCount: Object.keys(cached.sources || {}).length
      });
      
      // Load cached cover image for immediate display
      if (cached.selectedCoverImage) {
        console.log(`[BookCover] Loading cached cover image from localStorage`);
        setCachedCover(cached.selectedCoverImage);
        setSelectedCoverUrl(cached.selectedCoverUrl || null);
        hasExistingCover = true;
      } else if (cached.coverUrls && cached.coverUrls.length > 0) {
        // If no selected cover but we have cached covers, try to load the first one
        const firstCover = cached.coverUrls.find(cover => cover.url);
        if (firstCover) {
          console.log(`[BookCover] Using first cached cover URL: ${firstCover.source}`);
          setSelectedCoverUrl(firstCover.url);
          hasExistingCover = true;
        }
      }
      
      // Load cached metadata for modal
      const bestMetadata = cached.sources.amazon || cached.sources.google_books || cached.sources.openlibrary;
      if (bestMetadata) {
        console.log(`[BookCover] Loading cached metadata from: ${cached.sources.amazon ? 'amazon' : cached.sources.google_books ? 'google_books' : 'openlibrary'}`);
        setCachedMetadata(bestMetadata);
      }
      
      // If we have cached covers, populate the available covers for the modal
      if (cached.coverUrls && cached.coverUrls.length > 0) {
        const cachedCovers: CoverWithMetadata[] = cached.coverUrls
          .filter(cover => cover.source && cover.url)
          .map(cover => {
            const sourceMetadata = cached.sources[cover.source as keyof typeof cached.sources];
            const quality = sourceMetadata ? assessMetadataQuality(sourceMetadata) : {
              hasDescription: false,
              hasRating: false,
              hasCategories: false,
              descriptionLength: 0
            };
            
            return {
              url: cover.url,
              source: cover.source as 'google_books' | 'openlibrary' | 'amazon',
              size: cover.size,
              ...quality,
              rating: sourceMetadata?.average_rating,
              metadata: sourceMetadata
            };
          });
        
        console.log(`[BookCover] Loaded ${cachedCovers.length} cached covers for modal`);
        setAvailableCovers(cachedCovers);
      }
    }
    
    // Check backend database for stored covers
    loadStoredCoverFromDatabase().then(() => {
      // If no existing cover found, add to lazy loading queue
      if (!hasExistingCover && !selectedCoverUrl && !cachedCover) {
        console.log(`[BookCover] No existing cover found, adding to lazy loading queue: "${title}"`);
        addToLazyLoadQueue();
      }
    });
  }, [title, authors]);

  /**
   * Listen for queue status updates
   */
  useEffect(() => {
    if (!title || !authors) return;

    const bookId = `${title}-${authors}`.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();

    const handleQueueStatusUpdate = (event: CustomEvent) => {
      const { itemId, status } = event.detail;
      if (itemId === bookId) {
        console.log(`[BookCover] Queue status update for ${title}: ${status}`);
        setQueueStatus(status);
      }
    };

    window.addEventListener('queueItemStatusUpdate', handleQueueStatusUpdate as EventListener);

    return () => {
      window.removeEventListener('queueItemStatusUpdate', handleQueueStatusUpdate as EventListener);
    };
  }, [title, authors]);


  /**
   * Load stored cover and metadata from backend database
   */
  const loadStoredCoverFromDatabase = async (): Promise<void> => {
    if (!title || !authors) return;

    try {
      console.log(`[BookCover] Checking backend database for stored cover...`);
      
      // Check for stored cover
      const coverParams = new URLSearchParams({
        title: title,
        author: authors
      });
      
      const coverResponse = await fetch(`${apiBasePath}/cover-preference?${coverParams}`);
      
      if (coverResponse.ok) {
        const coverData = await coverResponse.json();
        console.log(`[BookCover] Found stored cover in database:`, coverData);
        
        if (coverData.success && coverData.stored_covers && coverData.stored_covers.length > 0) {
          const storedCover = coverData.stored_covers[0];
          const coverImageUrl = `${apiBasePath}/covers/${storedCover.image_hash}`;
          
          console.log(`[BookCover] Loading stored cover: ${coverImageUrl}`);
          setSelectedCoverUrl(coverImageUrl);
          
          // If we don't have a cached cover image, this stored cover takes priority
          if (!cachedCover) {
            setCachedCover(coverImageUrl);
          }
        }
      } else if (coverResponse.status === 404) {
        console.log(`[BookCover] No stored cover found in database for "${title}" by "${authors}"`);
      }

      // Check for cached metadata using cache-only endpoint (no API calls)
      console.log(`[BookCover] Checking for cached metadata...`);
      
      try {
        const metadataParams = new URLSearchParams({
          title: title,
          author: authors
        });
        
        const metadataResponse = await fetch(`${apiBasePath}/cached-metadata?${metadataParams}`);
        
        if (metadataResponse.ok) {
          const metadataData = await metadataResponse.json();
          
          if (metadataData.success && metadataData.metadata) {
            console.log(`[BookCover] Found cached metadata from ${metadataData.source}:`, metadataData.metadata);
            
            // Only set metadata if we don't already have it from localStorage
            if (!cachedMetadata) {
              setCachedMetadata(metadataData.metadata);
              console.log(`[BookCover] Loaded cached metadata from backend database (${metadataData.source})`);
            }
          } else {
            console.log(`[BookCover] No cached metadata found in database for "${title}" by "${authors}"`);
          }
        } else if (metadataResponse.status === 404) {
          console.log(`[BookCover] No cached metadata found in database for "${title}" by "${authors}"`);
        }
      } catch (error) {
        console.log(`[BookCover] Error checking cached metadata:`, error);
      }
      
    } catch (error) {
      console.error(`[BookCover] Error loading stored data from database:`, error);
    }
  };

  /**
   * Search for covers from fast sources (Google Books + OpenLibrary) first
   */
  const searchForFastCovers = async (): Promise<void> => {
    if (!title) return;

    setSearchingCovers(true);
    setSearchError(null);
    setFastSearchComplete(false);
    setAmazonSearchComplete(false);

    try {
      console.log(`[BookCover] Starting fast search for: "${title}" by "${authors}"`);

      // Search fast sources with exclude_sources parameter to prevent Amazon from being included
      const params = new URLSearchParams({
        title: title,
        author: authors || '',
        source: 'all', // Search all sources but exclude Amazon
        exclude_sources: 'amazon' // Explicitly exclude Amazon from fast search
      });

      const response = await fetch(`${apiBasePath}/cover-options?${params}`);
      const data: CoverOptionsResponse = await response.json();

      console.log(`[BookCover] Fast search response:`, data);

      if (data.success && data.covers) {
        console.log(`[BookCover] Found ${data.covers.length} covers from fast sources`);
        
        // Fetch metadata for each unique source
        const sourceMetadata: Record<string, BookMetadata> = {};
        const uniqueSources = [...new Set(data.covers.map(cover => cover.source).filter(Boolean))];

        // Fetch metadata for each unique source
        for (const source of uniqueSources) {
          try {
            console.log(`[BookCover] Fetching metadata from ${source}...`);
            const metadataResponse = await fetch(`${apiBasePath}/book-details`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                title: title,
                authors: authors || '',
                source: source
              })
            });

            const metadataData = await metadataResponse.json();
            if (metadataData.success && metadataData.metadata) {
              sourceMetadata[source] = metadataData.metadata;
              console.log(`[BookCover] Got metadata from ${source}`);
            }
          } catch (error) {
            console.error(`Error fetching metadata from ${source}:`, error);
          }
        }

        // Process covers with metadata
        const allCovers: CoverWithMetadata[] = [];
        for (const cover of data.covers) {
          if (!cover.source || !cover.url) continue;
          
          const metadata = sourceMetadata[cover.source];
          const quality = metadata ? assessMetadataQuality(metadata) : {
            hasDescription: false,
            hasRating: false,
            hasCategories: false,
            descriptionLength: 0
          };

          allCovers.push({
            url: cover.url,
            source: cover.source as 'google_books' | 'openlibrary' | 'amazon',
            size: cover.size,
            ...quality,
            rating: metadata?.average_rating,
            metadata
          });
        }

        // Remove duplicates
        const uniqueCovers = allCovers.filter((cover, index, self) => 
          index === self.findIndex(c => c.url === cover.url)
        );

        console.log(`[BookCover] Total unique covers found: ${uniqueCovers.length}`);
        setAvailableCovers(uniqueCovers);
        setFastSearchComplete(true);

        // Cache the fast results (excluding Amazon)
        const realCovers = uniqueCovers.map(cover => ({
          url: cover.url,
          source: cover.source as 'google_books' | 'openlibrary' | 'amazon',
          size: cover.size
        }));
        
        // Update cache with new results
        setCachedBookData(title, authors || '', {
          coverUrls: realCovers,
          sources: sourceMetadata
        });

        if (uniqueCovers.length === 0) {
          setSearchError('No covers found from Google Books or OpenLibrary');
        }
      } else {
        console.log(`[BookCover] No covers found from fast sources:`, data.error || 'Unknown error');
        setSearchError('No covers found from Google Books or OpenLibrary');
      }

    } catch (error) {
      setSearchError('Network error while searching for covers');
      console.error('Error searching for covers:', error);
    } finally {
      setSearchingCovers(false);
    }
  };

  /**
   * Search Amazon covers (slow, optional)
   */
  const searchAmazonCovers = async (): Promise<void> => {
    if (!title || amazonSearchComplete) return;

    setSearchingAmazon(true);
    setSearchError(null);

    try {
      const params = new URLSearchParams({
        title: title,
        author: authors || '',
        source: 'amazon'
      });

      const response = await fetch(`${apiBasePath}/cover-options?${params}`);
      const data: CoverOptionsResponse = await response.json();

      if (data.success && data.covers) {
        // For Amazon, we need to fetch metadata separately since the cover search doesn't include it
        // But we'll do it more efficiently by fetching it once for Amazon as a source
        let amazonMetadata: BookMetadata | null = null;
        
        try {
          console.log(`[BookCover] Fetching Amazon metadata for covers...`);
          const metadataResponse = await fetch(`${apiBasePath}/book-details`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: title,
              authors: authors || '',
              source: 'amazon'
            })
          });

          const metadataData = await metadataResponse.json();
          if (metadataData.success && metadataData.metadata) {
            amazonMetadata = metadataData.metadata;
            console.log(`[BookCover] Got Amazon metadata for covers`);
          }
        } catch (error) {
          console.error(`Error fetching Amazon metadata:`, error);
        }

        // Process Amazon covers with the fetched metadata
        const amazonCovers: CoverWithMetadata[] = [];
        const quality = amazonMetadata ? assessMetadataQuality(amazonMetadata) : {
          hasDescription: false,
          hasRating: false,
          hasCategories: false,
          descriptionLength: 0
        };

        for (const cover of data.covers) {
          if (!cover.source || !cover.url) continue;
          
          amazonCovers.push({
            url: cover.url,
            source: cover.source as 'google_books' | 'openlibrary' | 'amazon',
            size: cover.size,
            ...quality,
            rating: amazonMetadata?.average_rating,
            metadata: amazonMetadata || undefined
          });
        }

        // Add Amazon covers to existing covers (avoid duplicates)
        setAvailableCovers(prev => {
          const combined = [...prev, ...amazonCovers];
          return combined.filter((cover, index, self) => 
            index === self.findIndex(c => c.url === cover.url)
          );
        });

        // Update cache with Amazon results
        const cached = getCachedBookData(title, authors || '');
        if (cached) {
          const updatedCovers = [...cached.coverUrls, ...amazonCovers.map(cover => ({
            url: cover.url,
            source: cover.source as 'google_books' | 'openlibrary' | 'amazon',
            size: cover.size
          }))];
          
          const sourceMetadata = amazonMetadata ? { amazon: amazonMetadata } : {};
          
          setCachedBookData(title, authors || '', {
            coverUrls: updatedCovers.filter((cover, index, self) => 
              index === self.findIndex(c => c.url === cover.url)
            ),
            sources: { ...cached.sources, ...sourceMetadata }
          });
        }

        setAmazonSearchComplete(true);
        setSaveMessage(`Found ${amazonCovers.length} additional Amazon covers`);
        setTimeout(() => setSaveMessage(null), 3000);
      } else {
        setSearchError(data.error || 'No Amazon covers found');
        setTimeout(() => setSearchError(null), 3000);
      }
    } catch (error) {
      setSearchError('Network error while searching Amazon');
      console.error('Error searching Amazon:', error);
      setTimeout(() => setSearchError(null), 3000);
    } finally {
      setSearchingAmazon(false);
    }
  };

  // Legacy function for backward compatibility
  const searchForCovers = searchForFastCovers;

  /**
   * Clear cached cover and metadata data
   */
  const clearCachedData = (): void => {
    if (!title || !authors) return;
    
    // Clear from localStorage using the correct cache key format
    const cacheKey = generateCacheKey(title, authors);
    localStorage.removeItem(cacheKey);
    
    // Reset component state
    setCachedCover(null);
    setCachedMetadata(null);
    setSelectedCoverUrl(null);
    setAvailableCovers([]);
    
    setSaveMessage('Cached data cleared');
    setTimeout(() => setSaveMessage(null), 3000);
  };

  /**
   * Search by ISBN or ASIN using existing APIs
   */
  const searchByCode = async (): Promise<void> => {
    if (!isbnValue && !asinValue) return;
    
    setSearchingByCode(true);
    setSearchError(null);
    
    try {
      let searchParams;
      
      if (isbnValue) {
        // Search OpenLibrary and Google Books with ISBN
        searchParams = new URLSearchParams({
          title: isbnValue, // Use ISBN as title for search
          author: '',
          source: 'google_books',
          isbn: isbnValue
        });
      } else if (asinValue) {
        // Search Amazon ONLY with ASIN (no title/author)
        searchParams = new URLSearchParams({
          source: 'amazon',
          asin: asinValue
        });
      }
      
      if (searchParams) {
        const response = await fetch(`${apiBasePath}/cover-options?${searchParams}`);
        const data: CoverOptionsResponse = await response.json();
        
        if (data.success && data.covers) {
          // Process covers similar to regular search
          const uniqueCovers = data.covers.filter((cover, index, self) => 
            index === self.findIndex(c => c.url === cover.url)
          );
          
          const sourceMetadata: Record<string, BookMetadata> = {};
          const enhancedCovers: CoverWithMetadata[] = [];
          
          for (const cover of uniqueCovers) {
            if (!cover.source || !cover.url) continue;
            
            // Fetch metadata for the cover
            try {
              let metadataBody;
              
              if (isbnValue) {
                // For ISBN searches, pass title and ISBN
                metadataBody = {
                  title: isbnValue,
                  authors: '',
                  source: cover.source,
                  isbn: isbnValue
                };
              } else if (asinValue) {
                // For ASIN searches, only pass ASIN and source
                metadataBody = {
                  source: cover.source,
                  asin: asinValue
                };
              } else {
                // For regular searches, pass title and authors
                metadataBody = {
                  title: title,
                  authors: authors || '',
                  source: cover.source
                };
              }
              
              const metadataResponse = await fetch(`${apiBasePath}/book-details`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(metadataBody)
              });
              
              const metadataData = await metadataResponse.json();
              if (metadataData.success && metadataData.metadata) {
                sourceMetadata[cover.source] = metadataData.metadata;
              }
            } catch (error) {
              console.error(`Error fetching metadata from ${cover.source}:`, error);
            }
            
            const metadata = sourceMetadata[cover.source];
            const quality = metadata ? assessMetadataQuality(metadata) : {
              hasDescription: false,
              hasRating: false,
              hasCategories: false,
              descriptionLength: 0
            };
            
            enhancedCovers.push({
              url: cover.url,
              source: cover.source as 'google_books' | 'openlibrary' | 'amazon',
              size: cover.size,
              ...quality,
              rating: metadata?.average_rating,
              metadata
            });
          }
          
          // Add to existing covers instead of replacing
          setAvailableCovers(prev => [...prev, ...enhancedCovers]);
          
          setSaveMessage(`Found ${enhancedCovers.length} additional covers`);
          setTimeout(() => setSaveMessage(null), 3000);
        } else {
          setSearchError(data.error || 'No covers found for the provided code');
        }
      }
    } catch (error) {
      setSearchError('Network error while searching by code');
      console.error('Error searching by code:', error);
    } finally {
      setSearchingByCode(false);
    }
  };

  /**
   * Handle ISBN input change (clear ASIN when ISBN is entered)
   */
  const handleIsbnChange = (value: string): void => {
    setIsbnValue(value);
    if (value) setAsinValue(''); // Clear ASIN when ISBN is entered
  };

  /**
   * Handle ASIN input change (clear ISBN when ASIN is entered)
   */
  const handleAsinChange = (value: string): void => {
    setAsinValue(value);
    if (value) setIsbnValue(''); // Clear ISBN when ASIN is entered
  };

  /**
   * Clear both ISBN and ASIN inputs
   */
  const clearCodeInputs = (): void => {
    setIsbnValue('');
    setAsinValue('');
  };

  /**
   * Handle cover selection with immediate caching
   */
  const handleCoverSelection = async (cover: CoverWithMetadata): Promise<void> => {
    if (!title) return;

    setSavingCover(true);
    setSaveMessage(null);

    try {
      // Cache the selected cover image
      const success = await cacheSelectedCoverImage(title, authors || '', cover.url);
      
      if (success) {
        setSelectedCoverUrl(cover.url);
        setCachedCover(await getCachedCoverForBook(title, authors || ''));
        
        // Update metadata if available
        if (cover.metadata) {
          setCachedMetadata(cover.metadata);
        }

        // Save preference to backend
        const response = await fetch(`${apiBasePath}/cover-preference`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title,
            author: authors || '',
            md5: md5 || '',
            cover_url: cover.url
          })
        });

        if (response.ok) {
          setSaveMessage('Cover saved successfully!');
          setTimeout(() => setSaveMessage(null), 3000);
          
          // Notify parent component
          if (onCoverUpdate) {
            onCoverUpdate(cover.url);
          }
        }
      } else {
        setSaveMessage('Failed to cache cover image');
        setTimeout(() => setSaveMessage(null), 3000);
      }
    } catch (error) {
      setSaveMessage('Error saving cover');
      setTimeout(() => setSaveMessage(null), 3000);
      console.error('Error handling cover selection:', error);
    } finally {
      setSavingCover(false);
    }
  };

  /**
   * Handle modal open
   */
  const handleCoverClick = (): void => {
    if (title) {
      setShowModal(true);
    }
  };

  /**
   * Handle modal close
   */
  const handleCloseModal = (): void => {
    setShowModal(false);
    setSearchError(null);
  };

  /**
   * Handle keyboard events
   */
  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === 'Escape') {
      handleCloseModal();
    }
  };

  // Determine what cover to show
  const getCoverToDisplay = () => {
    // First priority: cached cover image (base64)
    if (cachedCover) {
      return cachedCover;
    }
    
    // Second priority: selected cover URL
    if (selectedCoverUrl) {
      return selectedCoverUrl;
    }
    
    // Third priority: check if we have any cached covers from previous searches
    const cached = getCachedBookData(title, authors || '');
    if (cached && cached.coverUrls.length > 0) {
      // Use the first available cached cover
      const firstCover = cached.coverUrls.find(cover => cover.url);
      if (firstCover) {
        return firstCover.url;
      }
    }
    
    // Fourth priority: try Google Books API fallback with proper encoding
    if (title && authors) {
      // Use Google Books API search instead of direct cover URL
      const query = encodeURIComponent(`${title} ${authors}`);
      return `https://books.google.com/books/publisher/content/images/frontcover?id=${query}&fife=w400-h600&source=gbs_api`;
    }
    
    // Last fallback: try title-only Google Books search
    if (title) {
      const query = encodeURIComponent(title);
      return `https://books.google.com/books/publisher/content/images/frontcover?id=${query}&fife=w400-h600&source=gbs_api`;
    }
    
    return null;
  };

  const handleImageLoad = () => {
    setIsLoading(false);
    setImageError(false);
  };

  const handleImageError = () => {
    setImageError(true);
    setIsLoading(false);
  };

  const getInitials = () => {
    const titleInitial = title?.charAt(0)?.toUpperCase() || 'B';
    const authorInitial = authors?.charAt(0)?.toUpperCase() || 'A';
    return `${titleInitial}${authorInitial}`;
  };

  const coverToDisplay = getCoverToDisplay();
  const shouldShowImage = !imageError && coverToDisplay;
  const isClickable = !!title;

  return (
    <>
      <div className="flex items-start gap-2">
        {/* Metadata quality indicators on the left side */}
        {cachedMetadata && (
          <div className="flex flex-col gap-1 mt-1">
            {cachedMetadata.description && (
              <div 
                className="flex items-center justify-center w-6 h-6 text-xs text-white bg-blue-600 rounded-full"
                title="Has Description"
              >
                {"📖"}
              </div>
            )}
            {cachedMetadata.average_rating !== undefined && cachedMetadata.average_rating !== null && cachedMetadata.average_rating > 0 && (
              <div 
                className="flex items-center justify-center w-6 h-6 text-xs text-white bg-yellow-600 rounded-full"
                title={`Rating: ${cachedMetadata.average_rating.toFixed(1)}`}
              >
                {"⭐"}
              </div>
            )}
            {cachedMetadata.description && cachedMetadata.average_rating !== undefined && cachedMetadata.average_rating !== null && cachedMetadata.average_rating > 0 && cachedMetadata.categories && cachedMetadata.categories.length > 0 && (
              <div 
                className="flex items-center justify-center w-6 h-6 text-xs text-white bg-green-600 rounded-full"
                title="Complete Metadata (Description + Rating + Categories)"
              >
                {"✨"}
              </div>
            )}
          </div>
        )}

        {/* Book Cover */}
        <div 
          className={`relative aspect-book bg-gradient-to-br from-slate-700 to-slate-800 rounded-lg overflow-hidden ${className} ${
            isClickable ? 'cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all duration-200' : ''
          }`}
          onClick={isClickable ? handleCoverClick : undefined}
          role={isClickable ? 'button' : undefined}
          tabIndex={isClickable ? 0 : undefined}
          onKeyDown={isClickable ? handleKeyDown : undefined}
          aria-label={isClickable ? `View details for ${title}` : undefined}
        >
          {shouldShowImage ? (
            <>
              <img
                src={coverToDisplay}
                alt={`Cover for ${title}`}
                className={`w-full h-full object-fill transition-opacity duration-300 ${
                  isLoading ? 'opacity-0' : 'opacity-100'
                }`}
                onLoad={handleImageLoad}
                onError={handleImageError}
              />
              {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-700">
                  <div className="text-2xl text-slate-300">{getInitials()}</div>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center w-full h-full">
              <div className="text-center">
                <div className="mb-2 text-2xl text-slate-300">{getInitials()}</div>
                <div className="px-2 text-xs leading-tight text-slate-400">
                  {title?.length > 20 ? `${title.substring(0, 20)}...` : title}
                </div>
              </div>
            </div>
          )}
        
        {/* Queue Status Overlays */}
        {queueStatus === 'queued' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-blue-900/80 rounded-lg">
            <div className="text-center text-white">
              <div className="mb-2 text-lg">🔍</div>
              <div className="text-xs font-medium">Queued for cover</div>
              {queuePosition > 0 && (
                <div className="text-xs opacity-75">Position: {queuePosition}</div>
              )}
            </div>
          </div>
        )}

        {queueStatus === 'processing' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-blue-900/80 rounded-lg">
            <div className="text-center text-white">
              <div className="w-6 h-6 mx-auto mb-2 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              <div className="text-xs font-medium">Searching...</div>
            </div>
          </div>
        )}

        {queueStatus === 'timeout-retry' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-orange-900/80 rounded-lg">
            <div className="text-center text-white">
              <div className="mb-2 text-lg">⏱️</div>
              <div className="text-xs font-medium">Will retry later</div>
            </div>
          </div>
        )}

        {queueStatus === 'failed-permanent' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-red-900/80 rounded-lg">
            <div className="text-center text-white">
              <div className="mb-2 text-lg">❌</div>
              <div className="text-xs font-medium">Cover not found</div>
              <button 
                className="px-2 py-1 mt-1 text-xs bg-red-700 rounded hover:bg-red-600"
                onClick={(e) => {
                  e.stopPropagation();
                  // Add manual retry logic here if needed
                }}
              >
                Retry
              </button>
            </div>
          </div>
        )}
        </div>
      </div>

      {/* Book Details Modal */}
      {showModal && createPortal(
        <div 
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black bg-opacity-50"
          onClick={handleCloseModal}
        >
          <div 
            className="bg-slate-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-700">
              <h2 className="text-xl font-bold text-slate-50">Book Details</h2>
              <button
                onClick={handleCloseModal}
                className="transition-colors text-slate-400 hover:text-slate-200"
                aria-label="Close modal"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6">
              {/* Book Cover and Basic Info */}
              <div className="flex flex-col gap-6 sm:flex-row">
                {coverToDisplay && (
                  <div className="flex-shrink-0">
                    <img
                      src={coverToDisplay}
                      alt={`Cover for ${title}`}
                      className="object-fill h-64 rounded-lg w-43"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}
                
                <div className="flex-1 space-y-3">
                  {/* KOReader Reading Time */}
                  {total_read_time !== undefined && total_read_time > 0 && (
                    <div className="flex items-center gap-2 text-sm">
                      <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span className="font-medium text-blue-300">
                        Reading Time: {formatKOReaderTime(total_read_time)}
                      </span>
                    </div>
                  )}
                  
                  <h3 className="text-2xl font-bold text-slate-50">{title}</h3>
                  {authors && (
                    <p className="text-lg text-slate-300">by {authors}</p>
                  )}
                  
                  {/* Metadata from cache */}
                  {cachedMetadata && (
                    <>
                      <div className="flex flex-wrap gap-4 text-sm text-slate-400">
                        <span>Publisher: {cachedMetadata.publisher || 'N/A'}</span>
                        <span>Published: {cachedMetadata.published_date || 'N/A'}</span>
                        <span>Pages: {(cachedMetadata.page_count && cachedMetadata.page_count > 0) ? cachedMetadata.page_count : 'N/A'}</span>
                        <span>Rating: {(cachedMetadata.average_rating && cachedMetadata.average_rating > 0) ? cachedMetadata.average_rating.toFixed(1) : 'N/A'}</span>
                      </div>
                      
                      {(cachedMetadata.average_rating !== undefined && cachedMetadata.average_rating !== null) && (
                        <div className="flex items-center gap-2">
                          <div className="flex text-yellow-400">
                            {[...Array(5)].map((_, i) => (
                              <svg
                                key={i}
                                className={`w-4 h-4 ${i < Math.floor(cachedMetadata.average_rating || 0) ? 'fill-current' : 'fill-gray-600'}`}
                                viewBox="0 0 20 20"
                              >
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                              </svg>
                            ))}
                          </div>
                          <span className="text-slate-300">
                            {cachedMetadata.average_rating.toFixed(1)}
                            {cachedMetadata.ratings_count && cachedMetadata.ratings_count > 0 ? ` (${cachedMetadata.ratings_count} reviews)` : cachedMetadata.ratings_count === 0 ? ' (0 reviews)' : ''}
                          </span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Description */}
              {cachedMetadata?.description && (
                <div className="mt-6">
                  <h4 className="mb-2 text-lg font-semibold text-slate-200">Description</h4>
                  <p className="leading-relaxed text-slate-300">{cachedMetadata.description}</p>
                </div>
              )}

              {/* Categories */}
              {cachedMetadata?.categories && cachedMetadata.categories.length > 0 && (
                <div className="mt-6">
                  <h4 className="mb-2 text-lg font-semibold text-slate-200">Categories</h4>
                  <div className="flex flex-wrap gap-2">
                    {cachedMetadata.categories.map((category, index) => (
                      <span
                        key={index}
                        className="px-3 py-1 text-sm text-blue-300 rounded-full bg-blue-600/20"
                      >
                        {category}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Search for Covers Button */}
              <div className="pt-6 mt-6 border-t border-slate-700">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-lg font-semibold text-slate-200">Cover Options</h4>
                  {saveMessage && (
                    <div className={`text-sm px-3 py-1 rounded-full ${
                      saveMessage.includes('successfully') 
                        ? 'bg-green-600/20 text-green-400' 
                        : 'bg-red-600/20 text-red-400'
                    }`}>
                      {saveMessage}
                    </div>
                  )}
                </div>

                {!searchingCovers && !fastSearchComplete && (
                  <button
                    onClick={searchForCovers}
                    className="w-full px-6 py-3 text-white transition-colors bg-blue-600 rounded-lg hover:bg-blue-700"
                  >
                    🔍 Search for Covers (Fast Sources)
                  </button>
                )}

                {searchingCovers && (
                  <div className="flex flex-col items-center justify-center py-6 space-y-3">
                    <div className="w-8 h-8 border-b-2 border-blue-500 rounded-full animate-spin"></div>
                    <span className="text-slate-300">Searching Google Books & OpenLibrary...</span>
                    {availableCovers.length > 0 && (
                      <div className="text-sm text-slate-400">
                        Found {availableCovers.length} covers so far...
                      </div>
                    )}
                  </div>
                )}

                {/* Amazon Search Button - appears after fast search is complete */}
                {fastSearchComplete && !amazonSearchComplete && (
                  <div className="p-4 mb-4 border rounded-lg bg-orange-900/20 border-orange-500/30">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h5 className="text-sm font-semibold text-orange-300">Amazon Search Available</h5>
                        <p className="text-xs text-orange-400">
                          Amazon has high-quality covers but takes longer to search (uses web scraping)
                        </p>
                      </div>
                      <svg className="w-6 h-6 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <button
                      onClick={searchAmazonCovers}
                      disabled={searchingAmazon}
                      className="w-full px-4 py-2 text-white transition-colors bg-orange-600 rounded-lg hover:bg-orange-700 disabled:bg-orange-800 disabled:cursor-not-allowed"
                    >
                      {searchingAmazon ? (
                        <>
                          <div className="inline-block w-4 h-4 mr-2 border-b-2 border-white rounded-full animate-spin"></div>
                          Searching Amazon... (this may take a while)
                        </>
                      ) : (
                        '🛒 Search Amazon (Slower but High Quality)'
                      )}
                    </button>
                  </div>
                )}

                {/* Amazon Search in Progress */}
                {searchingAmazon && (
                  <div className="flex flex-col items-center justify-center py-6 space-y-3">
                    <div className="w-8 h-8 border-b-2 border-orange-500 rounded-full animate-spin"></div>
                    <span className="text-slate-300">Searching Amazon...</span>
                    <div className="text-sm text-orange-400">
                      Please be patient, Amazon search uses web scraping and takes longer
                    </div>
                  </div>
                )}

                {searchError && (
                  <div className="p-4 border rounded-lg bg-red-900/20 border-red-500/30">
                    <p className="text-sm text-red-400">{searchError}</p>
                    <button
                      onClick={searchForCovers}
                      className="px-4 py-2 mt-2 text-white transition-colors bg-red-600 rounded hover:bg-red-700"
                    >
                      Retry Search
                    </button>
                  </div>
                )}

                {/* Additional Search Options */}
                {availableCovers.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4 mb-4">
                    <button
                      onClick={() => setShowIsbnSearch(!showIsbnSearch)}
                      className="px-3 py-1 text-xs text-blue-300 transition-colors border border-blue-600 rounded hover:bg-blue-600/20"
                    >
                      📚 Search by ISBN/ASIN
                    </button>
                    <button
                      onClick={clearCachedData}
                      className="px-3 py-1 text-xs text-red-300 transition-colors border border-red-600 rounded hover:bg-red-600/20"
                    >
                      🗑️ Clear Cache
                    </button>
                  </div>
                )}

                {/* ISBN/ASIN Search Form */}
                {showIsbnSearch && (
                  <div className="p-4 mb-4 border rounded-lg bg-slate-700/50 border-slate-600">
                    <h5 className="mb-3 text-sm font-semibold text-slate-200">Search by ISBN or ASIN</h5>
                    <div className="space-y-3">
                      <div>
                        <label className="block mb-1 text-xs text-slate-400">ISBN (for Google Books & OpenLibrary)</label>
                        <input
                          type="text"
                          value={isbnValue}
                          onChange={(e) => handleIsbnChange(e.target.value)}
                          placeholder="Enter ISBN (e.g., 9780123456789)"
                          className="w-full px-3 py-2 text-sm text-white rounded bg-slate-800 border-slate-600 focus:border-blue-500 focus:outline-none"
                          disabled={searchingByCode}
                        />
                      </div>
                      <div>
                        <label className="block mb-1 text-xs text-slate-400">ASIN (for Amazon)</label>
                        <input
                          type="text"
                          value={asinValue}
                          onChange={(e) => handleAsinChange(e.target.value)}
                          placeholder="Enter ASIN (e.g., B08N5WRWNW)"
                          className="w-full px-3 py-2 text-sm text-white rounded bg-slate-800 border-slate-600 focus:border-blue-500 focus:outline-none"
                          disabled={searchingByCode}
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={searchByCode}
                          disabled={(!isbnValue && !asinValue) || searchingByCode}
                          className="flex-1 px-4 py-2 text-sm text-white transition-colors bg-blue-600 rounded hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed"
                        >
                          {searchingByCode ? (
                            <>
                              <div className="inline-block w-4 h-4 mr-2 border-b-2 border-white rounded-full animate-spin"></div>
                              Searching...
                            </>
                          ) : (
                            '🔍 Search'
                          )}
                        </button>
                        <button
                          onClick={clearCodeInputs}
                          className="px-4 py-2 text-sm text-slate-300 transition-colors border border-slate-600 rounded hover:bg-slate-700"
                        >
                          Clear
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Cover Options Grid */}
                {availableCovers.length > 0 && (
                  <div className="grid grid-cols-2 gap-4 mt-4 sm:grid-cols-3 md:grid-cols-4">
                    {availableCovers.map((cover, index) => (
                      <div
                        key={index}
                        className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all aspect-[3/4] ${
                          selectedCoverUrl === cover.url
                            ? 'border-blue-500 ring-2 ring-blue-500/50'
                            : 'border-slate-600 hover:border-slate-500'
                        }`}
                        onClick={() => handleCoverSelection(cover)}
                      >
                        <img
                          src={cover.url}
                          alt={`Cover option ${index + 1}`}
                          className="object-fill w-full h-full"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                        
                        {/* Source badge */}
                        <div className="absolute top-1 right-1">
                          <span className={`px-1.5 py-0.5 text-xs rounded-full ${
                            cover.source === 'google_books' 
                              ? 'bg-blue-600/80 text-white' 
                              : cover.source === 'openlibrary'
                              ? 'bg-green-600/80 text-white'
                              : cover.source === 'amazon'
                              ? 'bg-orange-600/80 text-white'
                              : 'bg-gray-600/80 text-white'
                          }`}>
                            {cover.source === 'google_books' ? 'GB' : 
                             cover.source === 'openlibrary' ? 'OL' : 
                             cover.source === 'amazon' ? 'AZ' : '??'}
                          </span>
                        </div>

                        {/* Metadata quality indicators */}
                        <div className="absolute flex gap-1 bottom-1 left-1">
                          {cover.hasDescription && (
                            <div 
                              className="flex items-center justify-center w-5 h-5 text-xs text-white bg-blue-600 rounded-full"
                              title="Has Description"
                            >
                              📖
                            </div>
                          )}
                          {cover.hasRating && (
                            <div 
                              className="flex items-center justify-center w-5 h-5 text-xs text-white bg-yellow-600 rounded-full"
                              title="Has Rating"
                            >
                              ⭐
                            </div>
                          )}
                          {cover.hasDescription && cover.hasRating && cover.hasCategories && (
                            <div 
                              className="flex items-center justify-center w-5 h-5 text-xs text-white bg-green-600 rounded-full"
                              title="Complete Metadata (Description + Rating + Categories)"
                            >
                              ✨
                            </div>
                          )}
                        </div>

                        {/* Selected indicator */}
                        {selectedCoverUrl === cover.url && (
                          <div className="absolute inset-0 flex items-center justify-center bg-blue-600/20">
                            <svg className="w-8 h-8 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                          </div>
                        )}

                        {/* Loading overlay */}
                        {savingCover && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                            <div className="w-6 h-6 border-b-2 border-white rounded-full animate-spin"></div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

export default BookCover;
