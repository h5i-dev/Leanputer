-- Integer-domain compiler lemmas. These do not verify PyTorch, softmax,
-- machine typing, or the Python compiler.
import Std

namespace Leanputer

def bit (b : Bool) : Int := if b then 1 else 0
def relu (x : Int) : Int := max 0 x

theorem not_gate (a : Bool) : relu (1 - bit a) = bit (!a) := by
  cases a <;> decide

theorem and_gate (a b : Bool) : relu (bit a + bit b - 1) = bit (a && b) := by
  cases a <;> cases b <;> decide

theorem or_gate (a b : Bool) :
    relu (bit a + bit b) - relu (bit a + bit b - 1) = bit (a || b) := by
  cases a <;> cases b <;> decide

theorem masked_write (enable old new : Bool) :
    ((enable && new) || (!enable && old)) = (if enable then new else old) := by
  cases enable <;> cases old <;> cases new <;> decide

-- Absorbing-outcome pattern used by both transition implementations.
def absorb {α : Type} (done : Bool) (step : α → α) (state : α) : α :=
  if done then state else step state

theorem terminal_absorbs {α : Type} (step : α → α) (state : α) :
    absorb true step state = state := rfl

#print axioms not_gate
#print axioms and_gate
#print axioms or_gate
#print axioms masked_write
#print axioms terminal_absorbs
end Leanputer
