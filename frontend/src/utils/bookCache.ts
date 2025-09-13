/**
 * Book Cache Utility
 * Handles local storage caching for book metadata, covers, and selected cover images
 */

import { apiBasePath } from '../config/deployment';

export interface CoverOption {
  url: string;
  source: 'google_books' | 'openlibrary' | 'amazon';
  size?: string;
}

export interface BookMetadata {
  title: string;
  authors: string[];
  description?: string;
  publisher?: string;
  published_date?: string;
  page_count?: number;
  categories?: string[];
  average_rating?: number;
  ratings_count?: number;
  covers: string[];
  source: 'google_books' | 'openlibrary' | 'amazon';
}

export interface CachedBookData {
  title: string;
  author: string;
  sources: {
    google_books?: BookMetadata;
    openlibrary?: BookMetadata;
    amazon?: BookMetadata;
  };
  coverUrls: CoverOption[];
  selectedCoverUrl?: string;
  selectedCoverImage?: string; // base64 encoded image
  timestamp: number;
  ttl: number;
}

export interface CoverWithMetadata extends CoverOption {
  hasDescription: boolean;
  hasRating: boolean;
  hasCategories: boolean;
  descriptionLength?: number;
  rating?: number;
  metadata?: BookMetadata;
}

// Cache configuration
const CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds
const CACHE_PREFIX = 'book-cache-';
const MAX_CACHE_SIZE = 50 * 1024 * 1024; // 50MB limit

/**
 * Normalize text for consistent cache keys
 */
function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s]/g, '') // Remove special characters
    .replace(/\s+/g, '-'); // Replace spaces with hyphens
}

/**
 * Generate cache key for a book
 */
export function generateCacheKey(title: string, author: string): string {
  const normalizedTitle = normalizeText(title);
  const normalizedAuthor = normalizeText(author);
  return `${CACHE_PREFIX}${normalizedTitle}-${normalizedAuthor}`;
}

/**
 * Check if cached data is still valid
 */
function isCacheValid(cachedData: CachedBookData): boolean {
  const now = Date.now();
  return now - cachedData.timestamp < cachedData.ttl;
}

/**
 * Get cached book data from localStorage
 */
export function getCachedBookData(title: string, author: string): CachedBookData | null {
  try {
    const cacheKey = generateCacheKey(title, author);
    console.log(`[Cache] Looking for cache key: "${cacheKey}" for title: "${title}", author: "${author}"`);
    
    const cachedJson = localStorage.getItem(cacheKey);
    
    if (!cachedJson) {
      console.log(`[Cache] No cached data found for key: "${cacheKey}"`);
      
      // Debug: List all cache keys in localStorage
      const allCacheKeys = Object.keys(localStorage).filter(key => key.startsWith(CACHE_PREFIX));
      console.log(`[Cache] Available cache keys:`, allCacheKeys);
      
      return null;
    }

    const cachedData: CachedBookData = JSON.parse(cachedJson);
    
    if (!isCacheValid(cachedData)) {
      console.log(`[Cache] Cache expired for key: "${cacheKey}"`);
      // Remove expired cache
      localStorage.removeItem(cacheKey);
      return null;
    }

    console.log(`[Cache] Found valid cached data for key: "${cacheKey}"`, {
      coverUrlsCount: cachedData.coverUrls?.length || 0,
      hasSelectedCoverImage: !!cachedData.selectedCoverImage,
      sourcesCount: Object.keys(cachedData.sources || {}).length
    });

    return cachedData;
  } catch (error) {
    console.error('Error reading from cache:', error);
    return null;
  }
}

/**
 * Store book data in localStorage
 */
export function setCachedBookData(
  title: string, 
  author: string, 
  data: Partial<CachedBookData>
): boolean {
  try {
    const cacheKey = generateCacheKey(title, author);
    const existingData = getCachedBookData(title, author);
    
    const cacheData: CachedBookData = {
      title,
      author,
      sources: existingData?.sources || {},
      coverUrls: existingData?.coverUrls || [],
      selectedCoverUrl: existingData?.selectedCoverUrl,
      selectedCoverImage: existingData?.selectedCoverImage,
      timestamp: Date.now(),
      ttl: CACHE_TTL,
      ...data
    };

    const cacheJson = JSON.stringify(cacheData);
    
    // Check storage size before saving
    if (getStorageSize() + cacheJson.length > MAX_CACHE_SIZE) {
      cleanupOldCache();
    }

    localStorage.setItem(cacheKey, cacheJson);
    return true;
  } catch (error) {
    console.error('Error writing to cache:', error);
    return false;
  }
}

/**
 * Convert image URL to base64 using backend proxy to bypass CORS
 */
export async function imageUrlToBase64(url: string): Promise<string | null> {
  try {
    // Use backend proxy to fetch the image and bypass CORS restrictions
    const proxyUrl = `${apiBasePath}/proxy-image?url=${encodeURIComponent(url)}`;
    const response = await fetch(proxyUrl);
    
    if (!response.ok) {
      console.error(`Failed to fetch image via proxy: ${response.status} ${response.statusText}`);
      return null;
    }
    
    const blob = await response.blob();
    
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error('Error converting image to base64:', error);
    return null;
  }
}

/**
 * Cache selected cover image as base64
 */
export async function cacheSelectedCoverImage(
  title: string, 
  author: string, 
  coverUrl: string
): Promise<boolean> {
  try {
    const base64Image = await imageUrlToBase64(coverUrl);
    
    if (!base64Image) {
      return false;
    }

    return setCachedBookData(title, author, {
      selectedCoverUrl: coverUrl,
      selectedCoverImage: base64Image
    });
  } catch (error) {
    console.error('Error caching cover image:', error);
    return false;
  }
}

/**
 * Get current localStorage usage
 */
function getStorageSize(): number {
  let total = 0;
  for (const key in localStorage) {
    if (key.startsWith(CACHE_PREFIX)) {
      total += localStorage[key].length;
    }
  }
  return total;
}

/**
 * Clean up old cache entries to free space
 */
function cleanupOldCache(): void {
  const cacheEntries: Array<{ key: string; timestamp: number; size: number }> = [];
  
  // Collect all cache entries with timestamps
  for (const key in localStorage) {
    if (key.startsWith(CACHE_PREFIX)) {
      try {
        const data = JSON.parse(localStorage[key]);
        cacheEntries.push({
          key,
          timestamp: data.timestamp || 0,
          size: localStorage[key].length
        });
      } catch (error) {
        // Remove corrupted entries
        localStorage.removeItem(key);
      }
    }
  }

  // Sort by timestamp (oldest first)
  cacheEntries.sort((a, b) => a.timestamp - b.timestamp);

  // Remove oldest entries until we're under the size limit
  let currentSize = getStorageSize();
  for (const entry of cacheEntries) {
    if (currentSize < MAX_CACHE_SIZE * 0.8) { // Keep 20% buffer
      break;
    }
    localStorage.removeItem(entry.key);
    currentSize -= entry.size;
  }
}

/**
 * Clear all expired cache entries
 */
export function clearExpiredCache(): void {
  const now = Date.now();
  const keysToRemove: string[] = [];

  for (const key in localStorage) {
    if (key.startsWith(CACHE_PREFIX)) {
      try {
        const data = JSON.parse(localStorage[key]);
        if (now - data.timestamp > data.ttl) {
          keysToRemove.push(key);
        }
      } catch (error) {
        keysToRemove.push(key);
      }
    }
  }

  keysToRemove.forEach(key => localStorage.removeItem(key));
}

/**
 * Assess metadata quality for cover indicators
 */
export function assessMetadataQuality(metadata: BookMetadata): {
  hasDescription: boolean;
  hasRating: boolean;
  hasCategories: boolean;
  descriptionLength: number;
} {
  return {
    hasDescription: Boolean(metadata.description && metadata.description.length > 50),
    hasRating: Boolean(metadata.average_rating && metadata.average_rating > 0),
    hasCategories: Boolean(metadata.categories && metadata.categories.length > 0),
    descriptionLength: metadata.description?.length || 0
  };
}

/**
 * Get cached cover for immediate display in book grid
 */
export function getCachedCoverForBook(title: string, author: string): string | null {
  const cachedData = getCachedBookData(title, author);
  return cachedData?.selectedCoverImage || null;
}

/**
 * Debug function to list all cache entries
 */
export function debugListAllCacheEntries(): void {
  console.log('[Cache Debug] Listing all cache entries in localStorage:');
  const cacheEntries: Array<{key: string, title: string, author: string, timestamp: Date}> = [];
  
  for (const key in localStorage) {
    if (key.startsWith(CACHE_PREFIX)) {
      try {
        const data = JSON.parse(localStorage[key]);
        cacheEntries.push({
          key,
          title: data.title || 'Unknown',
          author: data.author || 'Unknown',
          timestamp: new Date(data.timestamp || 0)
        });
      } catch (error) {
        console.log(`[Cache Debug] Corrupted entry: ${key}`);
      }
    }
  }
  
  if (cacheEntries.length === 0) {
    console.log('[Cache Debug] No cache entries found');
  } else {
    console.log(`[Cache Debug] Found ${cacheEntries.length} cache entries:`);
    cacheEntries.forEach(entry => {
      console.log(`  - "${entry.title}" by "${entry.author}" (${entry.timestamp.toLocaleString()})`);
    });
  }
}

// Initialize cache cleanup on module load
clearExpiredCache();
