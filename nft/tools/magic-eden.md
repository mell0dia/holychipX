# Magic Eden

## What It Is
Magic Eden is the largest NFT marketplace on Solana (and also supports Ethereum, Polygon, Bitcoin Ordinals). It's where buyers discover, bid on, and purchase NFTs. Think of it as the "Amazon for NFTs" on Solana.

## Why We Chose It
- **#1 Solana marketplace** — ~90% of Solana NFT volume
- **Compressed NFT support** — supports cNFTs (critical for our scale)
- **Creator tools** — launchpad, collection pages, analytics
- **Free to list** — only 2% fee on sales
- **API available** — can pull listings into holy-chip.com/nfts.html
- **No approval needed for standard listings** — can list immediately after minting

## Setup

### 1. Connect Wallet
- Go to [magiceden.io](https://magiceden.io)
- Click "Connect Wallet" → select Phantom
- Approve the connection in Phantom

### 2. Creator Hub
- Navigate to Magic Eden Creator Hub
- Connect wallet
- Fill in creator profile:
  - Project name: Holy Chip
  - Description: AI-generated characters from the binary universe
  - Profile image: Holy Chip logo
  - Links: holy-chip.com, social media

### 3. Create a Collection
- Creator Hub → New Collection
- Collection details:
  - Name: "Holy Chip" (or per-series names like "Holy Chip: Neon Series")
  - Symbol: HCHIP
  - Description, banner image, profile image
  - Royalty: 5% (industry standard, goes to your wallet)

### 4. List NFTs
- After minting, NFTs appear in your Phantom wallet
- On Magic Eden: My Items → select NFT → List
- Set price in SOL
- Confirm transaction in Phantom

## API (for website integration)

### Collection Listings
```
GET https://api-mainnet.magiceden.dev/v2/collections/{symbol}/listings
```

### Collection Stats
```
GET https://api-mainnet.magiceden.dev/v2/collections/{symbol}/stats
```

### Single NFT Details
```
GET https://api-mainnet.magiceden.dev/v2/tokens/{mint_address}
```

### Rate Limits
- Public API: 120 requests/minute
- No API key required for read operations
- Sufficient for holy-chip.com traffic

## Cost
- **Listing:** Free
- **Seller fee:** 2% of sale price (deducted at sale time)
- **Royalties:** You set % (recommend 5%) — earned on every resale
- **Example:** Sell NFT for 1 SOL → you receive 0.98 SOL (after 2% ME fee). On resale at 2 SOL → you earn 0.10 SOL royalty (5%)

## Alternatives Considered
| Marketplace | Why Not |
|-------------|---------|
| Tensor | Good for trading, less for creators/collections |
| OpenSea | Primarily Ethereum, Solana support is secondary |
| Rarible | Lower Solana volume |
| Self-hosted | Too complex, no discovery/traffic |

## Notes
- Magic Eden Launchpad is available for bigger drops (requires application)
- Consider applying for "Verified Collection" status after establishing sales history
- Magic Eden supports "Buy Now" and auction formats
- Mobile app available for managing listings on the go
