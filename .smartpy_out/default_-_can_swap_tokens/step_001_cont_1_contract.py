import smartpy as sp

class Contract(sp.Contract):
  def __init__(self):
    self.init(tokenAddress = sp.address("KT1TezoooozzSmartPyzzSTATiCzzzwwBFA1"))

  @sp.entry_point
  def default(self, params):
    sp.set_type(params, sp.TUnit)

  @sp.entry_point
  def xtzToToken(self, params):
    sp.set_type(params, sp.TPair(sp.TAddress, sp.TPair(sp.TNat, sp.TTimestamp)))
    sp.transfer(sp.record(from_ = sp.self_address, to_ = sp.fst(params), value = sp.fst(sp.ediv(sp.amount, sp.mutez(1)).open_some())), sp.tez(0), sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))), self.data.tokenAddress, entry_point='transfer').open_some())