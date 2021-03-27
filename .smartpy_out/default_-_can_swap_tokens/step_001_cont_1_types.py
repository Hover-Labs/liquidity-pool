import smartpy as sp

tstorage = sp.TRecord(tokenAddress = sp.TAddress).layout("tokenAddress")
tparameter = sp.TVariant(default = sp.TUnit, xtzToToken = sp.TPair(sp.TAddress, sp.TPair(sp.TNat, sp.TTimestamp))).layout(("default", "xtzToToken"))
tglobals = { }
tviews = { }
