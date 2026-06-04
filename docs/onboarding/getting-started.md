# Getting Started — iOS Platform Team

## Welcome
This guide gets you from zero to submitting your first PR in 1 day.

## Prerequisites
- Mac with Apple Silicon (M1 or later recommended)
- Xcode 15.2+ (install from Mac App Store, takes 30–45 min)
- Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

## Repository Setup
```bash
# Clone the main app repo
git clone git@github.com:scotiabank/ios-banking-app.git
cd ios-banking-app

# Install dependencies
brew install mint
mint bootstrap

# Install Ruby gems (for Fastlane)
bundle install

# Open in Xcode
open BankingApp.xcworkspace
```

## Running the App
- Select scheme `BankingApp-Dev`
- Select simulator iPhone 15 Pro
- Press Cmd+R to build and run
- Use test credentials from 1Password vault "iOS Dev Credentials"

## Team Structure
| Squad | Slack Channel | Owns |
|-------|---------------|------|
| Platform | #ios-platform | Architecture, CI/CD, shared frameworks |
| Accounts | #ios-accounts | Account summary, transaction history |
| Payments | #ios-payments | Transfers, bill pay, Interac |
| Onboarding | #ios-onboarding | Registration, KYC, biometric setup |

## First Week Checklist
- [ ] Set up dev environment (this guide)
- [ ] Read architecture overview in `docs/architecture/`
- [ ] Complete security training in Workday
- [ ] Shadow a code review with your buddy
- [ ] Submit your first PR (pick a "good first issue" label ticket)
