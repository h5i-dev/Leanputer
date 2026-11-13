namespace LeanputerOfNat
noncomputable section

def family0 := OfNat.{0}
def rec10 := @OfNat.rec.{1, 0}
def normalLiteral : Nat := 3

def customLiteral :
    @OfNat.ofNat Nat (nat_lit 3) (@OfNat.mk Nat (nat_lit 3) (nat_lit 5)) = (nat_lit 5) := rfl

def eta (A : Type) (n : Nat) (r : OfNat A n) (P : OfNat A n → Prop) (k : P r) :
    P (@OfNat.mk A n r.1) := k

end
end LeanputerOfNat
