# Solana CLI Tools

## What It Is
The Solana CLI is a set of command-line tools for interacting with the Solana blockchain. It handles wallet management, transactions, program deployment, and network configuration. It's the foundation that Sugar CLI and other tools build on.

## Why We Chose It
- **Required** — Sugar CLI and Metaplex tools depend on it
- **Official tooling** — maintained by Solana Labs / Anza
- **Full control** — direct blockchain interaction, no middleman
- **Devnet testing** — free test SOL for development
- **Free** — open source

## Setup

### 1. Install Solana CLI
```bash
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
```

Add to PATH (add to `~/.zshrc` or `~/.bashrc`):
```bash
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
```

Verify:
```bash
solana --version
```

### 2. Configure Network
```bash
# Devnet (for testing — use this first!)
solana config set --url devnet

# Mainnet (for real minting)
solana config set --url mainnet-beta

# Check current config
solana config get
```

### 3. Create or Import Wallet

**Create new keypair:**
```bash
solana-keygen new --outfile ~/holy-chip-wallet.json
```

**Import from Phantom (private key):**
```bash
# Export private key from Phantom as base58 string
# Then save as JSON array format that Solana CLI expects
solana-keygen recover --outfile ~/holy-chip-wallet.json
```

**Set as default:**
```bash
solana config set --keypair ~/holy-chip-wallet.json
```

### 4. Fund Wallet

**Devnet (free test SOL):**
```bash
solana airdrop 2
# Can request up to 2 SOL per airdrop, multiple times
```

**Mainnet:**
- Buy SOL on exchange (Coinbase, Kraken)
- Send to your wallet address: `solana address`

## Key Commands

### Wallet & Balance
```bash
solana address                    # Show wallet address
solana balance                    # Check SOL balance
solana balance <ADDRESS>          # Check another wallet's balance
```

### Transactions
```bash
solana transfer <TO> <AMOUNT>     # Send SOL
solana confirm <TX_SIGNATURE>     # Check transaction status
```

### Network & Config
```bash
solana config get                 # Show current configuration
solana config set --url devnet    # Switch to devnet
solana config set --url mainnet-beta  # Switch to mainnet
solana cluster-version            # Check network version
solana epoch-info                 # Current epoch details
```

### Account Info
```bash
solana account <ADDRESS>          # Account details
solana rent <SIZE_BYTES>          # Calculate rent for account size
```

## Devnet vs Mainnet Workflow
```
1. Start on Devnet
   └── solana config set --url devnet
   └── solana airdrop 2
   └── sugar deploy (test)
   └── sugar mint (test)
   └── Verify everything works

2. Switch to Mainnet
   └── solana config set --url mainnet-beta
   └── Fund wallet with real SOL
   └── sugar deploy (real)
   └── sugar mint (real)
   └── List on Magic Eden
```

## Cost
- **CLI tools:** Free (open source)
- **Transactions:** ~0.00001 SOL per transaction (~$0.002)
- **Account rent:** ~0.002 SOL per account (refundable)

## Alternatives Considered
| Tool | Why Not |
|------|---------|
| Solana Web3.js | JavaScript SDK — good for apps, but CLI is simpler for our workflow |
| Anchor CLI | For smart contract development — overkill, we're using existing programs |
| Solana Playground | Browser IDE — convenient but limited for bulk operations |

## Notes
- Always verify you're on the right network before minting (`solana config get`)
- Keep keypair file secure — it's equivalent to a private key
- Devnet SOL has no value — use freely for testing
- Mainnet transactions are final and irreversible
- The CLI auto-updates: `solana-install update`
- macOS may require: `xcode-select --install` before installing
