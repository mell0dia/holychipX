# Phantom Wallet

## What It Is
Phantom is the most popular Solana wallet. It's a browser extension (Chrome, Firefox, Brave, Edge) and mobile app that stores your SOL, signs transactions, and interacts with Solana dApps like Magic Eden.

## Why We Chose It
- **Market leader** on Solana — used by ~90% of Solana NFT traders
- **Magic Eden integration** — connects directly, no extra steps
- **Built-in NFT gallery** — view your minted NFTs in-wallet
- **Multi-chain** — also supports Ethereum, Polygon, Bitcoin (future flexibility)
- **Free** — no cost to use

## Setup

### 1. Install
- Go to [phantom.app](https://phantom.app)
- Click "Download" → install browser extension
- Or install mobile app (iOS/Android)

### 2. Create Wallet
- Open Phantom → "Create New Wallet"
- **CRITICAL:** Write down 12-word seed phrase on paper. Never store digitally. Never share.
- Set a strong password for the extension

### 3. Fund with SOL
- Copy your wallet address (click address at top)
- Buy SOL on an exchange (Coinbase, Kraken, Binance)
- Send SOL to your Phantom address
- Start with ~1 SOL ($200) for initial minting

### 4. Switch to Devnet (for testing)
- Settings → Developer Settings → Change Network → Devnet
- Get free test SOL: Settings → Developer Settings → "Request Airdrop"
- Switch back to Mainnet when ready for real minting

### 5. Export Keypair (for CLI tools)
- Settings → Security & Privacy → Export Private Key
- Save as `id.json` for use with Solana CLI
- **Keep this file secure — it controls your wallet**

## Cost
- **Free** to install and use
- Only cost is SOL for transactions (fractions of a cent per tx)

## Alternatives Considered
| Wallet | Why Not |
|--------|---------|
| Solflare | Good but less Magic Eden integration |
| Backpack | Newer, less established |
| Ledger | Hardware wallet — good for cold storage later, but adds friction for minting |

## Notes
- Consider a Ledger hardware wallet later for storing high-value SOL/NFT holdings
- Phantom auto-detects NFTs in your wallet and displays them
- Can create multiple accounts within one wallet (useful for separating personal/business)
