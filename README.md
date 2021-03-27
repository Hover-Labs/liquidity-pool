# LP Token Contracts

This is a generic contract which takes in one set of tokens and issues LP tokens as a deposit.

This contract can be used as a base to customize other contracts.

## Interface

```
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