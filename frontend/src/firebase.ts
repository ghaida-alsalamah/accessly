import { initializeApp, getApps } from "firebase/app";
import { connectAuthEmulator, getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail, signOut } from "firebase/auth";

const provider = import.meta.env.VITE_IDENTITY_PROVIDER || "postgres";
if (!["postgres", "firebase"].includes(provider)) throw new Error("Invalid identity provider.");
export const firebaseEnabled = provider === "firebase";
let logoutPending: Promise<void> | undefined;
let authInstance: ReturnType<typeof getAuth> | undefined;
export function firebaseAuth() {
  if (!authInstance) {
    const app = getApps()[0] || initializeApp({
      apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyBM8PLmaYjkBd8yQoN53PBmfxMAL2cKt_g",
      authDomain: "accey-80215.firebaseapp.com",
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "accey-80215",
      storageBucket: "accey-80215.firebasestorage.app",
      messagingSenderId: "278973770920",
      appId: "1:278973770920:web:bf693995efd7506af8e69d",
    });
    authInstance = getAuth(app);
    if (import.meta.env.DEV && import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL) {
      connectAuthEmulator(authInstance, import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL);
    }
  }
  return authInstance;
}
export async function createPasswordAccount(email: string, password: string) {
  await logoutPending;
  return (await createUserWithEmailAndPassword(firebaseAuth(), email.trim(), password)).user;
}
export async function loginWithPassword(email: string, password: string) {
  await logoutPending;
  return (await signInWithEmailAndPassword(firebaseAuth(), email.trim(), password)).user;
}
export async function resetPassword(email: string) {
  await sendPasswordResetEmail(firebaseAuth(), email.trim(), { url: `${window.location.origin}/` });
}
export function authErrorMessage(error: unknown): string {
  const code = (error as { code?: string })?.code;
  const messages: Record<string, string> = {
    "auth/invalid-email": "Enter a valid email address.",
    "auth/weak-password": "Password must contain at least 6 characters.",
    "auth/password-does-not-meet-requirements": "Use a stronger password that meets the account password requirements.",
    "auth/email-already-in-use": "An account with this email already exists. Log in or use Forgot password? to set or reset its password.",
    "auth/invalid-credential": "Incorrect email or password.",
    "auth/wrong-password": "Incorrect email or password.",
    "auth/user-not-found": "Incorrect email or password.",
    "auth/too-many-requests": "Too many attempts. Please wait and try again.",
    "auth/network-request-failed": "Unable to connect. Check your connection and try again.",
    "auth/user-disabled": "This account has been disabled.",
  };
  return code ? messages[code] || "Authentication failed. Please try again." : error instanceof Error ? error.message : "Please try again.";
}
export async function firebaseToken() {
  await logoutPending;
  const auth = firebaseAuth();
  await auth.authStateReady();
  return auth.currentUser ? auth.currentUser.getIdToken() : null;
}
export function firebaseSignOut() {
  logoutPending = signOut(firebaseAuth());
  return logoutPending;
}
