# Payment Transfer Flow

## Overview
Interac e-Transfer and internal account transfers use the same orchestration pattern with different backend services.

## Transfer Orchestration
```
iOS App → BFF /transfer → [parallel: fraud-check + balance-check]
                        → debit source account
                        → credit destination account  
                        → send confirmation notification
```

## Idempotency
Every transfer request includes a client-generated `idempotency_key` (UUID v4). The backend deduplicates on this key for 24 hours. If the network drops after debit but before credit, the backend automatically completes the transfer on retry.

## Transfer Limits
| Type | Daily limit | Per transaction |
|------|-------------|-----------------|
| Interac e-Transfer | $3,000 | $1,000 |
| Internal transfer | $50,000 | $25,000 |
| Wire transfer | $100,000 | $50,000 |

## Error Handling
- `INSUFFICIENT_FUNDS` → show balance, offer overdraft if eligible
- `FRAUD_HOLD` → show generic "transfer unavailable" + support number (do not reveal fraud signal)
- `LIMIT_EXCEEDED` → show limit details and upgrade path
- `RECIPIENT_NOT_FOUND` → suggest verifying email/phone
