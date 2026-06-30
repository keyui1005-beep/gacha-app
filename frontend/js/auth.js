import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const apiBase = 'https://gacha-app-9xkq.onrender.com';

const firebaseConfig = {
  apiKey: "AIzaSyA0a0VvIXGNC5z5AZf9cxwRntct_vElPZU",
  authDomain: "gacha-exchange.firebaseapp.com",
  projectId: "gacha-exchange",
  storageBucket: "gacha-exchange.firebasestorage.app",
  messagingSenderId: "843866663760",
  appId: "1:843866663760:web:b20e7f3dc0e7bfbe74da55"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
const provider = new GoogleAuthProvider();

let currentUserData = null;

// ★ここが原因でした！確実に export されています
export async function getAuthToken() {
  const user = auth.currentUser;
  if (user) {
    return await user.getIdToken();
  }
  return null;
}

export function getCurrentUser() {
  return currentUserData;
}

export async function loginWithGoogle() {
  return await signInWithPopup(auth, provider);
}

export async function logoutUser() {
  return await signOut(auth);
}

export function initAuth(onStateChangedCallback) {
  onAuthStateChanged(auth, async (user) => {
    if (user) {
      try {
        const token = await user.getIdToken();
        const res = await fetch(apiBase + '/users/', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            name: user.displayName || '名無し',
            prefecture: '未設定',
            email: user.email || ''
          })
        });
        if (res.ok) {
          currentUserData = await res.json();
        }
      } catch (err) {
        console.error("ユーザー同期エラー:", err);
      }
    } else {
      currentUserData = null;
    }
    
    if (onStateChangedCallback) {
      onStateChangedCallback(currentUserData, user);
    }
  });
}