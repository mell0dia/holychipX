# Metaplex Candy Machine v3 + Sugar CLI

## What It Is
Candy Machine is Metaplex's on-chain program for minting NFT collections on Solana. **Sugar CLI** is the command-line tool that interacts with it. Together, they let you bulk-mint hundreds or thousands of NFTs from a folder of images + metadata.

## Why We Chose It
- **Industry standard** — used by 90%+ of Solana NFT collections
- **Compressed NFTs (cNFTs)** — mint 1000 NFTs for ~$1 instead of ~$2000
- **Sugar CLI** — simple command-line workflow: upload → deploy → mint
- **Configurable** — set price, dates, allowlists, payment options
- **Free to use** — only pay Solana transaction fees

## How cNFTs Work
Regular NFTs store each token as a separate on-chain account (~0.01 SOL each). Compressed NFTs use **Merkle trees** to store data off-chain with on-chain proofs, reducing cost by ~1000x.

| Type | Cost per NFT | 200 NFTs |
|------|-------------|----------|
| Regular NFT | ~0.01 SOL ($2) | ~2 SOL ($400) |
| Compressed NFT | ~0.0005 SOL ($0.10) | ~0.1 SOL ($20) |

## Setup

### 1. Install Sugar CLI
```bash
bash <(curl -sSf https://sugar.metaplex.com/install.sh)
```
Verify:
```bash
sugar --version
```

### 2. Configure Wallet
```bash
# Use existing Phantom keypair
solana config set --keypair /path/to/id.json

# Or generate new keypair
solana-keygen new --outfile ~/holy-chip-wallet.json
solana config set --keypair ~/holy-chip-wallet.json
```

### 3. Prepare Assets Folder
```
assets/
├── 0.png
├── 0.json
├── 1.png
├── 1.json
├── 2.png
├── 2.json
└── collection.png
└── collection.json
```

Each JSON follows Metaplex metadata standard:
```json
{
  "name": "Holy Chip #001",
  "symbol": "HCHIP",
  "description": "AI-generated Holy Chip character.",
  "image": "0.png",
  "attributes": [
    { "trait_type": "Character", "value": "Chip_0" },
    { "trait_type": "Rarity", "value": "Common" }
  ],
  "properties": {
    "files": [{ "uri": "0.png", "type": "image/png" }],
    "creators": [{ "address": "YOUR_WALLET_ADDRESS", "share": 100 }]
  }
}
```

### 4. Create Sugar Config
```bash
sugar config create
```
This generates `config.json`:
```json
{
  "price": 0.5,
  "number": 200,
  "symbol": "HCHIP",
  "sellerFeeBasisPoints": 500,
  "goLiveDate": "2026-03-01T00:00:00Z",
  "creators": [
    { "address": "YOUR_WALLET", "share": 100 }
  ],
  "uploadMethod": "bundlr",
  "isMutable": true
}
```
> **Note:** `"bundlr"` is the upload method name for Irys (formerly Bundlr). Sugar uploads images + metadata to Arweave via Irys, paid directly from your SOL wallet. No API keys or external accounts needed.

### 5. Upload → Deploy → Mint
```bash
# Upload images + metadata to Arweave via Irys
sugar upload

# Deploy Candy Machine on-chain
sugar deploy

# Verify everything is correct
sugar verify

# Mint all NFTs (or specific number)
sugar mint --number 10

# Mint as compressed NFTs
sugar mint --number 200 --compressed
```

## Key Commands
```bash
sugar config create     # Interactive config setup
sugar validate          # Check assets folder structure
sugar upload            # Upload to Arweave via Irys
sugar deploy            # Create Candy Machine on-chain
sugar verify            # Verify deployment
sugar mint              # Mint NFTs
sugar show              # Show Candy Machine details
sugar withdraw          # Withdraw SOL from Candy Machine
sugar collection set    # Set collection for NFTs
```

## Cost
- **Sugar CLI:** Free
- **Candy Machine creation:** ~0.02 SOL one-time
- **Upload to Arweave via Irys:** ~0.001 SOL per file (paid from wallet, no subscription)
- **Minting (cNFTs):** ~0.0005 SOL per NFT
- **Total for 200 cNFTs:** ~0.5 SOL ($100) including storage + minting

## Alternatives Considered
| Tool | Why Not |
|------|---------|
| Metaplex JS SDK | More flexible but requires custom code; Sugar CLI is simpler |
| Crossmint | Easy but expensive ($0.35/mint + fees) |
| NFT.storage + manual | No bulk minting workflow |
| Solana Token Program directly | Too low-level, would need to build everything from scratch |

## Notes
- Always test on Devnet first: `solana config set --url devnet`
- Sugar CLI handles Arweave upload automatically via Irys — no extra accounts or API keys
- Can update metadata after minting if `isMutable: true`
- Candy Machine can be configured with guards (allowlists, start dates, payment tokens)
- For drops > 10,000 NFTs, consider Bubblegum program directly for cNFTs
