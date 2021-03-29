# Kolibri Liquidation Pool

A liquidation pool contract where users can stake `kUSD` for use in oven liquidations and receive the profits of liquidations.

##  Functionality 

### Liquidity Providers ("LPs")

Liquidity Providers ("LPs") stake `kUSD` in the contract by calling `deposit`. In return they receive `QLkUSD` (**Q**uipuswap **L**iquidating **kUSD**) tokens, which entitle to them to their share of the `kUSD` in the Liquidation Pool. The deposited `kUSD` is now available to help liquidate undercollateralized Kolibri ovens.

LPs can redeem `QLkUSD` tokens by calling `redeem` at any time. The `QLkUSD` tokens are burnt and the LP receives their share of `kUSD` back from the pool. 

### Liquidations

Any user may call `liquidate` with the address of an undercollateralized Kolibri oven. Provided that there is sufficient `kUSD` to liquidate the oven, and the oven is actually undercollateralized, then the following will process will happen:
1. The Kolibri oven is liquidated
2. The liquidation pool receives `XTZ` from the liquidation. 
3. Of the received `XTZ`, a percentage (currently 1%) is sent to the user who initiated the transaction to reward them for liquidating through the pool.
4. The remaining `XTZ` is immediately converted to `kUSD` on [Quipuswap](https://quipusap.com). This `kUSD` is distributed ratably to users in the liquidation pool.

## Governance

A special contract, called the `governor` can make changes to the contract. Currently, the `governor` is a two of three multisig with an eight hour timelock. 

Specifically, the following parameters are governable:
- rewardPercent: The percentage of received `XTZ` to pay the user who initiated the transaction as a reward for using the pool.
- governorAddress: The governor may rotate itself to a new address (ex. a new multisig or a DAO)

Additionally, a number of mundane plumbing parameters are also updatable in order to support upgrades in Kolibri, Quipuswap, and Tezos metadata standards.
- quipuswapPoolAddress: The address of the Quipuswap Liquidity Pool. Updatable in case pool in needs to be rotated.
- ovenRegistryAddress: The address of the Kolibri Oven Registry. Required to support future Kolibri protocol upgrades
- contractMetadata: Updatable to allow compliance with with emerging standards
- tokenMetada: Updateable to allow compliance with emerging standards

## Risks

### Smart Contract Risk
This token contract is unaudited. If vulnerabilities are discovered, attackers may be able to drain `kUSD` from the contract.

### Market Manipulation Attacks

The pool will blindly trade `XTZ` for `kUSD` at market rate on Quipuswap when the contract receives `XTZ`. Because of this, attackers may be able to manipulate exchange rates on Quipuswap to produce favorable trading conditions for themselves.

## Interface

```
# Accept a number of XTZ and immediately swap them to kUSD.
default(unit)

# Liquidate an oven.
liquidate(address target)

# Deposit a number of tokens and receive LP tokens back.
deposit(nat numTokens)

# Redeem a number of LP tokens for underlying tokens.
redeem(nat numLpTokens)

# Update the contract's balance.
updateBalance(unit)
```

## Building

```
# Pre-req install SmartPy (https://smartpy.io)

./compile.sh
```

##  Deployment

TODO(Keefertaylor): Rethink deploy instructions
```
./compile.sh

export NODE_URL=https://rpc.tzbeta.net

export DEXTER_ADDRESS=KT1AbYeDbjjcAnV1QK7EZUUdqku77CdkTuv6
export GOVERNOR_ADDRESS=KT1JBmbYxTv3xptk2CadgEdMfjUCUXKEfe5u
export OVEN_REGISTRY_ADDRESS=KT1Ldn1XWQmk7J4pYgGFjjwV57Ew8NYvcNtJ
export TOKEN_ADDRESS=KT1K9gCRgaLRFKTErYt1wVxA3Frb9FjasjTV

export REWARD_PERCENT=1

export SOURCE=tz1hoverof3f2F8NAavUyTjbFBstZXTqnUMS

export STORAGE="(Pair (Pair (Pair {} (Pair \"$DEXTER_ADDRESS\" \"$GOVERNOR_ADDRESS\")) (Pair (Pair {Elt \"\" 0x74657a6f732d73746f726167653a64617461; Elt \"data\" 0x7b20226e616d65223a2022446578746572204c69717569646174696e67206b555344222c2020226465736372697074696f6e223a20226b555344204c69717569646174696f6e20506f6f6c207469656420746f20446578746572222c202022617574686f7273223a205b22486f766572204c616273203c68656c6c6f40686f7665722e656e67696e656572696e673e225d2c202022686f6d6570616765223a20202268747470733a2f2f6b6f6c696272692e66696e616e636522207d} \"$OVEN_REGISTRY_ADDRESS\") (Pair $REWARD_PERCENT None))) (Pair (Pair (Pair None None) (Pair None 0)) (Pair (Pair \"$TOKEN_ADDRESS\" {Elt 0 (Pair 0 {Elt \"decimals\" 0x3138; Elt \"icon\" 0x2068747470733a2f2f6b6f6c696272692d646174612e73332e616d617a6f6e6177732e636f6d2f6c6f676f2e706e67; Elt \"name\" 0x446578746572204c69717569646174696e67206b555344; Elt \"symbol\" 0x6465787465724c6b555344})}) (Pair 0 0))))"

tezos-client -E $NODE_URL originate contract liquidation_pool transferring 0 from $SOURCE running ./pool.tz --init $STORAGE --burn-cap 10
```
