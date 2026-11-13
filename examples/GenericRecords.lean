namespace LeanputerGenericRecords

inductive Color : Type where
 | red : Color
 | blue : Color

structure Box where
  value : Color

theorem projection_iota (P : Color → Prop) (h : P Color.red) :
    P (Box.mk Color.red).value := h

theorem projection_beta (P : Color → Prop) (x : Box) (h : P x.value) :
    P ((fun y : Box => y.value) x) := h

end LeanputerGenericRecords
