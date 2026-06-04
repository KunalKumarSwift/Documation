# Session Management

## Token Strategy
- **Access token**: JWT, 15-minute expiry, stored in memory only
- **Refresh token**: Opaque, 30-day expiry, stored in Keychain
- **Session token**: 24-hour idle timeout, reset on any user action

## Token Storage
| Token | Storage | Why |
|-------|---------|-----|
| Access token | In-memory only | Shortest lived, no persistence needed |
| Refresh token | Keychain | Secure enclave backed, survives app restart |
| Device fingerprint | Keychain | Used for fraud signal, not authentication |

## Refresh Flow
When the access token expires, the app automatically:
1. Calls `POST /auth/refresh` with the refresh token
2. Receives new access + refresh token pair
3. Updates in-memory access token
4. Updates Keychain refresh token
5. Retries the original failed request

If refresh fails (expired or revoked), the user is sent to the login screen.

## Session Expiry Events
- **Idle timeout**: No user interaction for 5 minutes → soft lock (biometric re-auth)
- **Background timeout**: App backgrounded for 24 hours → full re-auth required
- **Force logout**: Server revokes refresh token → next API call fails, redirects to login
