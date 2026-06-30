import { getAuthToken } from './auth.js';

export const apiBase = 'https://gacha-app-9xkq.onrender.com';

// 認証トークンを付与する共通fetchラッパー
export async function fetchWithAuth(endpoint, options = {}) {
  const token = await getAuthToken();
  
  if (token) {
    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${token}`;
  }
  
  return fetch(apiBase + endpoint, options);
}