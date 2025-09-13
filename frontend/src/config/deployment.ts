/**
 * Deployment Configuration for Ko-Merge Frontend
 * 
 * This module handles flexible deployment configuration using environment variables
 * that can be set at build time or runtime. It supports various deployment scenarios:
 * - Root domain deployment (https://mydomain.com)
 * - Subfolder deployment (https://mydomain.com/ko-merge)
 * - Development (http://localhost:8000)
 * - Custom ports and protocols
 */

// Build-time environment variables (injected by Vite define)
const BUILD_TIME_CONFIG = {
  BASE_URL: (globalThis as any).__VITE_PUBLIC_BASE_URL__ || '',
  SUBFOLDER_PATH: (globalThis as any).__VITE_PUBLIC_SUBFOLDER_PATH__ || '',
  USE_SUBFOLDER: (globalThis as any).__VITE_USE_SUBFOLDER__ === 'true',
};

/**
 * Normalize and validate deployment configuration
 */
function getDeploymentConfig() {
  // Always start with runtime detection from current URL
  const currentUrl = window.location;
  let baseUrl = `${currentUrl.protocol}//${currentUrl.host}`;
  let subfolderPath = '';
  let useSubfolder = false;
  
  // Check if we're in a subfolder by examining the pathname
  const pathname = currentUrl.pathname;
  const pathSegments = pathname.split('/').filter(segment => segment);
  
  // If there are path segments, we're likely in a subfolder
  if (pathSegments.length > 0) {
    // Use the first path segment as the subfolder
    const detectedSubfolder = pathSegments[0];
    
    // Common patterns that indicate we're in a subfolder deployment
    const isSubfolderDeployment = 
      detectedSubfolder && 
      detectedSubfolder !== 'api' && 
      detectedSubfolder !== 'static' &&
      detectedSubfolder !== 'assets';
    
    if (isSubfolderDeployment) {
      subfolderPath = `/${detectedSubfolder}`;
      useSubfolder = true;
    }
  }
  
  // Override with build-time config if available and not empty
  if (BUILD_TIME_CONFIG.BASE_URL.trim()) {
    baseUrl = BUILD_TIME_CONFIG.BASE_URL.trim();
  }
  if (BUILD_TIME_CONFIG.SUBFOLDER_PATH.trim()) {
    subfolderPath = BUILD_TIME_CONFIG.SUBFOLDER_PATH.trim();
    useSubfolder = BUILD_TIME_CONFIG.USE_SUBFOLDER;
  }

  // Normalize base URL
  if (baseUrl) {
    // Add protocol if missing
    if (!baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
      // Smart protocol detection
      if (baseUrl.includes('localhost') || 
          baseUrl.includes('127.0.0.1') || 
          baseUrl.includes(':80') ||
          baseUrl.startsWith('192.168.') ||
          baseUrl.startsWith('10.') ||
          baseUrl.startsWith('172.')) {
        baseUrl = `http://${baseUrl}`;
      } else {
        baseUrl = `https://${baseUrl}`;
      }
    }
    // Remove trailing slash
    baseUrl = baseUrl.replace(/\/$/, '');
  } else {
    // Default for development
    baseUrl = 'http://localhost:8000';
  }

  // Normalize subfolder path
  if (subfolderPath) {
    // Add leading slash if missing
    if (!subfolderPath.startsWith('/')) {
      subfolderPath = `/${subfolderPath}`;
    }
    // Remove trailing slash
    subfolderPath = subfolderPath.replace(/\/$/, '');
    // If it becomes just "/", treat as root deployment
    if (subfolderPath === '/') {
      subfolderPath = '';
      useSubfolder = false;
    }
  }

  // Determine API base path (ensure no double slashes)
  const apiBasePath = useSubfolder ? `${subfolderPath}/api` : '/api';

  const config = {
    baseUrl,
    subfolderPath,
    useSubfolder,
    apiBasePath,
    // Full API URL for external requests
    fullApiUrl: `${baseUrl}${apiBasePath}`,
  };

  // Log configuration in development
  if ((import.meta as any).env?.DEV) {
    console.log('=== Frontend Deployment Configuration ===');
    console.log('Base URL:', config.baseUrl);
    console.log('Subfolder Path:', config.subfolderPath || '(root deployment)');
    console.log('Use Subfolder:', config.useSubfolder);
    console.log('API Base Path:', config.apiBasePath);
    console.log('Full API URL:', config.fullApiUrl);
    console.log('Build-time config:', BUILD_TIME_CONFIG);
    console.log('==========================================');
  }

  return config;
}

// Export the configuration
export const DEPLOYMENT_CONFIG = getDeploymentConfig();

// Export individual values for convenience
export const { baseUrl, subfolderPath, useSubfolder, apiBasePath, fullApiUrl } = DEPLOYMENT_CONFIG;

// Export a function to get the API base path (for compatibility)
export function getApiBasePath(): string {
  return apiBasePath;
}

// Export a function to build full URLs
export function buildUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${subfolderPath}${cleanPath}`;
}

// Export a function to build API URLs
export function buildApiUrl(endpoint: string): string {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  // Ensure no double slashes by checking if apiBasePath already ends with /
  if (apiBasePath.endsWith('/')) {
    return `${apiBasePath}${cleanEndpoint}`;
  } else {
    return `${apiBasePath}/${cleanEndpoint}`;
  }
}
