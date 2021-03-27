import smartpy as sp

# A fake oven registry which always returns the same value.
class FakeOvenRegistry(sp.Contract):
  def __init__(
    self,
    isOvenValue = False
  ):
    self.init(
      isOvenValue = isOvenValue
    )

  @sp.entry_point
  def default(self, unit):
    sp.set_type(unit, sp.TUnit)
    pass

  # Param: <address>
  @sp.entry_point
  def isOven(self, maybeOvenAddress):
    sp.set_type(maybeOvenAddress, sp.TAddress)

    sp.verify(self.data.isOvenValue, "NOT OVEN")



