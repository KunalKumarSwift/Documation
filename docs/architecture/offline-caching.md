# Offline Caching Strategy

## Decision: Core Data over Realm (ADR-012)
We chose Core Data for offline caching after evaluating Core Data, Realm, and SQLite directly.

### Why Core Data won
- **No third-party dependency**: Realm adds 10MB to binary size and has a separate update lifecycle
- **SwiftUI integration**: Core Data has first-class `@FetchRequest` support in SwiftUI
- **Team familiarity**: 80% of iOS team already knew Core Data from previous projects
- **Apple support**: Long-term support guaranteed, no vendor risk

### Why Realm lost
- Binary size increase
- Separate threading model conflicts with our async/await patterns
- License changes in 2023 added uncertainty

## What we cache
- Account balances (TTL: 5 minutes)
- Transaction history last 30 days (TTL: 1 hour)
- User profile and preferences (TTL: 24 hours)
- Offer cards (TTL: 15 minutes)

## Cache invalidation
Push notifications with `content-available: 1` trigger background refresh. If offline, stale cache is shown with a "last updated" timestamp.
