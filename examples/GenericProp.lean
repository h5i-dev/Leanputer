namespace LeanputerGenericProp

inductive Choices : Prop where
 | left : Choices
 | right : Choices

/- An arbitrary proof of the singleton must reduce through the generic K rule. -/
theorem singleton_k (P : Bool → Prop) (h : P false) (t : True) :
    P (True.rec (motive := fun _ => Bool) false t) := h

def from_empty (h : False) : Bool := False.rec (fun _ => Bool) h

theorem choose_proof (P : Prop) (h : P) : P :=
  Choices.rec (motive := fun _ => P) h h Choices.left

end LeanputerGenericProp
