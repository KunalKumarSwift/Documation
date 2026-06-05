# Runbook: Push Notifications Not Working

## Symptoms
- Users report not receiving push notifications
- Transaction alerts missing
- Marketing push campaigns showing 0 delivery

## Diagnostic Steps

### Step 1 — Check APNs certificate expiry
```bash
# Check current cert status
openssl x509 -in apns-cert.pem -noout -dates

# Alert fires when cert expires in < 30 days
# Renew via Apple Developer Portal → Certificates → Push Notification
```

### Step 2 — Check notification service health
```bash
curl https://notifications.internal/health
# Expected: {"status": "ok", "queue_depth": <100}
# If queue_depth > 1000: service is backed up, check SQS dead letter queue
```

### Step 3 — Check device token registration
- Open Datadog → Notifications dashboard → "Token registration failures"
- >1% failure rate suggests a client-side bug (usually after iOS update)
- Check `DeviceTokenManager.swift` for recent changes

### Step 4 — Test a direct APNs send
```bash
# Send test notification directly via APNs
python scripts/send_test_apns.py --device-token <token> --env prod
```

## Escalation
- P1 (>10% users affected): Page on-call, notify #ios-incidents
- P2 (1–10% users affected): Create Jira ticket, monitor hourly
- P3 (<1% users affected): Log in backlog, investigate next sprint

## Post-incident
Update this runbook with the root cause and fix within 48 hours.
