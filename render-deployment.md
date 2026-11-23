# Labhya Web App — Render Deployment Guide

## Overview
The Labhya app is a **static single-page application** (HTML + Vanilla JS) that runs entirely in the browser. No backend, no build step, no server-side code.

**Status**: ✅ Ready for Render deployment

---

## ✅ Pre-Deployment Checklist

| Item | Status | Notes |
|------|--------|-------|
| Git repo initialized | ✅ | `/home/meghana/think/` |
| Files committed | ✅ | `index.html` (107KB) + `README.txt` (158B) + `technical-documentation.html` |
| GitHub remote set | ✅ | `https://github.com/meghanameghu970-beep/labhya-meghu.git` |
| TailwindCSS CDN | ✅ | `https://cdn.tailwindcss.com/3.4.17` |
| Google Fonts CDN | ✅ | `Inter` font family |
| Viewport meta tag | ✅ | `<meta name="viewport" content="width=device-width, initial-scale=1.0">` |
| DOCTYPE & charset | ✅ | `<!DOCTYPE html><meta charset="UTF-8">` |
| No build step required | ✅ | Pure client-side, CDN dependencies |
| localStorage persistence | ✅ | Works in production |
| 5 languages supported | ✅ | English, Hindi, Kannada, Tamil, Telugu |
| 26 screens (19 onboarding + 7 dashboard) | ✅ | Client-side routing via `goTo()` |

---

## 📋 Render Deployment Steps

### 1. Connect GitHub Repository
1. Log in to [Render.com](https://render.com)
2. Click **New +** → **Web Service**
3. Connect your GitHub account (if not already)
4. Select repository: `meghanameghu970-beep/labhya-meghu`

### 2. Service Configuration
| Setting | Value |
|---------|-------|
| **Name** | `labhya-meghu` (or your preference) |
| **Environment** | `Static` |
| **Build Command** | `echo "No build step required"` |
| **Publish Directory** | `.` (root directory) |
| **Start Command** | *(leave blank for static sites)* |

### 3. Essential Environment Variables (Optional)
The app works without environment variables since all dependencies are CDN-linked. If you need to configure anything:
- `LANG_CODE` — Default language ('en', 'hi', 'kn', 'ta', 'te')
- Not required for prototype

### 4. Deploy
1. Click **Create Web Service**
2. Render will detect `index.html` in the root and serve it as a static site
3. Wait 1-2 minutes for the first deploy
4. Once live, you'll get a URL like `https://labhya-meghu.onrender.com`

---

## 🔧 Why This Works on Render

| Feature | How It Works |
|---------|-------------|
| **TailwindCSS** | Loaded from `https://cdn.tailwindcss.com/3.4.17` — no installation needed |
| **Google Fonts** | `Inter` font loaded from `https://fonts.googleapis.com` — instant rendering |
| **localStorage** | Persists across sessions even after deploy restart |
| **Client-side routing** | `goTo(screenId)` updates UI without page reloads |
| **No backend** | All data (schemes, profiles, translations) is embedded in `index.html` or stored in `localStorage` |

---

## 📦 Files in the Git Repo

```
labhya-meghu/ (GitHub repo)
├── index.html          # Main app (107KB, 1824 lines)
├── README.txt          # App description (158B)
└── technical-documentation.html  # Full tech docs (22KB)
```

---

## 🌐 Post-Deployment Verification

After deploy, verify:

| Check | Expected Result |
|-------|----------------|
| **Page loads** | `https://<your-service>.onrender.com` shows Labhya dashboard |
| **Language selector** | Can switch between EN/HI/KN/TA/TE |
| **Mobile OTP flow** | Enter mobile → Get OTP → Verify → Dashboard |
| **Returning user** | On second visit, goes directly to dashboard (profile persisted in localStorage) |
| **DigiLocker** | Connect/Discuss document verification works |
| **Scheme search** | Find schemes by category/keyword works |
| **Eligibility check** | Filters schemes based on user profile (gender, occupation, state) |

---

## ⚠️ Known Prototype Limitations (Not Blockers for Deployment)

| Limitation | Workaround |
|------------|------------|
| **Mock OTP** | `verifyOtp()` uses hardcoded mock OTP — fine for prototype |
| **localStorage scoped** | Each user's device/browser has independent state |
| **No user accounts** | Authentication via mobile number + localStorage only |
| **Scheme data static** | 12 hardcoded schemes — easy to extend later |
| **No backend** | All data embedded; suitable for MVP/prototype |

---

## 📈 Scaling Considerations (Future)

If you need to expand beyond the prototype:

| Feature | Approach |
|---------|----------|
| **Dynamic scheme data** | Connect to a simple Node/Python API |
| **User accounts** | Add Supabase/Firebase auth + backend persistence |
| **Custom domains** | Map `labhya.yourdomain.com` in Render settings |
| **Analytics** | Add Plausible or Google Analytics (client-side only) |
| **A/B testing** | Feature flags via environment variables |

---

## ✅ Final Check

```bash
# Verify local deployment works before Render
cd /home/meghana/think
python3 -m http.server 3000  # open http://localhost:3000

# Or open directly
open /home/meghana/think/index.html  # in your browser
```

**The app is ready for Render deployment.** All files are committed, the GitHub repo is synced, and the static site configuration requires zero build steps.