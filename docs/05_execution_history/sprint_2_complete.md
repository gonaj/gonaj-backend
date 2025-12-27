# Sprint-2 Completion Summary: Headless Authentication System

## Overview
Implemented a comprehensive headless authentication system with JWT access tokens, opaque refresh tokens with rotation, magic link passwordless authentication, and social login backend support.

## Implementation Status: ✅ COMPLETE

### Components Implemented

#### 1. **Models** (`accounts/models.py`)
- `RefreshToken` model with:
  - SHA256 token hashing for security
  - Single-use rotation mechanism
  - Replay attack detection via `replaced_by` tracking
  - Device fingerprinting support
  - Automatic expiration (30 days default)
  - Methods: `hash_token()`, `create_for_user()`, `rotate()`, `revoke()`, `is_valid()`, `is_expired()`

#### 2. **Token Utilities** (`api/utils/tokens.py`)
- `create_access_token()` - Generate short-lived JWT access tokens (15 min)
- `create_refresh_token()` - Generate long-lived opaque refresh tokens (30 days)
- `rotate_refresh_token()` - Single-use rotation with new token generation
- `validate_access_token()` - JWT verification and payload extraction
- `get_user_from_token()` - Retrieve user from JWT payload
- `get_jwt_secret()` - Centralized secret key management

#### 3. **Magic Link Authentication** (`accounts/email/magic_link.py`)
- `MagicLinkTokenGenerator` - Django TimestampSigner wrapper (15 min expiration)
- `generate_magic_link_token()` - Token creation for email
- `send_magic_link_email()` - HTML/text email sending with proper formatting

#### 4. **Django-Allauth Integration** (`accounts/allauth_adapter.py`)
- `HeadlessAccountAdapter` - Custom adapter for headless account management
- `HeadlessSocialAccountAdapter` - Social login adapter for Google OAuth2

#### 5. **Serializers** (`api/serializers/auth.py`)
- `MagicLinkRequestSerializer` - Email validation and normalization
- `MagicLinkVerifySerializer` - Token validation
- `LoginSerializer` - Email/password credentials
- `TokenRefreshSerializer` - Refresh token input
- `TokenRevokeSerializer` - Optional refresh token and revoke_all flag
- `UserProfileSerializer` - User profile data (id, email, username, display_name, email_verified)
- `SocialCallbackSerializer` - OAuth2 code and state (placeholder)

#### 6. **API Views** (`api/views/auth.py`)
- `JWTAuthentication` - Custom DRF authentication class for Bearer tokens
- `MagicLinkRequestView` - POST endpoint to send magic link via email
- `MagicLinkVerifyView` - POST endpoint to verify magic link and return tokens
- `LoginView` - POST endpoint for email/password login
- `LogoutView` - POST endpoint to revoke refresh tokens
- `TokenRefreshView` - POST endpoint for token rotation
- `TokenRevokeView` - POST endpoint for explicit token revocation
- `MeView` - GET endpoint for current user profile
- `SocialCallbackView` - POST endpoint for OAuth2 callbacks (placeholder)

#### 7. **URL Configuration** (`api/urls.py`)
All endpoints under `/api/auth/` prefix:
- `POST /api/auth/magic-link` - Request magic link
- `POST /api/auth/magic-link/verify` - Verify magic link
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/logout` - Logout (revoke tokens)
- `POST /api/auth/token/refresh` - Refresh access token
- `POST /api/auth/token/revoke` - Revoke refresh token
- `GET /api/auth/me` - Get current user profile
- `POST /api/auth/social/<provider>/callback` - Social login callback

#### 8. **Settings Configuration** (`backend/settings.py`)
- Added `django-allauth` apps and middleware
- REST Framework configuration with JSON-only parsers
- JWT settings (secret key, token lifetime)
- Email backend configuration (console for dev, SMTP for production)
- Allauth headless configuration
- Google OAuth2 provider settings
- Magic link token expiration settings

#### 9. **Migrations**
- `accounts/migrations/0001_initial.py` - RefreshToken model migration
- Applied successfully with all django-allauth migrations

#### 10. **Tests** (`api/tests/test_auth.py`)
Comprehensive test coverage with **22 passing tests**:

**Magic Link Tests (3):**
- ✅ Magic link request sends email
- ✅ Email normalization to lowercase
- ✅ Magic link verification creates new user
- ✅ Magic link verification for existing user

**Login Tests (4):**
- ✅ Successful login with correct credentials
- ✅ Login fails with wrong password
- ✅ Login fails with nonexistent email
- ✅ Login fails for inactive user

**Token Refresh Tests (4):**
- ✅ Successful token refresh
- ✅ Token rotation (single-use)
- ✅ Invalid token rejection
- ✅ Revoked token rejection

**Logout Tests (3):**
- ✅ Logout revokes specific token
- ✅ Logout revokes all user tokens
- ✅ Logout requires authentication

**User Profile Tests (3):**
- ✅ /me returns user profile
- ✅ /me requires authentication
- ✅ /me rejects invalid token

**Token Utility Tests (3):**
- ✅ Access token creation and JWT payload
- ✅ Refresh token creation and storage
- ✅ Refresh token rotation

**Social Login Tests (1):**
- ✅ Social callback placeholder returns 501

**Audit Logging:**
- ✅ All auth events logged to AuditLog (login, logout, magic link requests)

## Security Features

### Token Strategy
- **Access Tokens (JWT)**: 
  - Short-lived (15 minutes)
  - Stateless, verified via signature
  - Contains user metadata (id, email, username)
  - Used in Authorization: Bearer header

- **Refresh Tokens (Opaque)**:
  - Long-lived (30 days)
  - Server-side storage with SHA256 hashing
  - Single-use rotation on every refresh
  - Device tracking capability
  - Replay attack prevention via `replaced_by` chain

### Protection Mechanisms
1. **Token Rotation**: New refresh token on every use, old one marked as replaced
2. **Hashing**: Refresh tokens hashed before storage (SHA256)
3. **Replay Detection**: `replaced_by` field tracks token replacement chain
4. **Expiration**: Automatic token invalidation after timeout
5. **Revocation**: Manual token revocation via logout
6. **Device Tracking**: Optional device fingerprinting for security alerts
7. **Audit Logging**: All authentication events recorded with IP and user agent

## API Contracts

### POST /api/auth/magic-link
**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "If the email exists, a magic link has been sent",
  "email": "user@example.com"
}
```

### POST /api/auth/magic-link/verify
**Request:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "user",
    "display_name": "User Name",
    "email_verified": true
  }
}
```

### POST /api/auth/login
**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": { /* same as above */ }
}
```

### POST /api/auth/token/refresh
**Request:**
```json
{
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "660f9511-f3ac-52e5-b827-557766551111",
  "token_type": "Bearer",
  "expires_in": 900
}
```
*Note: New refresh token replaces old one (single-use rotation)*

### GET /api/auth/me
**Request Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "user",
  "display_name": "User Name",
  "email_verified": true
}
```

### POST /api/auth/logout
**Request Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Request Body (Optional):**
```json
{
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
  "revoke_all": false
}
```

**Response (200):**
```json
{
  "message": "Logged out successfully",
  "revoked_count": 1
}
```

## Frontend Integration Guide

### Web SPA (React/Vue/Angular)

#### Initial Setup
```javascript
// Configure API client
const API_BASE_URL = 'https://api.gonaj.app';

// Store tokens securely
function storeTokens(accessToken, refreshToken) {
  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('refresh_token', refreshToken);
}

function getAccessToken() {
  return localStorage.getItem('access_token');
}
```

#### Magic Link Flow
```javascript
// Step 1: Request magic link
async function requestMagicLink(email) {
  const response = await fetch(`${API_BASE_URL}/api/auth/magic-link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
  const data = await response.json();
  // Show success message to user
}

// Step 2: Verify magic link (from email link)
async function verifyMagicLink(token) {
  const response = await fetch(`${API_BASE_URL}/api/auth/magic-link/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
  const data = await response.json();
  storeTokens(data.access_token, data.refresh_token);
  // Redirect to dashboard
}
```

#### Email/Password Login
```javascript
async function login(email, password) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  storeTokens(data.access_token, data.refresh_token);
}
```

#### Authenticated Requests
```javascript
async function authenticatedFetch(url, options = {}) {
  const token = getAccessToken();
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (response.status === 401 || response.status === 403) {
    // Token expired, try refresh
    const refreshed = await refreshToken();
    if (refreshed) {
      // Retry request with new token
      return authenticatedFetch(url, options);
    } else {
      // Refresh failed, redirect to login
      window.location.href = '/login';
    }
  }
  
  return response;
}
```

#### Token Refresh
```javascript
async function refreshToken() {
  const refreshToken = localStorage.getItem('refresh_token');
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/token/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    const data = await response.json();
    storeTokens(data.access_token, data.refresh_token);
    return true;
  } catch (error) {
    return false;
  }
}
```

#### Logout
```javascript
async function logout() {
  const token = getAccessToken();
  const refreshToken = localStorage.getItem('refresh_token');
  
  await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ 
      refresh_token: refreshToken,
      revoke_all: true  // Revoke all user tokens
    })
  });
  
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.href = '/login';
}
```

### Mobile App (React Native/Flutter)

Use secure storage for tokens:
- **iOS**: Keychain
- **Android**: EncryptedSharedPreferences

```javascript
// React Native example with expo-secure-store
import * as SecureStore from 'expo-secure-store';

async function storeTokens(accessToken, refreshToken) {
  await SecureStore.setItemAsync('access_token', accessToken);
  await SecureStore.setItemAsync('refresh_token', refreshToken);
}

async function getAccessToken() {
  return await SecureStore.getItemAsync('access_token');
}
```

## Environment Variables

Add to `.env` or environment configuration:

```bash
# Django Secret Keys
DJANGO_SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=different-secret-for-jwt-signing

# Token Lifetimes
JWT_ACCESS_TOKEN_LIFETIME=900         # 15 minutes in seconds
REFRESH_TOKEN_LIFETIME_DAYS=30        # 30 days
MAGIC_LINK_TOKEN_MAX_AGE=900          # 15 minutes in seconds

# Email Configuration (Production)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@gonaj.app

# Frontend URLs
FRONTEND_EMAIL_CONFIRM_URL=https://app.gonaj.com/verify-email/{key}
FRONTEND_PASSWORD_RESET_URL=https://app.gonaj.com/reset-password/{key}

# Google OAuth2 (for social login)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Deployment Checklist

- [ ] Set all environment variables in production
- [ ] Change `DJANGO_SECRET_KEY` and `JWT_SECRET_KEY` to secure random values
- [ ] Configure production email backend (SMTP)
- [ ] Set up Google OAuth2 app credentials
- [ ] Update `FRONTEND_EMAIL_CONFIRM_URL` and `FRONTEND_PASSWORD_RESET_URL`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Test all authentication flows in staging
- [ ] Set up HTTPS/TLS for API endpoints
- [ ] Configure CORS for frontend domain
- [ ] Set up Redis for future rate limiting (optional)
- [ ] Monitor AuditLog for suspicious activity

## Next Steps (Sprint-3 Suggestions)

1. **Rate Limiting**
   - Implement rate limiting on auth endpoints
   - Use Django-ratelimit or Redis-based solution

2. **Email Verification Flow**
   - Send verification emails for new registrations
   - Restrict unverified users from certain actions

3. **Password Reset**
   - Implement forgot password flow
   - Token-based password reset via email

4. **2FA/MFA**
   - TOTP-based two-factor authentication
   - SMS-based verification (optional)

5. **Social Login Frontend**
   - Complete Google OAuth2 integration
   - Add Facebook, GitHub providers

6. **Account Management**
   - Change password endpoint
   - Change email endpoint
   - Delete account endpoint

7. **Session Management**
   - List active sessions/devices
   - Revoke specific sessions
   - Security alerts for new logins

## Test Results

```
Sprint-1 Tests: 32/32 PASSING ✅
Sprint-2 Tests: 22/22 PASSING ✅
Total: 54/54 PASSING ✅
```

## Files Created/Modified

### New Files (Sprint-2)
- `accounts/models.py` - RefreshToken model
- `accounts/email/magic_link.py` - Magic link utilities
- `accounts/allauth_adapter.py` - Allauth adapters
- `accounts/migrations/0001_initial.py` - RefreshToken migration
- `api/utils/tokens.py` - JWT and refresh token utilities
- `api/serializers/auth.py` - Authentication serializers
- `api/serializers/__init__.py` - Serializers package init
- `api/views/auth.py` - Authentication views
- `api/views/__init__.py` - Views package init
- `api/tests/test_auth.py` - Authentication tests

### Modified Files (Sprint-2)
- `pyproject.toml` - Added PyJWT, django-allauth[socialaccount], requests
- `backend/backend/settings.py` - Added allauth configuration, JWT settings, email settings
- `api/urls.py` - Added authentication endpoints

## Dependencies Added

```toml
[project]
dependencies = [
    "PyJWT==2.10.1",
    "django-allauth[socialaccount]==65.3.0",
    "requests>=2.32.0",
]
```

---

**Sprint-2 Status: ✅ COMPLETE**

All acceptance criteria met:
- ✅ JWT access tokens with 15-minute expiration
- ✅ Opaque refresh tokens with SHA256 hashing and rotation
- ✅ Magic link passwordless authentication
- ✅ Email/password login
- ✅ Token refresh with single-use rotation
- ✅ Logout with token revocation
- ✅ User profile endpoint
- ✅ Social login backend preparation
- ✅ Comprehensive test coverage
- ✅ Audit logging for all auth events
- ✅ Security best practices implemented
