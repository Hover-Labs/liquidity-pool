import smartpy as sp

class Contract(sp.Contract):
  def __init__(self):
    self.init(administrator = sp.address('tz1abmz7jiCV2GH2u81LRrGgAFFgvQgiDiaf'), balances = {}, dexterAddress = sp.address('tz1aRoaRhSpRYvFdyvgWLL6TGyRoGF51wDjM'), governorAddress = sp.address('tz1NoYvKjXTzTk54VpLxBfouJ33J8jwKPPvw'), metadata = {'' : sp.bytes('0x74657a6f732d73746f726167653a64617461'), 'data' : sp.bytes('0x7b20226e616d65223a2022446578746572204c69717569646174696e67206b555344222c2020226465736372697074696f6e223a20225374616b6564206b55534420696e206120446578746572206c69717569646174696f6e2073797374656d222c202022617574686f7273223a205b22486f766572204c616273203c68656c6c6f40686f7665722e656e67696e656572696e673e225d2c202022686f6d6570616765223a20202268747470733a2f2f6b6f6c696272692e66696e616e636522207d0a')}, ovenRegistryAddress = sp.address('tz1VQnqCCqX4K5sP3FNkVSNKTdCAMJDd3E1n'), paused = False, rewardPercent = 1, savedState_depositor = sp.none, savedState_redeemer = sp.none, savedState_tokensToDeposit = sp.none, savedState_tokensToRedeem = sp.none, state = 0, tokenAddress = sp.address("KT1TezoooozzSmartPyzzSTATiCzzzwwBFA1"), token_metadata = {0 : (0, {'decimals' : sp.bytes('0x3138'), 'icon' : sp.bytes('0x2068747470733a2f2f6b6f6c696272692d646174612e73332e616d617a6f6e6177732e636f6d2f6c6f676f2e706e67'), 'name' : sp.bytes('0x446578746572204c69717569646174696e67206b555344'), 'symbol' : sp.bytes('0x6465787465724c6b555344')})}, totalSupply = 0, underlyingBalance = 0)

  @sp.entry_point
  def approve(self, params):
    sp.set_type(params, sp.TRecord(spender = sp.TAddress, value = sp.TNat).layout(("spender", "value")))
    sp.if ~ (self.data.balances.contains(sp.sender)):
      self.data.balances[sp.sender] = sp.record(approvals = {}, balance = 0)
    sp.verify(~ self.data.paused)
    sp.verify((self.data.balances[sp.sender].approvals.get(params.spender, default_value = 0) == 0) | (params.value == 0), message = 'UnsafeAllowanceChange')
    self.data.balances[sp.sender].approvals[params.spender] = params.value

  @sp.entry_point
  def burn(self, params):
    sp.set_type(params, sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")))
    sp.verify((sp.sender == self.data.administrator) | (sp.sender == sp.self_address))
    sp.verify(self.data.balances[params.address].balance >= params.value)
    self.data.balances[params.address].balance = sp.as_nat(self.data.balances[params.address].balance - params.value)
    self.data.totalSupply = sp.as_nat(self.data.totalSupply - params.value)

  @sp.entry_point
  def default(self, params):
    sp.set_type(params, sp.TUnit)
    sp.send(sp.source, sp.split_tokens(sp.amount, self.data.rewardPercent, 100))
    sp.transfer((sp.self_address, (1, sp.add_seconds(sp.now, 3600))), sp.balance - sp.split_tokens(sp.amount, self.data.rewardPercent, 100), sp.contract(sp.TPair(sp.TAddress, sp.TPair(sp.TNat, sp.TTimestamp)), self.data.dexterAddress, entry_point='xtzToToken').open_some())
    sp.send(sp.self_address, sp.tez(0))

  @sp.entry_point
  def deposit(self, params):
    sp.set_type(params, sp.TNat)
    sp.verify(self.data.state == 0, message = 'bad state')
    self.data.state = 3
    self.data.savedState_tokensToDeposit = sp.some(params)
    self.data.savedState_depositor = sp.some(sp.sender)
    sp.transfer((sp.self_address, sp.self_entry_point('deposit_callback')), sp.tez(0), sp.contract(sp.TPair(sp.TAddress, sp.TContract(sp.TNat)), self.data.tokenAddress, entry_point='getBalance').open_some())

  @sp.entry_point
  def deposit_callback(self, params):
    sp.set_type(params, sp.TNat)
    sp.verify(sp.sender == self.data.tokenAddress, message = 'bad sender')
    sp.verify(self.data.state == 3, message = 'bad state')
    tokensToDeposit = sp.local("tokensToDeposit", self.data.savedState_tokensToDeposit.open_some())
    newTokens = sp.local("newTokens", tokensToDeposit.value * 1000000000000000000)
    sp.if self.data.totalSupply != 0:
      newUnderlyingBalance = sp.local("newUnderlyingBalance", params + tokensToDeposit.value)
      fractionOfPoolOwnership = sp.local("fractionOfPoolOwnership", (tokensToDeposit.value * 1000000000000000000) // newUnderlyingBalance.value)
      newTokens.value = (fractionOfPoolOwnership.value * self.data.totalSupply) // sp.as_nat(1000000000000000000 - fractionOfPoolOwnership.value)
    self.data.underlyingBalance = params + tokensToDeposit.value
    depositor = sp.local("depositor", self.data.savedState_depositor.open_some())
    sp.transfer(sp.record(from_ = depositor.value, to_ = sp.self_address, value = tokensToDeposit.value), sp.tez(0), sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))), self.data.tokenAddress, entry_point='transfer').open_some())
    sp.transfer(sp.record(address = depositor.value, value = newTokens.value), sp.tez(0), sp.contract(sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")), sp.self_address, entry_point='mint').open_some())
    self.data.state = 0
    self.data.savedState_tokensToDeposit = sp.none
    self.data.savedState_depositor = sp.none

  @sp.entry_point
  def getAdministrator(self, params):
    sp.set_type(sp.fst(params), sp.TUnit)
    __s73 = sp.local("__s73", self.data.administrator)
    sp.set_type(sp.snd(params), sp.TContract(sp.TAddress))
    sp.transfer(__s73.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def getAllowance(self, params):
    __s74 = sp.local("__s74", self.data.balances[sp.fst(params).owner].approvals[sp.fst(params).spender])
    sp.set_type(sp.snd(params), sp.TContract(sp.TNat))
    sp.transfer(__s74.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def getBalance(self, params):
    sp.if ~ (self.data.balances.contains(sp.fst(params))):
      self.data.balances[sp.fst(params)] = sp.record(approvals = {}, balance = 0)
    __s75 = sp.local("__s75", self.data.balances[sp.fst(params)].balance)
    sp.set_type(sp.snd(params), sp.TContract(sp.TNat))
    sp.transfer(__s75.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def getTotalSupply(self, params):
    sp.set_type(sp.fst(params), sp.TUnit)
    __s76 = sp.local("__s76", self.data.totalSupply)
    sp.set_type(sp.snd(params), sp.TContract(sp.TNat))
    sp.transfer(__s76.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def liquidate(self, params):
    sp.set_type(params, sp.TAddress)
    sp.transfer(params, sp.tez(0), sp.contract(sp.TAddress, self.data.ovenRegistryAddress, entry_point='isOven').open_some())
    sp.send(params, sp.tez(0))

  @sp.entry_point
  def mint(self, params):
    sp.set_type(params, sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")))
    sp.verify((sp.sender == self.data.administrator) | (sp.sender == sp.self_address))
    sp.if ~ (self.data.balances.contains(params.address)):
      self.data.balances[params.address] = sp.record(approvals = {}, balance = 0)
    self.data.balances[params.address].balance += params.value
    self.data.totalSupply += params.value

  @sp.entry_point
  def redeem(self, params):
    sp.set_type(params, sp.TNat)
    sp.verify(self.data.state == 0, message = 'bad state')
    self.data.state = 2
    self.data.savedState_tokensToRedeem = sp.some(params)
    self.data.savedState_redeemer = sp.some(sp.sender)
    sp.transfer((sp.self_address, sp.self_entry_point('redeem_callback')), sp.tez(0), sp.contract(sp.TPair(sp.TAddress, sp.TContract(sp.TNat)), self.data.tokenAddress, entry_point='getBalance').open_some())

  @sp.entry_point
  def redeem_callback(self, params):
    sp.set_type(params, sp.TNat)
    sp.verify(sp.sender == self.data.tokenAddress, message = 'bad sender')
    sp.verify(self.data.state == 2, message = 'bad state')
    tokensToRedeem = sp.local("tokensToRedeem", self.data.savedState_tokensToRedeem.open_some())
    fractionOfPoolOwnership = sp.local("fractionOfPoolOwnership", (tokensToRedeem.value * 1000000000000000000) // self.data.totalSupply)
    tokensToReceive = sp.local("tokensToReceive", (fractionOfPoolOwnership.value * params) // 1000000000000000000)
    self.data.underlyingBalance = sp.as_nat(params - tokensToReceive.value)
    redeemer = sp.local("redeemer", self.data.savedState_redeemer.open_some())
    sp.transfer(sp.record(address = redeemer.value, value = tokensToRedeem.value), sp.tez(0), sp.contract(sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")), sp.self_address, entry_point='burn').open_some())
    sp.transfer(sp.record(from_ = sp.self_address, to_ = redeemer.value, value = tokensToReceive.value), sp.tez(0), sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))), self.data.tokenAddress, entry_point='transfer').open_some())
    self.data.state = 0
    self.data.savedState_tokensToRedeem = sp.none
    self.data.savedState_redeemer = sp.none

  @sp.entry_point
  def setAdministrator(self, params):
    sp.set_type(params, sp.TAddress)
    sp.verify(sp.sender == self.data.administrator)
    self.data.administrator = params

  @sp.entry_point
  def setPause(self, params):
    sp.set_type(params, sp.TBool)
    sp.verify(sp.sender == self.data.administrator)
    self.data.paused = params

  @sp.entry_point
  def transfer(self, params):
    sp.set_type(params, sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))))
    sp.verify((sp.sender == self.data.administrator) | ((~ self.data.paused) & ((params.from_ == sp.sender) | (self.data.balances[params.from_].approvals[sp.sender] >= params.value))))
    sp.if ~ (self.data.balances.contains(params.to_)):
      self.data.balances[params.to_] = sp.record(approvals = {}, balance = 0)
    sp.verify(self.data.balances[params.from_].balance >= params.value)
    self.data.balances[params.from_].balance = sp.as_nat(self.data.balances[params.from_].balance - params.value)
    self.data.balances[params.to_].balance += params.value
    sp.if (params.from_ != sp.sender) & (~ (sp.sender == self.data.administrator)):
      self.data.balances[params.from_].approvals[sp.sender] = sp.as_nat(self.data.balances[params.from_].approvals[sp.sender] - params.value)

  @sp.entry_point
  def updateBalance(self, params):
    sp.set_type(params, sp.TUnit)
    sp.verify(self.data.state == 0, message = 'bad state')
    self.data.state = 1
    sp.transfer((sp.self_address, sp.self_entry_point('updateBalance_callback')), sp.tez(0), sp.contract(sp.TPair(sp.TAddress, sp.TContract(sp.TNat)), self.data.tokenAddress, entry_point='getBalance').open_some())

  @sp.entry_point
  def updateBalance_callback(self, params):
    sp.set_type(params, sp.TNat)
    sp.verify(sp.sender == self.data.tokenAddress, message = 'bad sender')
    sp.verify(self.data.state == 1, message = 'bad state')
    self.data.state = 0
    self.data.underlyingBalance = params

  @sp.entry_point
  def updateContractMetadata(self, params):
    sp.set_type(params, sp.TPair(sp.TString, sp.TBytes))
    sp.verify(sp.sender == self.data.governorAddress, message = 'not governor')
    self.data.metadata[sp.fst(params)] = sp.snd(params)

  @sp.entry_point
  def updateDexterAddress(self, params):
    sp.set_type(params, sp.TAddress)
    sp.verify(sp.sender == self.data.governorAddress, message = 'not governor')
    self.data.dexterAddress = params

  @sp.entry_point
  def updateGovernorAddress(self, params):
    sp.set_type(params, sp.TAddress)
    sp.verify(sp.sender == self.data.governorAddress, message = 'not governor')
    self.data.governorAddress = params

  @sp.entry_point
  def updateOvenRegistryAddress(self, params):
    sp.set_type(params, sp.TAddress)
    sp.verify(sp.sender == self.data.governorAddress, message = 'not governor')
    self.data.ovenRegistryAddress = params

  @sp.entry_point
  def updateRewardPercent(self, params):
    sp.set_type(params, sp.TNat)
    sp.verify(sp.sender == self.data.governorAddress, message = 'not governor')
    self.data.rewardPercent = params

  @sp.entry_point
  def updateTokenMetadata(self, params):
    sp.set_type(params, sp.TPair(sp.TNat, sp.TMap(sp.TString, sp.TBytes)))
    sp.verify(sp.sender == self.data.governorAddress, message = 'not governor')
    self.data.token_metadata[0] = params