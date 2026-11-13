namespace LeanputerGenericParameters

inductive Either (A B : Type) : Type where
 | left : A → Either A B
 | right : B → Either A B

theorem option_constructor (P : Option Bool → Prop) (x : Bool) (h : P (Option.some x)) :
    P ((fun y : Bool => Option.some y) x) := h

theorem two_parameters (P : Either Bool Bool → Prop) (x : Bool) (h : P (Either.left x)) :
    P ((fun y : Bool => Either.left y) x) := h

theorem option_rec_boundary (P : Bool → Prop) (x : Bool) (h : P x) :
    P (Option.rec (motive := fun _ => Bool) false (fun y => y) (Option.some x)) := h

end LeanputerGenericParameters
