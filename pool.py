import smartpy as sp

Token= sp.import_script_from_url("file:token.py")

################################################################
################################################################
# CONSTANTS
################################################################
################################################################

# The number of decimals of precision.
PRECISION = 1000000000000000000 # 18 decimals

################################################################
################################################################
# STATE MACHINE STATES
################################################################
################################################################

IDLE = 0
WAITING_UPDATE_BALANCE = 1
WAITING_REDEEM = 2
WAITING_DEPOSIT = 3

################################################################
################################################################
# CONTRACT
################################################################
################################################################

Addresses = sp.import_script_from_url("file:./test-helpers/addresses.py")

class PoolContract(Token.FA12):
  def __init__(
    self,
    
    # Parent class fields
    administrator = Addresses.ADMIN_ADDRESS,
    paused = False,

    # The address of the token contract which will be deposited.
    tokenAddress = Addresses.TOKEN_ADDRESS,

    # The address of the Quipuswap contract.
    quipuswapAddress = Addresses.QUIPUSWAP_ADDRESS,
    
    # The address of the Oven Registry contract.
    ovenRegistryAddress = Addresses.OVEN_REGISTRY_ADDRESS,

    # The governor of the pool.
    governorAddress = Addresses.GOVERNOR_ADDRESS,

    # How much of the payout to reward the liquidator with.
    rewardPercent = sp.nat(1), # 1%

    # The block which rewards can be changed after.
    rewardChangeAllowedLevel = sp.nat(0),

    # The initial state of the state machine.
    state = IDLE,

    # State machine states - exposed for testing.
    savedState_tokensToRedeem = sp.none,
    savedState_redeemer = sp.none,
    savedState_tokensToDeposit = sp.none,
    savedState_depositor = sp.none,
  ):
    token_id = sp.nat(0)

    token_metadata = sp.map(
      l = {
        "name": sp.bytes('0x517569707573776170204c69717569646174696e67206b555344'), # Quipuswap Liquidating kUSD
        "decimals": sp.bytes('0x3336'), # 36
        "symbol": sp.bytes('0x514c6b555344'), # QLkUSD
        "icon": sp.bytes('0x2068747470733a2f2f6b6f6c696272692d646174612e73332e616d617a6f6e6177732e636f6d2f6c6f676f2e706e67') # https://kolibri-data.s3.amazonaws.com/logo.png
      },
      tkey = sp.TString,
      tvalue = sp.TBytes
    )
    token_entry = (token_id, token_metadata)
    token_metadata = sp.big_map(
      l = {
        token_id: token_entry,
      },
      tkey = sp.TNat,
      tvalue = sp.TPair(sp.TNat, sp.TMap(sp.TString, sp.TBytes))
    )
        
    
    metadata_data = sp.bytes_of_string('{ "name": "Quipuswap Liquidating kUSD",  "description": "kUSD Liquidation Pool tied to Quipuswap",  "authors": ["Hover Labs <hello@hover.engineering>"],  "homepage":  "https://kolibri.finance", "interfaces": [ "TZIP-007-2021-01-29"] }')
    metadata = sp.big_map(
      l = {
        "": sp.bytes('0x74657a6f732d73746f726167653a64617461'), # "tezos-storage:data"
        "data": metadata_data
      },
      tkey = sp.TString,
      tvalue = sp.TBytes            
    )

    self.exception_optimization_level = "debug-message"

    self.init(
      # Parent class fields
      balances = sp.big_map(tvalue = sp.TRecord(approvals = sp.TMap(sp.TAddress, sp.TNat), balance = sp.TNat)), 
      totalSupply = 0,

      # Metadata
      metadata = metadata,
      token_metadata = token_metadata,

      # Addresses
      quipuswapAddress = quipuswapAddress,
      governorAddress = governorAddress,
      ovenRegistryAddress = ovenRegistryAddress,
      tokenAddress = tokenAddress,

      # Configuration paramaters
      rewardPercent = rewardPercent,
      rewardChangeAllowedLevel = rewardChangeAllowedLevel,
      
      # State machinge
      state = state,
      savedState_tokensToRedeem = savedState_tokensToRedeem, # Amount of tokens to redeem, populated when state = WAITING_REDEEM
      savedState_redeemer = savedState_redeemer, # Account redeeming tokens, populated when state = WAITING_REDEEM
      savedState_tokensToDeposit = savedState_tokensToDeposit, # Amount of tokens to deposit, populated when state = WAITING_DEPOSIT
      savedState_depositor = savedState_depositor, # Account depositing the tokens, populated when state = WAITING_DEPOSIT
    )

  ################################################################
  # Liquidation Functions
  ################################################################    

  # Accept XTZ and immediately swap them for kUSD on Quipuswap.
  @sp.entry_point
  def default(self, unit):
    sp.set_type(unit, sp.TUnit)

    # Reward the user who called this transaction.
    rewardAmount = sp.split_tokens(sp.amount, self.data.rewardPercent, 100)
    sp.send(sp.source, rewardAmount)

    # Invoke Quipuswap.
    remainingBalance = sp.balance - rewardAmount
    tradeParam = (
      1, # Min amount to receive
      sp.self_address, # To param
    )    
    tradeHandle = sp.contract(
      sp.TPair(sp.TNat, sp.TAddress),
      self.data.quipuswapAddress,
      "tezToTokenPayment"
    ).open_some()
    sp.transfer(tradeParam, remainingBalance, tradeHandle)

  # Liquidate an oven.
  @sp.entry_point
  def liquidate(self, targetAddress):
    sp.set_type(targetAddress, sp.TAddress)

    # Validate that the target is an oven.
    isOvenHandle = sp.contract(
      sp.TAddress,
      self.data.ovenRegistryAddress,
      "isOven"
    ).open_some()
    sp.transfer(targetAddress, sp.mutez(0), isOvenHandle)

    # Send a liquidation to the oven.
    liquidateHandle = sp.contract(
      sp.TUnit,
      targetAddress,
      "liquidate"
    ).open_some()
    sp.transfer(sp.unit, sp.mutez(0), liquidateHandle)

  ################################################################
  # Liquidity Provider Tokens
  ################################################################

  # Deposit a number of tokens and receive LP tokens.
  @sp.entry_point
  def deposit(self, tokensToDeposit):
    sp.set_type(tokensToDeposit, sp.TNat)

    # Validate state
    sp.verify(self.data.state == IDLE, "BAD_STATE")

    # Save state
    self.data.state = WAITING_DEPOSIT
    self.data.savedState_tokensToDeposit = sp.some(tokensToDeposit)
    self.data.savedState_depositor = sp.some(sp.sender)

    # Call token contract to update balance.
    param = (sp.self_address, sp.self_entry_point(entry_point = 'deposit_callback'))
    contractHandle = sp.contract(
      sp.TPair(sp.TAddress, sp.TContract(sp.TNat)),
      self.data.tokenAddress,
      "getBalance",      
    ).open_some()
    sp.transfer(param, sp.mutez(0), contractHandle)

  # Private callback for redeem.
  @sp.entry_point
  def deposit_callback(self, updatedBalance):
    sp.set_type(updatedBalance, sp.TNat)

    # Validate sender
    sp.verify(sp.sender == self.data.tokenAddress, "BAD_SENDER")

    # Validate state
    sp.verify(self.data.state == WAITING_DEPOSIT, "BAD_STATE")

    # Calculate the tokens to issue.
    tokensToDeposit = sp.local('tokensToDeposit', self.data.savedState_tokensToDeposit.open_some())
    newTokens = sp.local('newTokens', tokensToDeposit.value * PRECISION)
    sp.if self.data.totalSupply != sp.nat(0):
      newUnderlyingBalance = sp.local('newUnderlyingBalance', updatedBalance + tokensToDeposit.value)
      fractionOfPoolOwnership = sp.local('fractionOfPoolOwnership', (tokensToDeposit.value * PRECISION) / newUnderlyingBalance.value)
      newTokens.value = ((fractionOfPoolOwnership.value * self.data.totalSupply) / (sp.as_nat(PRECISION - fractionOfPoolOwnership.value)))

    # Transfer tokens to this contract.
    depositor = sp.local('depositor', self.data.savedState_depositor.open_some())
    tokenTransferParam = sp.record(
      from_ = depositor.value,
      to_ = sp.self_address, 
      value = tokensToDeposit.value
    )
    transferHandle = sp.contract(
      sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
      self.data.tokenAddress,
      "transfer"
    ).open_some()
    sp.transfer(tokenTransferParam, sp.mutez(0), transferHandle)

    # Mint tokens to the depositor
    tokenMintParam = sp.record(
      address = depositor.value, 
      value = newTokens.value
    )
    mintHandle = sp.contract(
      sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")),
      sp.self_address,
      entry_point = 'mint',
    ).open_some()
    sp.transfer(tokenMintParam, sp.mutez(0), mintHandle)

    # Reset state
    self.data.state = IDLE
    self.data.savedState_tokensToDeposit = sp.none
    self.data.savedState_depositor = sp.none

  # Redeem a number of LP tokens for the underlying asset.
  @sp.entry_point
  def redeem(self, tokensToRedeem):
    sp.set_type(tokensToRedeem, sp.TNat)

    # Validate state
    sp.verify(self.data.state == IDLE, "BAD_STATE")

    # Save state
    self.data.state = WAITING_REDEEM
    self.data.savedState_tokensToRedeem = sp.some(tokensToRedeem)
    self.data.savedState_redeemer = sp.some(sp.sender)

    # Call token contract to update balance.
    param = (sp.self_address, sp.self_entry_point(entry_point = 'redeem_callback'))
    contractHandle = sp.contract(
      sp.TPair(sp.TAddress, sp.TContract(sp.TNat)),
      self.data.tokenAddress,
      "getBalance",      
    ).open_some()
    sp.transfer(param, sp.mutez(0), contractHandle)

  # Private callback for redeem.
  @sp.entry_point
  def redeem_callback(self, updatedBalance):
    sp.set_type(updatedBalance, sp.TNat)

    # Validate sender
    sp.verify(sp.sender == self.data.tokenAddress, "BAD_SENDER")

    # Validate state
    sp.verify(self.data.state == WAITING_REDEEM, "BAD_STATE")

    # Calculate tokens to receive.
    tokensToRedeem = sp.local('tokensToRedeem', self.data.savedState_tokensToRedeem.open_some())
    fractionOfPoolOwnership = sp.local('fractionOfPoolOwnership', (tokensToRedeem.value * PRECISION) / self.data.totalSupply)
    tokensToReceive = sp.local('tokensToReceive', (fractionOfPoolOwnership.value * updatedBalance) / PRECISION)

    # Burn the tokens being redeemed.
    redeemer = sp.local('redeemer', self.data.savedState_redeemer.open_some())
    tokenBurnParam = sp.record(
      address = redeemer.value, 
      value = tokensToRedeem.value
    )
    burnHandle = sp.contract(
      sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")),
      sp.self_address,
      entry_point = 'burn',
    ).open_some()
    sp.transfer(tokenBurnParam, sp.mutez(0), burnHandle)

    # Transfer tokens to the owner.
    tokenTransferParam = sp.record(
      from_ = sp.self_address,
      to_ = redeemer.value, 
      value = tokensToReceive.value
    )
    transferHandle = sp.contract(
      sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
      self.data.tokenAddress,
      "transfer"
    ).open_some()
    sp.transfer(tokenTransferParam, sp.mutez(0), transferHandle)

    # Reset state
    self.data.state = IDLE
    self.data.savedState_tokensToRedeem = sp.none
    self.data.savedState_redeemer = sp.none

  ################################################################
  # Governance
  ################################################################

  # Update the governor address.
  @sp.entry_point
  def updateGovernorAddress(self, newGovernorAddress):
    sp.set_type(newGovernorAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorAddress, "NOT_GOVERNOR")
    self.data.governorAddress = newGovernorAddress

  # Update the reward percent.
  @sp.entry_point
  def updateRewardPercent(self, newRewardPercent):
    sp.set_type(newRewardPercent, sp.TNat)

    sp.verify(sp.sender == self.data.governorAddress, "NOT_GOVERNOR")
    sp.verify(sp.level >= self.data.rewardChangeAllowedLevel, "TOO_SOON")

    self.data.rewardPercent = newRewardPercent

  # Update the quipuswap pool address
  @sp.entry_point
  def updateQuipuswapAddress(self, newQuipuswapAddress):
    sp.set_type(newQuipuswapAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorAddress, "NOT_GOVERNOR")
    self.data.quipuswapAddress = newQuipuswapAddress
  
  # Update the oven registry address
  @sp.entry_point
  def updateOvenRegistryAddress(self, newOvenRegistryAddress):
    sp.set_type(newOvenRegistryAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorAddress, "NOT_GOVERNOR")
    self.data.ovenRegistryAddress = newOvenRegistryAddress    

  # Update contract metadata
  @sp.entry_point	
  def updateContractMetadata(self, params):	
    sp.set_type(params, sp.TPair(sp.TString, sp.TBytes))	

    sp.verify(sp.sender == self.data.governorAddress, "NOT_GOVERNOR")

    key = sp.fst(params)
    value = sp.snd(params)	
    self.data.metadata[key] = value

  # Update token metadata
  @sp.entry_point	
  def updateTokenMetadata(self, params):	
    sp.set_type(params, sp.TPair(sp.TNat, sp.TMap(sp.TString, sp.TBytes)))	

    sp.verify(sp.sender == self.data.governorAddress, "NOT_GOVERNOR")
    self.data.token_metadata[0] = params

################################################################
################################################################
# TESTS
################################################################
################################################################

# Only run tests if this file is main.
if __name__ == "__main__":

  Dummy = sp.import_script_from_url("file:./test-helpers/dummy.py")
  FA12 = sp.import_script_from_url("file:./test-helpers/fa12.py")
  FakeQuipuswap = sp.import_script_from_url("file:./test-helpers/fake-quipuswap-pool.py")
  FakeOven = sp.import_script_from_url("file:./test-helpers/fake-oven.py")
  FakeOvenRegistry = sp.import_script_from_url("file:./test-helpers/fake-oven-registry.py")

  ################################################################
  # updateContractMetadata
  ################################################################

  @sp.add_test(name="updateContractMetadata - succeeds when called by governor")
  def test():
    # GIVEN a Pool contract
    scenario = sp.test_scenario()

    pool = PoolContract(
      governorAddress = Addresses.GOVERNOR_ADDRESS,
    )
    scenario += pool

    # WHEN the updateContractMetadata is called with a new locator
    locatorKey = ""
    newLocator = sp.bytes('0x1234567890')
    scenario += pool.updateContractMetadata((locatorKey, newLocator)).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is updated.
    scenario.verify(pool.data.metadata[locatorKey] == newLocator)

  @sp.add_test(name="updateContractMetadata - fails when not called by governor")
  def test():
    # GIVEN a Pool contract
    scenario = sp.test_scenario()

    pool = PoolContract(
      governorAddress = Addresses.GOVERNOR_ADDRESS,
    )
    scenario += pool

    # WHEN the updateContractMetadata is called by someone who isn't the governor THEN the call fails
    locatorKey = ""
    newLocator = sp.bytes('0x1234567890')
    scenario += pool.updateContractMetadata((locatorKey, newLocator)).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False
    )            

  ################################################################
  # updateTokenMetadata
  ################################################################

  @sp.add_test(name="updateTokenMetadata - succeeds when called by governor")
  def test():
    # GIVEN a pool contract
    scenario = sp.test_scenario()

    pool = PoolContract(
      governorAddress = Addresses.GOVERNOR_ADDRESS,
    )
    scenario += pool

    # WHEN the updateTokenMetadata is called with a new data set.
    newKey = "new"
    newValue = sp.bytes('0x123456')
    newMap = sp.map(
      l = {
        newKey: newValue
      },
      tkey = sp.TString,
      tvalue = sp.TBytes
    )
    newData = (sp.nat(0), newMap)

    scenario += pool.updateTokenMetadata(newData).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is updated.
    tokenMetadata = pool.data.token_metadata[0]
    tokenId = sp.fst(tokenMetadata)
    tokenMetadataMap = sp.snd(tokenMetadata)
            
    scenario.verify(tokenId == sp.nat(0))
    scenario.verify(tokenMetadataMap[newKey] == newValue)

  @sp.add_test(name="updateTokenMetadata - fails when not called by governor")
  def test():
    # GIVEN a Pool contract
    scenario = sp.test_scenario()

    pool = PoolContract(
      governorAddress = Addresses.GOVERNOR_ADDRESS,
    )
    scenario += pool

    # WHEN the updateTokenMetadata is called by someone who isn't the governor THEN the call fails
    newMap = sp.map(
      l = {
        "new": sp.bytes('0x123456')
      },
      tkey = sp.TString,
      tvalue = sp.TBytes
    )
    newData = (sp.nat(0), newMap)
    scenario += pool.updateTokenMetadata(newData).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False
    )            

  ################################################################
  # updateRewardPercent
  ################################################################

  @sp.add_test(name="updateRewardPercent - fails if sender is not governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateRewardPercent is called by someone other than the governor
    # THEN the call will fail
    notGovernor = Addresses.NULL_ADDRESS
    newRewardPercent = sp.nat(4)
    scenario += pool.updateRewardPercent(newRewardPercent).run(
      sender = notGovernor,
      valid = False
    )

  @sp.add_test(name="updateRewardPercent - fails if before lock height")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract which is locked until a blacok
    rewardChangeAllowedLevel = sp.nat(5)
    pool = PoolContract(
      rewardChangeAllowedLevel = rewardChangeAllowedLevel
    )
    scenario += pool

    # WHEN updateRewardPercent is called before the level.
    # THEN the call fails.
    newRewardPercent = sp.nat(4)
    scenario += pool.updateRewardPercent(newRewardPercent).run(
      sender = Addresses.GOVERNOR_ADDRESS,
      level = sp.as_nat(rewardChangeAllowedLevel - 1),
      valid = False
    )    

  @sp.add_test(name="updateRewardPercent - can update reward amount")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateRewardPercent is called
    newRewardPercent = sp.nat(4)
    scenario += pool.updateRewardPercent(newRewardPercent).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )    

    # THEN the reward amount is updated.
    scenario.verify(pool.data.rewardPercent == newRewardPercent)

  ################################################################
  # updateQuipuswapAddress
  ################################################################

  @sp.add_test(name="updateQuipuswapAddress - fails if sender is not governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateQuipuswapAddress is called by someone other than the governor
    # THEN the call will fail
    notGovernor = Addresses.NULL_ADDRESS
    scenario += pool.updateQuipuswapAddress(Addresses.ROTATED_ADDRESS).run(
      sender = notGovernor,
      valid = False
    )

  @sp.add_test(name="updateQuipuswapAddress - can rotate governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateQuipuswapAddress is called
    scenario += pool.updateQuipuswapAddress(Addresses.ROTATED_ADDRESS).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )    

    # THEN the quipuswap address is rotated.
    scenario.verify(pool.data.quipuswapAddress == Addresses.ROTATED_ADDRESS)

  ################################################################
  # updateOvenRegistryAddress
  ################################################################

  @sp.add_test(name="updateOvenRegistryAddress - fails if sender is not governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateOvenRegistryAddress is called by someone other than the governor
    # THEN the call will fail
    notGovernor = Addresses.NULL_ADDRESS
    scenario += pool.updateOvenRegistryAddress(Addresses.ROTATED_ADDRESS).run(
      sender = notGovernor,
      valid = False
    )

  @sp.add_test(name="updateOvenRegistryAddress - can rotate governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateOvenRegistryAddress is called
    scenario += pool.updateOvenRegistryAddress(Addresses.ROTATED_ADDRESS).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )    

    # THEN the oven registry address is rotated.
    scenario.verify(pool.data.ovenRegistryAddress == Addresses.ROTATED_ADDRESS)

  ################################################################
  # updateGovernorAddress
  ################################################################

  @sp.add_test(name="updateGovernorAddress - fails if sender is not governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateGovernorAddress is called by someone other than the governor
    # THEN the call will fail
    notGovernor = Addresses.NULL_ADDRESS
    scenario += pool.updateGovernorAddress(Addresses.ROTATED_ADDRESS).run(
      sender = notGovernor,
      valid = False
    )

  @sp.add_test(name="updateGovernorAddress - can rotate governor")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a pool contract
    pool = PoolContract()
    scenario += pool

    # WHEN updateGovernorAddress is called
    scenario += pool.updateGovernorAddress(Addresses.ROTATED_ADDRESS).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )    

    # THEN the governor is rotated.
    scenario.verify(pool.data.governorAddress == Addresses.ROTATED_ADDRESS)

  ################################################################
  # liquidate
  ################################################################

  @sp.add_test(name="liquidate - fails if given address is not oven")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a fake oven registry which will identify all addresses as not ovens.
    ovenRegistry = FakeOvenRegistry.FakeOvenRegistry(
      isOvenValue = False
    )
    scenario += ovenRegistry

    # AND a pool contract
    pool = PoolContract(
      ovenRegistryAddress = ovenRegistry.address,
      tokenAddress = token.address,
    )
    scenario += pool

    # AND the pool has a bunch of tokens
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = sp.nat(10000000000)
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a fake oven.
    oven = FakeOven.FakeOven()
    scenario += oven

    # WHEN liquidate is called
    # THEN the call will fail
    scenario += pool.liquidate(oven.address).run(
      valid = False
    )

  @sp.add_test(name="liquidate - liqudates oven")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a fake oven registry
    ovenRegistry = FakeOvenRegistry.FakeOvenRegistry(
      isOvenValue = True
    )
    scenario += ovenRegistry

    # AND a pool contract
    pool = PoolContract(
      ovenRegistryAddress = ovenRegistry.address,
      tokenAddress = token.address,
    )
    scenario += pool

    # AND the pool has a bunch of tokens
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = sp.nat(10000000000)
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a fake oven.
    oven = FakeOven.FakeOven()
    scenario += oven

    # WHEN Alice liquidates an oven through the pool
    scenario += pool.liquidate(oven.address).run(
      sender = Addresses.ALICE_ADDRESS
    )    
    # THEN the oven is liquidated
    scenario.verify(oven.data.isLiquidated == True)

  ################################################################
  # default
  ################################################################

  @sp.add_test(name="default - can swap tokens")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a fake quipuswap contract
    quipuswapPool = FakeQuipuswap.FakePool(
      tokenAddress = token.address
    )
    scenario += quipuswapPool

    # AND a dummy contract.
    dummy = Dummy.DummyContract()
    scenario += dummy

    # AND a pool contract
    pool = PoolContract(
      quipuswapAddress = quipuswapPool.address,
      tokenAddress = token.address,
    )
    scenario += pool

    # AND the quipuswap pool has a bunch of tokens
    scenario += token.mint(
      sp.record(
        address = quipuswapPool.address,
        value = sp.nat(10000000000)
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN the pool receives some XTZ
    amountMutez = sp.mutez(240000)
    scenario += pool.default(sp.unit).run(
      amount = amountMutez,
      sender = dummy.address,
    )

    # THEN the initiator received 1% of the payout.
    scenario.verify(dummy.balance == sp.mutez(2400))
    
    # AND the amount is transferred to the quipuswap pool.
    scenario.verify(quipuswapPool.balance == sp.mutez(240000 - 2400))

    # AND the pool contract received a number of kUSD back.
    scenario.verify(token.data.balances[pool.address].balance == sp.as_nat((240000 - 2400)))

    # AND the pool has no remaining XTZ.
    scenario.verify(pool.balance == sp.mutez(0))

  ################################################################
  # deposit
  ################################################################

  @sp.add_test(name="deposit - fails in bad state")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract in the WAITING_DEPOSIT state
    pool = PoolContract(
      tokenAddress = token.address,
      state = WAITING_DEPOSIT
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # WHEN Alice deposits tokens in the contract.
    # THEN the call fails
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS,
      valid = False
    )

  @sp.add_test(name="deposit - resets state")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # WHEN Alice deposits tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN the state is reset to idle.
    scenario.verify(pool.data.state == IDLE)
    scenario.verify(pool.data.savedState_tokensToDeposit.is_some() == False)
    scenario.verify(pool.data.savedState_depositor.is_some() == False)

  @sp.add_test(name="deposit - can deposit from one account")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # WHEN Alice deposits tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice trades her tokens for LP tokens
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens * PRECISION)

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == aliceTokens * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == aliceTokens)

  @sp.add_test(name="deposit - can deposit from two accounts")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # THEN Alice trades her tokens for LP tokens
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens * PRECISION)

    # AND Bob trades his tokens for LP tokens
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == aliceTokens * 4  * PRECISION)

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == (aliceTokens + bobTokens) * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == aliceTokens + bobTokens)

  @sp.add_test(name="deposit - can deposit from two accounts - reversed")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice trades her tokens for LP tokens
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens * PRECISION)

    # AND Bob trades his tokens for LP tokens
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == aliceTokens * 4  * PRECISION)

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == (aliceTokens + bobTokens) * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == aliceTokens + bobTokens)

  @sp.add_test(name="deposit - successfully mints LP tokens after additional liquidity is deposited in the pool")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie has tokens
    charlieTokens = sp.nat(60)
    scenario += token.mint(
      sp.record(
        address = Addresses.CHARLIE_ADDRESS,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Charlie has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN the contract receives an additional number of tokens.
    additionalTokens = 10
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = additionalTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie joins after the liquidity is added
    scenario += pool.deposit(
      charlieTokens
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # THEN the contract doubles the number of LP tokens
    scenario.verify(pool.data.totalSupply == (100 * PRECISION))

    # AND the pool has the right number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(10 + 40 + 10 + 60))

    # AND Charlie has the right number of LP tokens.
    scenario.verify(pool.data.balances[Addresses.CHARLIE_ADDRESS].balance == 50 * PRECISION)

  @sp.add_test(name="deposit - successfully mints LP tokens after additional liquidity is deposited in the pool with a small amount of tokens")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie has tokens
    charlieTokens = sp.nat(20)
    scenario += token.mint(
      sp.record(
        address = Addresses.CHARLIE_ADDRESS,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Charlie has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN the contract receives an additional number of tokens.
    additionalTokens = 10
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = additionalTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie joins after the liquidity is added
    scenario += pool.deposit(
      charlieTokens
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # # THEN the contract computes the LP tokens correctly
    scenario.verify(pool.data.totalSupply == (66666666666666666666))

    # AND the pool has the right number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(10 + 40 + 10 + 20))

    # AND Charlie has the right number of LP tokens.
    scenario.verify(pool.data.balances[Addresses.CHARLIE_ADDRESS].balance == 16666666666666666666)

  ################################################################
  # deposit_callback
  ################################################################

  @sp.add_test(name="deposit_callback - can finish deposit")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a pool contract in the WAITING_DEPOSIT state
    pool = PoolContract(
      state = WAITING_DEPOSIT,
      savedState_depositor = sp.some(Addresses.ALICE_ADDRESS),
      savedState_tokensToDeposit = sp.some(aliceTokens),

      tokenAddress = token.address
    )
    scenario += pool
    
    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND the pool has tokens
    poolTokens = PRECISION * 200
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = poolTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN deposit_callback is run
    scenario += pool.deposit_callback(
      poolTokens
    ).run(
      sender = token.address
    )

    # THEN the call succeeds.
    # NOTE: The exact end state is covered by `deposit` tests - we just want to prove that deposit_callback works
    # under the given conditions so we can vary state and sender in other tests to prove it fails.
    scenario.verify(pool.data.state == IDLE)

  @sp.add_test(name="deposit_callback - fails in bad state")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a pool contract in the IDLE state
    pool = PoolContract(
      state = IDLE,
      savedState_depositor = sp.none,
      savedState_tokensToDeposit = sp.none,

      tokenAddress = token.address
    )
    scenario += pool
    
    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND the pool has tokens
    poolTokens = PRECISION * 200
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = poolTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN deposit_callback is run
    # THEN the call fails
    scenario += pool.deposit_callback(
      poolTokens
    ).run(
      sender = token.address,
      valid = False
    )

  @sp.add_test(name="deposit_callback - fails with bad sender")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a pool contract in the WAITING_DEPOSIT state
    pool = PoolContract(
      state = WAITING_DEPOSIT,
      savedState_depositor = sp.some(Addresses.ALICE_ADDRESS),
      savedState_tokensToDeposit = sp.some(aliceTokens),

      tokenAddress = token.address
    )
    scenario += pool
    
    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND the pool has tokens
    poolTokens = PRECISION * 200
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = poolTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN deposit_callback is called by someone other than the token contract
    # THEN the call fails.
    scenario += pool.deposit_callback(
      poolTokens
    ).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False
    )

  ################################################################
  # redeem
  ################################################################

  @sp.add_test(name="redeem - fails in bad state")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract not in the IDLE state
    pool = PoolContract(
      state = WAITING_REDEEM,
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has LP tokens
    scenario += pool.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens * PRECISION
      )
    ).run(
      sender = pool.address
    )

    # WHEN Alice withdraws from the contract
    # THEN the call fails.
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS,
      valid = False
    )

  @sp.add_test(name="redeem - clears state")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Alice deposits tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # WHEN Alice withdraws from the contract.
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN the pool's state is idle.
    scenario.verify(pool.data.state == IDLE)
    scenario.verify(pool.data.savedState_tokensToRedeem.is_some() == False)
    scenario.verify(pool.data.savedState_redeemer.is_some() == False)

  @sp.add_test(name="redeem - can deposit and withdraw from one account")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Alice deposits tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # WHEN Alice withdraws from the contract.
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice trades her LP tokens for her original tokens
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == sp.nat(0))

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(0))

  @sp.add_test(name="redeem - can redeem from two accounts")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN Alice withdraws her tokens
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice receives her original tokens back and the LP tokens are burnt
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))

    # AND Bob still has his position
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == aliceTokens * 4 * PRECISION)

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == bobTokens * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == bobTokens)

    # WHEN Bob withdraws his tokens
    scenario += pool.redeem(
      bobTokens * PRECISION
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # THEN Alice retains her position
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))

    # AND Bob receives his original tokens back and the LP tokens are burn.
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == bobTokens)
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == sp.nat(0))

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(0))

  @sp.add_test(name="redeem - can redeem from two accounts - reversed")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN Bob withdraws his tokens
    scenario += pool.redeem(
      bobTokens * PRECISION
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # THEN Alice retains her position
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens * PRECISION)

    # AND Bob receives his original tokens back and the LP tokens are burn.
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == bobTokens)
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == aliceTokens * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == aliceTokens)

    # WHEN Alice withdraws her tokens
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice receives her original tokens back and the LP tokens are burnt
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))

    # AND Bob still has his position
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == bobTokens)
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == sp.nat(0))

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(0))

  @sp.add_test(name="redeem - can redeem partially from two accounts")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # WHEN Alice withdraws half of her tokens
    scenario += pool.redeem(
      aliceTokens / 2 * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice receives her original tokens back and the LP tokens are burnt
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens / 2)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens / 2 * PRECISION)

    # AND Bob still has his position
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == aliceTokens * 4 * PRECISION)

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == (bobTokens + (aliceTokens / 2)) * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == bobTokens + (aliceTokens / 2))

    # WHEN Bob withdraws a quarter of his tokens
    scenario += pool.redeem(
      bobTokens / 4 * PRECISION
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # THEN Alice retains her position
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens / 2)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens / 2 * PRECISION)

    # AND Bob receives his original tokens back and the LP tokens are burn.
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == 9) # Bob withdraws 22% (10/45) of the pool, which is 9.9999 tokens. Integer math truncates the remainder
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == 30 * PRECISION) # Bob withdrew 1/4 of tokens = .25 * 40 = 30

    # AND the total supply of tokens is as expected
    # Expected = 50 tokens generated - 5 tokens alice redeemed - 10 tokens bob redeemed
    scenario.verify(pool.data.totalSupply == sp.nat(35) * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    # Expected:
    # 1/2 of alice tokens + 3/4 of bob tokens + 1 token rounding error = 5 + 30 + 1 = 36
    expectedRemainingTokens = sp.nat(36)
    scenario.verify(token.data.balances[pool.address].balance == expectedRemainingTokens) 

  @sp.add_test(name="redeem - can redeem from two accounts with liquidity added")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND the contract receives an additional number of tokens.
    additionalTokens = 10
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = additionalTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN Alice withdraws her tokens
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # THEN Alice receives her original tokens plus a proportion of the additional tokens back and the LP tokens are burnt
    # Alice owns 20% of the pool * 10 additional tokens = 2 additional tokens
    additionalTokensForAlice = sp.nat(2)
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens + additionalTokensForAlice)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))

    # AND Bob still has his position
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == aliceTokens * 4 * PRECISION)

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == bobTokens * PRECISION)

    # AND the pool has possession of the correct number of tokens.
    # 10 tokens were added to the pool - 2 tokens alice withdrew = 8 additional tokens remaining.
    scenario.verify(token.data.balances[pool.address].balance == bobTokens + sp.as_nat(additionalTokens - additionalTokensForAlice))

    # WHEN Bob withdraws his tokens
    scenario += pool.redeem(
      bobTokens * PRECISION
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # THEN Alice retains her position
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == aliceTokens + additionalTokensForAlice)
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))

    # AND Bob receives his original tokens back and the LP tokens are burn.
    # Bob owned 80% of the pool * 10 additional tokens = 8 additional tokens   
    additionalTokensForBob = sp.nat(8)
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == bobTokens + additionalTokensForBob)
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))

    # AND the total supply of tokens is as expected
    scenario.verify(pool.data.totalSupply == sp.nat(0))

    # AND the pool has possession of the correct number of tokens.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(0))

  @sp.add_test(name="redeem - can redeem correctly from accounts joining after liquidity is added")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie has tokens
    charlieTokens = sp.nat(60)
    scenario += token.mint(
      sp.record(
        address = Addresses.CHARLIE_ADDRESS,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Charlie has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND the contract receives an additional number of tokens.
    additionalTokens = 10
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = additionalTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie joins after the liquidity is added
    scenario += pool.deposit(
      charlieTokens
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # WHEN everyone withdraws their tokens
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.redeem(
      bobTokens * PRECISION
    ).run(
      sender = Addresses.BOB_ADDRESS
    )
    
    scenario += pool.redeem(
      pool.data.balances[Addresses.CHARLIE_ADDRESS].balance
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # THEN all LP tokens are burnt
    scenario.verify(pool.data.totalSupply == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.CHARLIE_ADDRESS].balance == sp.nat(0))

    # AND the pool has no tokens left in it.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(0))

    # AND Balances are expected
    # NOTE: there are minor rounding errors on withdrawals.
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(12))
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(47))
    scenario.verify(token.data.balances[Addresses.CHARLIE_ADDRESS].balance == sp.nat(61))

  @sp.add_test(name="redeem - can redeem correctly from accounts joining after liquidity is added with fraction of pool")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND a pool contract
    pool = PoolContract(
      tokenAddress = token.address
    )
    scenario += pool

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Bob has twice as many tokens
    bobTokens = sp.nat(40)
    scenario += token.mint(
      sp.record(
        address = Addresses.BOB_ADDRESS,
        value = bobTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie has tokens
    charlieTokens = sp.nat(20)
    scenario += token.mint(
      sp.record(
        address = Addresses.CHARLIE_ADDRESS,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Alice has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    # AND Bob has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = bobTokens
      )
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND Charlie has given the pool an allowance
    scenario += token.approve(
      sp.record(
        spender = pool.address,
        value = charlieTokens
      )
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # AND Alice and Bob deposit tokens in the contract.
    scenario += pool.deposit(
      aliceTokens
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.deposit(
      bobTokens
    ).run(
      sender = Addresses.BOB_ADDRESS
    )

    # AND the contract receives an additional number of tokens.
    additionalTokens = 10
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = additionalTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND Charlie joins after the liquidity is added
    scenario += pool.deposit(
      charlieTokens
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # WHEN everyone withdraws their tokens
    scenario += pool.redeem(
      aliceTokens * PRECISION
    ).run(
      sender = Addresses.ALICE_ADDRESS
    )

    scenario += pool.redeem(
      bobTokens * PRECISION
    ).run(
      sender = Addresses.BOB_ADDRESS
    )
    
    scenario += pool.redeem(
      pool.data.balances[Addresses.CHARLIE_ADDRESS].balance
    ).run(
      sender = Addresses.CHARLIE_ADDRESS
    )

    # THEN all LP tokens are burnt
    scenario.verify(pool.data.totalSupply == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(0))
    scenario.verify(pool.data.balances[Addresses.CHARLIE_ADDRESS].balance == sp.nat(0))

    # AND the pool has no tokens left in it.
    scenario.verify(token.data.balances[pool.address].balance == sp.nat(0))

    # AND Balances are expected
    # NOTE: there are minor rounding errors on withdrawals.
    scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == sp.nat(12))
    scenario.verify(token.data.balances[Addresses.BOB_ADDRESS].balance == sp.nat(47))
    scenario.verify(token.data.balances[Addresses.CHARLIE_ADDRESS].balance == sp.nat(21))

  ################################################################
  # redeem_callback
  ################################################################

  @sp.add_test(name="redeem_callback - can finish redeem")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a pool contract in the WAITING_REDEEM state
    pool = PoolContract(
      state = WAITING_REDEEM,
      savedState_redeemer = sp.some(Addresses.ALICE_ADDRESS),
      savedState_tokensToRedeem = sp.some(aliceTokens * PRECISION),

      tokenAddress = token.address
    )
    scenario += pool
    
    # AND Alice has LP tokens
    scenario += pool.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens * PRECISION
      )
    ).run(
      sender = pool.address
    )

    # AND the pool has tokens
    poolTokens = PRECISION * 200
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = poolTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN redeem_callback is run
    scenario += pool.redeem_callback(
      poolTokens
    ).run(
      sender = token.address
    )

    # THEN the call succeeds.
    # NOTE: The exact end state is covered by `redeem` tests - we just want to prove that redeem_callback works
    # under the given conditions so we can vary state and sender in other tests to prove it fails.
    scenario.verify(pool.data.state == IDLE)

  @sp.add_test(name="redeem_callback - fails in bad state")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a pool contract in the IDLE state
    pool = PoolContract(
      state = IDLE,
      savedState_redeemer = sp.none,
      savedState_tokensToRedeem = sp.none,

      tokenAddress = token.address
    )
    scenario += pool
    
    # AND Alice has LP tokens
    scenario += pool.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens * PRECISION
      )
    ).run(
      sender = pool.address
    )

    # AND the pool has tokens
    poolTokens = PRECISION * 200
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = poolTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN redeem_callback is run
    # THEN the call fails
    scenario += pool.redeem_callback(
      poolTokens
    ).run(
      sender = token.address,
      valid = False
    )

  @sp.add_test(name="redeem_callback - fails with bad sender")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a token contract
    token = FA12.FA12(
      admin = Addresses.ADMIN_ADDRESS
    )
    scenario += token

    # AND Alice has tokens
    aliceTokens = sp.nat(10)
    scenario += token.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # AND a pool contract in the WAITING_REDEEM state
    pool = PoolContract(
      state = WAITING_REDEEM,
      savedState_redeemer = sp.some(Addresses.ALICE_ADDRESS),
      savedState_tokensToRedeem = sp.some(aliceTokens * PRECISION),

      tokenAddress = token.address
    )
    scenario += pool
    
    # AND Alice has LP tokens
    scenario += pool.mint(
      sp.record(
        address = Addresses.ALICE_ADDRESS,
        value = aliceTokens * PRECISION
      )
    ).run(
      sender = pool.address
    )

    # AND the pool has tokens
    poolTokens = PRECISION * 200
    scenario += token.mint(
      sp.record(
        address = pool.address,
        value = poolTokens
      )
    ).run(
      sender = Addresses.ADMIN_ADDRESS
    )

    # WHEN redeem_callback is run from someone other than the token contract
    # THEN the call fails.
    scenario += pool.redeem_callback(
      poolTokens
    ).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False
    )

  sp.add_compilation_target("pool", PoolContract())
