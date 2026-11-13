namespace LeanputerLet

def local_identity (P : Prop) : P → P :=
  let f : P → P := fun h => h
  f

def type_alias (A : Type) (a : A) : A :=
  let B : Type := A
  let b : B := a
  b

def type_zeta (P : Prop) (h : P) : (let Q : Prop := P; Q) := h

end LeanputerLet
