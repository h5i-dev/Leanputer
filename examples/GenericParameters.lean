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

inductive Phantom (A : Type) : Type where
 | base : Phantom A
 | step : Phantom A → Phantom A

theorem two_parameter_rec (P : Bool → Prop) (x : Bool) (h : P x) :
    P (Either.rec (motive := fun _ => Bool) (fun a => a) (fun b => b)
      (Either.left (B := Bool) x)) := h

theorem recursive_parameter_iota (P : Phantom Bool → Prop)
    (h : P (@Phantom.step Bool (@Phantom.base Bool))) :
    P (@Phantom.rec Bool (fun _ => Phantom Bool) (@Phantom.base Bool)
      (fun _ ih => @Phantom.step Bool ih) (@Phantom.step Bool (@Phantom.base Bool))) := h

theorem parameterized_none (P : Bool → Prop) (h : P false) :
    P (Option.rec (motive := fun _ => Bool) false (fun x => x) (Option.none : Option Bool)) := h

inductive ProofBox (P : Prop) : Type where
 | mk : P → ProofBox P

theorem prop_parameter_rec (Q : Bool → Prop) (h : Q false) :
    Q (@ProofBox.rec True (fun _ => Bool) (fun _ => false) (@ProofBox.mk True True.intro)) := h

end LeanputerGenericParameters
