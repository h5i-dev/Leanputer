# Original-source Nat literal and recursor evidence

The source driver checks the complete raw ordinary Nat block, validates the
finite literal bindings, checks arbitrary limb data, and reduces its generated
recursor from literal majors. No input type/admission/constructor metadata is
trusted. [Algorithm and remaining gaps](../../docs/kernel/literals-native.md).

`regression.log`: PASS5tests166.179s, including five Nat cases
(0,1,65536,2^160,2^128+17), explicit missing/empty/different Nat binding GAPs,
narrow physical-word borrow RESOURCE INDEX, Quot initialization/reduction/
atomicity and restored-owner K/eta source cases. Nat143SELECTED transitions plus
4selected terminal boundary transitions compare all registers/banks. Independent
SPEC accepts the five positive sources and every public scheme/RHS matches.
Source DONE steps7864/8183/8190/8271/8256; heap864/901/904/931/927includingnull.

This is selected IR/semantic evidence, not STOCK or full Nat arithmetic. The
independent full arithmetic expectations are not connected to native yet.
String services and primitive-negative conversion remain explicit gaps. There
is no new native measurement; the historical10.35B smoke is not a small model.
