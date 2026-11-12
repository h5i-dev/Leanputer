-- Matching closed theorem statements: P/Q/R are fixed atomic propositions
-- in the neural checker and universally quantified here.
theorem identity_P (P : Prop) : P → P := fun p => p
theorem identity_Q (Q : Prop) : Q → Q := fun q => q
theorem identity_R (R : Prop) : R → R := fun r => r
theorem identity_function (P Q : Prop) : (P → Q) → P → Q := fun f => f
theorem apply (P Q : Prop) : (P → Q) → P → Q := fun f p => f p
theorem compose (P Q R : Prop) : (P → Q) → (Q → R) → P → R := fun f g p => g (f p)
theorem constant (P Q : Prop) : P → Q → P := fun p q => p
theorem first (P : Prop) : P → P → P := fun p q => p
theorem second (P Q : Prop) : P → Q → Q := fun p q => q
theorem beta_identity (P : Prop) : P → P := fun p => (fun q : P => q) p
