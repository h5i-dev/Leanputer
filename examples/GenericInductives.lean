/- Real elaborated source, with no per-name checking rules. -/
namespace LeanputerGeneric

inductive Color : Type where
  | red : Color
  | blue : Color

inductive Signal : Type where
  | red : Signal
  | amber : Signal
  | green : Signal

inductive Packet : Type where
  | empty : Packet
  | wrap : Color → Packet

theorem bool_iota (P : Bool → Prop) (h : P false) :
    P (Bool.rec (motive := fun _ => Bool) false true false) := h

theorem signal_iota (P : Signal → Prop) (h : P Signal.red) :
    P (Signal.rec (motive := fun _ => Signal) Signal.amber Signal.green Signal.red Signal.green) := h

theorem packet_iota (P : Color → Prop) (h : P Color.red) :
    P (Packet.rec (motive := fun _ => Color) Color.blue (fun x => x) (Packet.wrap Color.red)) := h

end LeanputerGeneric
