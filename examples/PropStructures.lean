namespace LeanputerStructures

def iff_intro := @Iff.intro
def and_intro := @And.intro

def iff_mp (a b : Prop) (h : a ↔ b) : a → b := h.mp
def and_left (a b : Prop) (h : a ∧ b) : a := h.left

def and_project_constructor (a b : Prop) (ha : a) (hb : b) : a :=
  (And.intro ha hb).left

end LeanputerStructures

namespace LeanputerStructures

def and_iota_type (a b : Prop) (ha : a) (hb : b) (F : a → Prop) (h : F ha) :
    F ((And.intro ha hb).left) := h

def iff_iota_type (a b : Prop) (mp : a → b) (mpr : b → a)
    (F : (a → b) → Prop) (h : F mp) : F ((Iff.intro mp mpr).mp) := h

end LeanputerStructures
