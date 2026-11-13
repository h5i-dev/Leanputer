namespace LeanputerUnits
noncomputable section

def family0 := PUnit.{0}
def family1 := PUnit.{1}
def unit0 := PUnit.unit.{0}
def unit1 := PUnit.unit.{1}
def rec10 := @PUnit.rec.{1, 0}
def rec01 := @PUnit.rec.{0, 1}

def data_rec (x : PUnit.{1}) (P : Bool → Prop) (k : P Bool.true) :
    P (@PUnit.rec.{1, 1} (fun _ => Bool) Bool.true x) := k

def data_eta (x : PUnit.{1}) (P : PUnit.{1} → Prop) (k : P x) : P PUnit.unit := k

def prop_eta (x : PUnit.{0}) (P : PUnit.{0} → Prop) (k : P x) : P PUnit.unit := k

def prop_ctor (P : Bool → Prop) (k : P Bool.true) :
    P (@PUnit.rec.{1, 0} (fun _ => Bool) Bool.true PUnit.unit) := k

end
end LeanputerUnits
