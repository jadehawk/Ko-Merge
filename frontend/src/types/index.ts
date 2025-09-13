export interface Book {
  id: number;
  title: string;
  total_read_time: number;
  md5: string;
  authors?: string;
  series?: string;
}

export interface MergeGroup {
  keep_id: number;
  merge_ids: number[];
}

export interface SessionData {
  session_id: string;
  books: Book[];
  merge_groups: [number, number[]][];
}

export interface ApiResponse<T = any> {
  message?: string;
  data?: T;
  error?: string;
}

export interface UploadResponse {
  session_id: string;
  message: string;
}

export interface BooksResponse {
  books: Book[];
  merge_groups: [number, number[]][];
}

export interface MergeResponse {
  message: string;
  download_filename: string;
}

export interface ResultResponse {
  books: Book[];
}

/**
 * Rich book metadata from Google Books or OpenLibrary APIs
 * Contains detailed information beyond basic book data
 */
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

/**
 * API response for book details endpoint
 * Returns rich metadata or error information
 */
export interface BookDetailsResponse {
  success: boolean;
  metadata?: BookMetadata;
  error?: string;
}

/**
 * Cover option with source and URL information
 * Used for cover selection functionality
 */
export interface CoverOption {
  url: string;
  source: 'google_books' | 'openlibrary' | 'amazon' | 'generated';
  size: 'small' | 'medium' | 'large';
}

/**
 * API response for cover options endpoint
 * Returns available cover images for a book
 */
export interface CoverOptionsResponse {
  success: boolean;
  covers?: CoverOption[];
  error?: string;
}
