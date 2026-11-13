import Mathlib.Algebra.Group.Defs
namespace LeanputerLaws
noncomputable section
def sgFamily0 := Semigroup.{0}
def addSgFamily1 := AddSemigroup.{1}
def cmFamily0 := CommMagma.{0}
def addCmFamily1 := AddCommMagma.{1}
def sgRec10 := @Semigroup.rec.{1,0}
def addCmRec01 := @AddCommMagma.rec.{0,1}
def parent (A : Type) (s : Semigroup A) : Mul A := s.toMul
def assoc (A : Type) [s : Semigroup A] : ∀a b c:A, (a*b)*c=a*(b*c) := s.mul_assoc
def eta (A : Type) (s : Semigroup A) : (@Semigroup.mk A s.toMul s.mul_assoc : Semigroup A)=s := rfl
end
end LeanputerLaws
