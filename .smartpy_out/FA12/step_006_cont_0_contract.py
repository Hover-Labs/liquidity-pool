import smartpy as sp

class Contract(sp.Contract):
  def __init__(self):
    self.init(administrator = sp.address('tz1hdQscorfqMzFqYxnrApuS5i6QSTuoAp3w'), balances = {}, paused = False, totalSupply = 0)

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
  def getAdministrator(self, params):
    sp.set_type(sp.fst(params), sp.TUnit)
    __s1 = sp.local("__s1", self.data.administrator)
    sp.set_type(sp.snd(params), sp.TContract(sp.TAddress))
    sp.transfer(__s1.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def getAllowance(self, params):
    __s2 = sp.local("__s2", self.data.balances[sp.fst(params).owner].approvals[sp.fst(params).spender])
    sp.set_type(sp.snd(params), sp.TContract(sp.TNat))
    sp.transfer(__s2.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def getBalance(self, params):
    sp.if ~ (self.data.balances.contains(sp.fst(params))):
      self.data.balances[sp.fst(params)] = sp.record(approvals = {}, balance = 0)
    __s3 = sp.local("__s3", self.data.balances[sp.fst(params)].balance)
    sp.set_type(sp.snd(params), sp.TContract(sp.TNat))
    sp.transfer(__s3.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def getTotalSupply(self, params):
    sp.set_type(sp.fst(params), sp.TUnit)
    __s4 = sp.local("__s4", self.data.totalSupply)
    sp.set_type(sp.snd(params), sp.TContract(sp.TNat))
    sp.transfer(__s4.value, sp.tez(0), sp.snd(params))

  @sp.entry_point
  def mint(self, params):
    sp.set_type(params, sp.TRecord(address = sp.TAddress, value = sp.TNat).layout(("address", "value")))
    sp.verify((sp.sender == self.data.administrator) | (sp.sender == sp.self_address))
    sp.if ~ (self.data.balances.contains(params.address)):
      self.data.balances[params.address] = sp.record(approvals = {}, balance = 0)
    self.data.balances[params.address].balance += params.value
    self.data.totalSupply += params.value

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