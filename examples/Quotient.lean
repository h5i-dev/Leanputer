namespace LeanputerQuotient
noncomputable section

def family := @Quot.{1}
def mk := @Quot.mk.{1}
def ind := @Quot.ind.{1}
def lift01 := @Quot.lift.{0,1}
def lift10 := @Quot.lift.{1,0}

def lift_constant (A : Type) (a : A) (p : Prop) (h : p) (P : A → Prop) (k : P a) :
    P (@Quot.lift.{0,1} p (fun _ _ => True) A (fun _ => a) (fun _ _ _ => Eq.refl a)
      (@Quot.mk.{0} p (fun _ _ => True) h)) := k

theorem ind_iota (p : Prop) (h : p) :
    @Quot.ind.{0} p (fun _ _ => True) (fun _ => p) (fun h => h)
      (@Quot.mk.{0} p (fun _ _ => True) h) = h := rfl

end
end LeanputerQuotient
