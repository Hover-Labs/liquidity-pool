import smartpy as sp

tstorage = sp.TRecord(isLiquidated = sp.TBool).layout("isLiquidated")
tparameter = sp.TVariant(default = sp.TUnit, liquidate = sp.TUnit).layout(("default", "liquidate"))
tglobals = { }
tviews = { }
