# BFF Layer Architecture

## Overview
The Backend For Frontend (BFF) layer is a dedicated API gateway that sits between the iOS app and the microservices backend. It aggregates multiple service calls into a single optimised response for mobile.

## Why BFF?
Before the BFF layer, the iOS app made 12–15 individual API calls on app launch, causing N+1 network problems. The BFF reduced this to 2–3 calls, cutting app launch latency by 70%.

## Design Decisions
- **ADR-003**: Chose BFF over GraphQL due to simpler iOS team ownership and easier caching strategy
- The BFF owns response shaping — iOS engineers define the contract, backend implements it
- Caching at the BFF layer uses Redis with a 60-second TTL for non-sensitive data

## Endpoints
- `GET /bff/v2/home` — home screen aggregation (account summary + offers + notifications)
- `GET /bff/v2/account/{id}` — account detail + transaction history + pending transfers
- `POST /bff/v2/transfer` — orchestrates fraud check → balance check → debit → credit

## Performance Targets
| Metric | Target | Current |
|--------|--------|---------|
| P50 latency | <200ms | 145ms |
| P99 latency | <800ms | 620ms |
| App launch calls | ≤3 | 2 |
