import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Flexible deployment configuration for Vite
// Supports environment variables for different deployment scenarios
const getViteConfig = () => {
  // Get environment variables with defaults
  const subfolderPath = process.env.VITE_PUBLIC_SUBFOLDER_PATH || '';
  const useSubfolder = process.env.VITE_USE_SUBFOLDER === 'true';
  
  // For UnRaid and other deployment systems that don't pass build args,
  // we default to root path and let the frontend detect at runtime
  let basePath = '/';
  
  // Only use build-time configuration if explicitly provided
  if (useSubfolder && subfolderPath) {
    // Normalize subfolder path
    let normalizedPath = subfolderPath;
    if (!normalizedPath.startsWith('/')) {
      normalizedPath = '/' + normalizedPath;
    }
    if (!normalizedPath.endsWith('/')) {
      normalizedPath = normalizedPath + '/';
    }
    basePath = normalizedPath;
  }
  
  console.log('=== Vite Build Configuration ===');
  console.log('Raw Environment Variables:');
  console.log('  VITE_PUBLIC_SUBFOLDER_PATH:', process.env.VITE_PUBLIC_SUBFOLDER_PATH || '(not set)');
  console.log('  VITE_USE_SUBFOLDER:', process.env.VITE_USE_SUBFOLDER || '(not set)');
  console.log('Processed Values:');
  console.log('  Subfolder Path:', subfolderPath || '(root deployment)');
  console.log('  Use Subfolder:', useSubfolder);
  console.log('  Vite Base Path:', basePath);
  console.log('Note: If build-time vars are not set, frontend will detect deployment at runtime');
  console.log('================================');
  
  return {
    base: basePath,
  };
};

const { base } = getViteConfig();

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base,
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // Define environment variables that should be available at build time
  define: {
    // Make deployment config available to the frontend
    __VITE_PUBLIC_BASE_URL__: JSON.stringify(process.env.VITE_PUBLIC_BASE_URL || ''),
    __VITE_PUBLIC_SUBFOLDER_PATH__: JSON.stringify(process.env.VITE_PUBLIC_SUBFOLDER_PATH || ''),
    __VITE_USE_SUBFOLDER__: JSON.stringify(process.env.VITE_USE_SUBFOLDER || 'false'),
  },
})
