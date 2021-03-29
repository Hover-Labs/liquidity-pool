import smartpy as sp

Addresses = sp.import_script_from_url("file:./test-helpers/addresses.py")

# A fake quipuswap pool that always exchanges 1 mutez for one token.
class FakePool(sp.Contract):
  def __init__(
    self,
    tokenAddress = Addresses.TOKEN_ADDRESS
  ):
    self.init(
      tokenAddress = tokenAddress
    )

  @sp.entry_point
  def default(self, unit):
    sp.set_type(unit, sp.TUnit)
    pass

  # Param: (<min amount> <to>)
  @sp.entry_point
  def tezToTokenPayment(self, param):
    sp.set_type(param, sp.TPair(sp.TNat, sp.TAddress))

    # Extract destination.
    destination = sp.snd(param)

    # Compute tokens to supply at 1 to 1.
    # This fancy statement converts mutez to a nat.
    amount = sp.fst(sp.ediv(sp.amount, sp.mutez(1)).open_some())

    # Transfer tokens to recipient.
    tokenTransferParam = sp.record(
      from_ = sp.self_address,
      to_ = destination, 
      value = amount
    )
    transferHandle = sp.contract(
      sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
      self.data.tokenAddress,
      "transfer"
    ).open_some()
    sp.transfer(tokenTransferParam, sp.mutez(0), transferHandle)



