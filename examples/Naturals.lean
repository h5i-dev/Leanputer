namespace LeanputerNat
noncomputable section

def family := Nat
def zero := Nat.zero
def succ := Nat.succ
def rec0 := @Nat.rec.{0}
def rec1 := @Nat.rec.{1}
def literal : Nat := nat_lit 3

def succ_literal : Nat.succ (nat_lit 4) = (nat_lit 5) := rfl
def recursive_iota : @Nat.rec.{1} (fun _ => Nat) Nat.zero
    (fun _ ih => Nat.succ ih) (nat_lit 3) = (nat_lit 3) := rfl

def zeroFamily := Zero.{0}
def oneFamily := One.{1}
def zeroRec10 := @Zero.rec.{1, 0}
def zeroField (A : Type) (m : Zero A) : A := m.1
def oneField (A : Type) (m : One A) : A := m.1

end
end LeanputerNat
