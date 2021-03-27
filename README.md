# Kolibri Liquidation Pool

This pool contract is allows users to stake `kUSD` and receive liquidating kUSD `lkUSD` in return.

## Interface

TODO(keefertaylor): Update the interface.

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