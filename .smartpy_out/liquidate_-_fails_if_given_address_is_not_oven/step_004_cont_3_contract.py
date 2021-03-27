import smartpy as sp

class Contract(sp.Contract):
  def __init__(self):
    self.init(isLiquidated = False)

  @sp.entry_point
  def default(self, params):
    sp.set_type(params, sp.TUnit)

  @sp.entry_point
  def liquidate(self, params):
    sp.set_type(params, sp.TUnit)
    self.data.isLiquidated = True