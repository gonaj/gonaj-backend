# Authentication API - Quick Reference

## Base URL
```
Development: http://localhost:8000/api
Production: https://api.gonaj.app/api
```

## Endpoints

### 🔐 Magic Link Authentication

#### Request Magic Link
```bash
POST /auth/magic-link
Content-Type: application/json

{
  "email": "user@example.com"
}

# Response: 200 OK
{
  "message": "If the email exists, a magic link has been sent",
  "email": "user@example.com"
}
```

#### Verify Magic Link
```bash
POST /auth/magic-link/verify
Content-Type: application/json

{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGci..."
}

# Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
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

### 🔑 Email/Password Login

```bash
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

# Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": { /* same as above */ }
}
```

### 🔄 Token Refresh

```bash
POST /auth/token/refresh
Content-Type: application/json

{
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000"
}

# Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
  "refresh_token": "660f9511-f3ac-52e5-b827-557766551111",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### 🚪 Logout

```bash
POST /auth/logout
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
Content-Type: application/json

{
  "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
  "revoke_all": false  # Optional: true to revoke all user tokens
}

# Response: 200 OK
{
  "message": "Logged out successfully",
  "revoked_count": 1
}
```

### 👤 Current User Profile

```bash
GET /auth/me
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...

# Response: 200 OK
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "user",
  "display_name": "User Name",
  "email_verified": true
}
```

### 🔗 Social Login (Google)

```bash
POST /auth/social/google/callback
Content-Type: application/json

{
  "code": "4/0AeanS0ZPT...",
  "state": "random-state-string"
}

# Response: 501 Not Implemented (Placeholder)
{
  "message": "Social authentication not yet implemented",
  "provider": "google"
}
```

## cURL Examples

### Request Magic Link
```bash
curl -X POST http://localhost:8000/api/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'
```

### Refresh Token
```bash
curl -X POST http://localhost:8000/api/auth/token/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

### Get Current User
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Logout
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid credentials"
}
```

### 401 Unauthorized / 403 Forbidden
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

## Token Lifetimes

- **Access Token (JWT)**: 15 minutes
- **Refresh Token (Opaque)**: 30 days
- **Magic Link**: 15 minutes

## Security Notes

1. **Access Tokens**: Short-lived, include in `Authorization: Bearer` header
2. **Refresh Tokens**: Single-use, rotated on every refresh
3. **Magic Links**: One-time use, 15-minute expiration
4. **Token Storage**: 
   - Web: localStorage or sessionStorage
   - Mobile: Secure storage (Keychain/EncryptedSharedPreferences)
5. **HTTPS Only**: Always use HTTPS in production
6. **Token Revocation**: Logout revokes refresh tokens server-side

## Testing

Run authentication tests:
```bash
cd backend
uv run python manage.py test api.tests.test_auth
```

Expected output:
```
Ran 22 tests in ~5s
OK
```
