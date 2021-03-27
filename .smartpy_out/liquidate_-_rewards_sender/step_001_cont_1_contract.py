import smartpy as sp

class Contract(sp.Contract):
  def __init__(self):
    self.init(isOvenValue = True)

  @sp.entry_point
  def default(self, params):
    sp.set_type(params, sp.TUnit)

  @sp.entry_point
  def isOven(self, params):
    sp.set_type(params, sp.TAddress)
    sp.verify(self.data.isOvenValue, message = 'NOT OVEN')