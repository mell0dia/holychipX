# Irys + Arweave (Primary Storage)

## What It Is
**Arweave** is a permanent, decentralized storage network. Unlike IPFS (which requires "pinning" to keep files available), data on Arweave is stored **forever** with a one-time payment. No subscriptions, no renewals.

**Irys** (formerly Bundlr) is the upload layer for Arweave. It accepts payments in SOL (and other tokens), bundles your data, and submits it to Arweave. Sugar CLI uses Irys under the hood when you run `sugar upload`.

## Why We Chose It
- **No subscriptions** — pay once from your SOL wallet, stored forever
- **Sugar CLI default** — built-in, no extra accounts or API keys needed
- **Truly permanent** — data guaranteed for 200+ years by Arweave's endowment model
- **NFT industry standard** — most Solana NFT collections use Arweave for storage
- **Simpler workflow** — `sugar upload` handles everything automatically
- **No file limits** — upload as many files as you want, just pay per file

## How It Works
```
sugar upload
    ↓
Images + metadata JSON files in assets/ folder
    ↓
Irys bundles files + deducts SOL from your wallet
    ↓
Data submitted to Arweave blockchain
    ↓
Permanent URLs: https://arweave.net/{transaction_id}
```

## Setup
**There is no setup.** Irys is built into Sugar CLI. When you run `sugar upload` with `"uploadMethod": "bundlr"` in your config, it:
1. Reads files from your `assets/` folder
2. Connects to Irys using your Solana wallet keypair
3. Deducts a small SOL fee per file
4. Uploads to Arweave
5. Returns permanent URLs that get embedded in your NFT metadata

### Sugar Config
```json
{
  "uploadMethod": "bundlr"
}
```
That's it. The `"bundlr"` method name is a legacy name — it uses Irys (which was renamed from Bundlr).

## Cost

### Per-File Pricing
Storage cost depends on file size. Typical NFT image costs:

| File Size | Cost per File | 200 Files |
|-----------|--------------|-----------|
| 100 KB (small PNG) | ~0.0005 SOL ($0.10) | ~0.1 SOL ($20) |
| 500 KB (medium PNG) | ~0.001 SOL ($0.20) | ~0.2 SOL ($40) |
| 2 MB (large PNG) | ~0.004 SOL ($0.80) | ~0.8 SOL ($160) |

> Each NFT needs 2 uploads: the image + the metadata JSON (~1 KB, negligible cost).

### Cost Comparison
| Storage | 200 NFTs | Monthly Fee | Permanent? |
|---------|----------|-------------|------------|
| **Irys/Arweave** | ~0.2 SOL ($40) one-time | $0 | Yes, forever |
| Pinata IPFS (free) | $0 (up to 500 files) | $0 | No, only while pinned |
| Pinata IPFS (paid) | $0 | $20/mo | No, only while pinned |
| AWS S3 | ~$1 | ~$5/mo | No, centralized |

### Why Pay-Per-Use Beats Subscriptions
- No monthly bills to forget about
- No files disappearing if you cancel a subscription
- Cost scales linearly with usage — mint 10 NFTs, pay for 10 files
- All costs come from the same SOL wallet used for minting

## Accessing Stored Files
```
# Permanent Arweave URL (used in NFT metadata)
https://arweave.net/{transaction_id}

# Example
https://arweave.net/abc123def456...
```

These URLs are permanent. As long as Arweave exists, these files are accessible. Arweave's endowment model pre-pays for 200+ years of storage with the one-time fee.

## How Arweave Permanence Works
- Arweave uses a **storage endowment** — your one-time fee funds decades of replication
- Data is stored across hundreds of nodes worldwide
- The endowment earns interest to fund future storage costs as hardware gets cheaper
- This is why NFT buyers trust Arweave — the image won't disappear if you stop paying

## Integration with Sugar CLI
```bash
# 1. Set upload method in config.json
#    "uploadMethod": "bundlr"

# 2. Place assets in folder
#    assets/0.png, assets/0.json, assets/1.png, assets/1.json...

# 3. Upload (Irys handles everything)
sugar upload

# 4. Sugar automatically:
#    - Uploads each image to Arweave
#    - Gets permanent URL
#    - Updates metadata JSON with the URL
#    - Uploads metadata JSON to Arweave
#    - Stores the cache for Candy Machine deployment
```

## Irys CLI (Optional — For Advanced Use)
If you ever need to upload files outside of Sugar:

### Install
```bash
npm install -g @irys/sdk
```

### Upload a Single File
```bash
irys upload image.png -n mainnet -t solana -w ~/holy-chip-wallet.json
```

### Check Balance
```bash
irys balance YOUR_WALLET_ADDRESS -n mainnet -t solana
```

### Fund Irys Node (Pre-deposit SOL)
```bash
irys fund 100000000 -n mainnet -t solana -w ~/holy-chip-wallet.json
# Amount in lamports (100000000 = 0.1 SOL)
```

## Alternatives Considered
| Service | Why Not (as primary) |
|---------|---------------------|
| Pinata (IPFS) | Monthly subscription, files can disappear if you stop paying |
| NFT.storage | Was free but unreliable, unclear future |
| AWS S3 | Centralized, monthly cost, can be taken down |
| Shadow Drive | Solana-native but less proven, smaller ecosystem |

## Notes
- On **Devnet**, Irys uploads are free (uses test SOL)
- Sugar handles upload resumption — if it fails mid-upload, run `sugar upload` again and it picks up where it left off
- The `cache.json` file created by Sugar maps each asset to its Arweave URL — don't delete it before deploying
- Arweave transaction IDs are permanent and immutable — double-check images before uploading
- For very large batches (1000+), consider pre-funding your Irys balance to avoid per-upload gas overhead
