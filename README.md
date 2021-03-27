# Kolibri Liquidation Pool

A liquidation pool contract where users can stake `kUSD` for use in oven liquidations and receive the profits of liquidations.

##  Functionality 

### Liquidity Providers ("LPs")

Liquidity Providers ("LPs") stake `kUSD` in the contract by calling `deposit`. In return they receive `dexterLkUSD` tokens, which entitle to them to their share of the `kUSD` in the Liquidation Pool. The deposited `kUSD` is now available to help liquidate undercollateralized Kolibri ovens.

LPs can redeem `dexterLkUSD` tokens by calling `redeem` at any time. The `dexterLkUSD` tokens are burnt and the LP receives their share of `kUSD` back from the pool. 

### Liquidations

Any user may call `liquidate` with the address of an undercollateralized Kolibri oven. Provided that there is sufficient `kUSD` to liquidate the oven, and the oven is actually undercollateralized, then the following will process will happen:
1. The Kolibri oven is liquidated
2. The liquidation pool receives `XTZ` from the liquidation. This `XTZ` is immediately converted to `kUSD` on [Dexter](https://dexter.exchange).
3. The user who called `liquidate` receives a payment from the pool (currently 1 `kUSD`) as a reward for using the pool to liquidate the oven, rather than selfishly liquidating it themsevles. 

## Governance

A special contract, called the `governor` can make changes to the contract. Currently, the `governor` is a two of three multisig with an eight hour timelock. 

Specifically, the following parameters are governable:
- rewardAmount: The amount to pay users who liquidate ovens through the pool contract. 
- governorAddress: The governor may rotate itself to a new address (ex. a new multisig or a DAO)

Additionally, a number of mundane plumbing parameters are also updatable in order to support upgrades in Kolibri, Dexter, and Tezos metadata standards.
- dexterPoolAddress: The address of the Dexter Liquidity Pool. Updatable in case pool in needs to be rotated.
- ovenRegistryAddress: The address of the Kolibri Oven Registry. Required to support future Kolibri protocol upgrades
- contractMetadata: Updatable to allow compliance with with emerging standards
- tokenMetada: Updateable to allow compliance with emerging standards

## Risks

### Smart Contract Risk
This token contract is unaudited. If vulnerabilities are discovered, attackers may be able to drain `kUSD` from the contract.

### Market Manipulation Attacks

The pool will blindly trade `XTZ` for `kUSD` at market rate on Dexter when the contract receives `XTZ`. Because of this, attackers may be able to manipulate exchange rates on Dexter to produce favorable trading conditions for themselves.

### Dust Attacks

TODO(keefertaylor): We can mitigate this attack by sending a percentage of the price.

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
