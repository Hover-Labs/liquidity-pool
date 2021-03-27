import smartpy as sp

# This file contains addresses for tests which are named and ensure uniqueness across the test suite.

# The address which acts as the Token Admin
ADMIN_ADDRESS = sp.address("tz1abmz7jiCV2GH2u81LRrGgAFFgvQgiDiaf")

# Contract address
TOKEN_ADDRESS = sp.address("tz1aJS7Pk9uWR3wWyFf1i3RwhYxN84G7stom")
DEXTER_ADDRESS = sp.address("tz1aRoaRhSpRYvFdyvgWLL6TGyRoGF51wDjM")

# An series of named addresses with no particular role.
# These are used for token transfer tests.
ALICE_ADDRESS = sp.address("tz1LLNkQK4UQV6QcFShiXJ2vT2ELw449MzAA")
BOB_ADDRESS = sp.address("tz1UMCB2AHSTwG7YcGNr31CqYCtGN873royv")
CHARLIE_ADDRESS = sp.address("tz1R6Ej25VSerE3MkSoEEeBjKHCDTFbpKuSX")

# An address which is never used. This is a `null` value for addresses.
NULL_ADDRESS = sp.address("tz1bTpviNnyx2PXsNmGpCQTMQsGoYordkUoA")
