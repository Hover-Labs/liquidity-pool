import smartpy as sp

# A fake oven which keeps track of liqudation state.
class FakeOven(sp.Contract):
  def __init__(
    self,
  ):
    self.init(
      isLiquidated = False
    )

  @sp.entry_point
  def default(self, unit):
    sp.set_type(unit, sp.TUnit)
    pass

  # Param: <unit>
  @sp.entry_point
  def liquidate(self, unit):
    sp.set_type(unit, sp.TUnit)
    self.data.isLiquidated = True
   