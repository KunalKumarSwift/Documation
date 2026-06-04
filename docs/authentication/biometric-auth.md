# Biometric Authentication

## Overview
The app supports Face ID and Touch ID for authentication. Biometric auth is handled via `LocalAuthentication` framework with a multi-layer fallback strategy.

## Fallback Chain
1. **Face ID** → primary method on supported devices
2. **Touch ID** → primary method on older devices
3. **Device PIN** → system fallback when biometric fails 3 times
4. **Password** → explicit user choice or when device PIN is disabled
5. **Session expiry** → force full re-auth after 24 hours idle

## Why Face ID can fail
- Mask or sunglasses blocking facial features
- Dirty sensor
- 5 failed attempts (lockout)
- After device restart
- When `LAContext.canEvaluatePolicy` returns false

## Implementation
```swift
let context = LAContext()
var error: NSError?

guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
    // Fall back to device passcode
    authenticateWithPasscode()
    return
}

context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                        localizedReason: "Authenticate to access your account") { success, error in
    if success {
        handleAuthSuccess()
    } else {
        handleBiometricFailure(error)
    }
}
```

## Security Notes
- Biometric data never leaves the device Secure Enclave
- Session tokens are stored in Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`
- Failed attempts are logged for fraud detection (count only, not timing)
