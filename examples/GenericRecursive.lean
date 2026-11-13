namespace LeanputerGenericRecursive

inductive Tally : Type where
 | zero : Tally
 | step : Tally → Tally

inductive Renamed : Type where
 | base : Renamed
 | next : Renamed → Renamed

theorem recursive_iota (P : Tally → Prop) (h : P (Tally.step Tally.zero)) :
    P (Tally.rec (motive := fun _ => Tally) Tally.zero (fun _ ih => Tally.step ih)
      (Tally.step Tally.zero)) := h

theorem renamed_iota (P : Renamed → Prop) (h : P (Renamed.next Renamed.base)) :
    P (Renamed.rec (motive := fun _ => Renamed) Renamed.base (fun _ ih => Renamed.next ih)
      (Renamed.next Renamed.base)) := h

theorem nested_iota (P : Tally → Prop) (h : P (Tally.step (Tally.step Tally.zero))) :
    P (Tally.rec (motive := fun _ => Tally) Tally.zero (fun _ ih => Tally.step ih)
      (Tally.step (Tally.step Tally.zero))) := h

theorem natural_iota (P : Nat → Prop) (h : P (Nat.succ Nat.zero)) :
    P (Nat.rec (motive := fun _ => Nat) Nat.zero (fun _ ih => Nat.succ ih)
      (Nat.succ Nat.zero)) := h

end LeanputerGenericRecursive
