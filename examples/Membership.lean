namespace LeanputerMembership
noncomputable section
def family01 := Membership.{0,1}
def family10 := Membership.{1,0}
def rec102 := @Membership.rec.{1,0,2}
def field (A C : Type) (m : Membership A C) : C → A → Prop := m.1
def eta (A C : Type) (m : Membership A C) :
    (Membership.mk m.1 : Membership A C) = m := rfl
def distinctCarriers : Membership Bool Nat := ⟨fun _ _ => True⟩
end
end LeanputerMembership
