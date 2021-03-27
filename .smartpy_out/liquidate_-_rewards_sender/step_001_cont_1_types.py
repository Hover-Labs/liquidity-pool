import smartpy as sp

tstorage = sp.TRecord(isOvenValue = sp.TBool).layout("isOvenValue")
tparameter = sp.TVariant(default = sp.TUnit, isOven = sp.TAddress).layout(("default", "isOven"))
tglobals = { }
tviews = { }
