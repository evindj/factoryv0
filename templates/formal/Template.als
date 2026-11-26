// Alloy skeleton for structural / data-model invariants.
// Run each `check` with the Alloy Analyzer; record results in <Name>.model-check.log ending in RESULT: PASS|FAIL.
module Template

sig User { roles: set Role }
sig Role { grants: set Permission }
sig Permission {}

// Facts: what the design guarantees structurally.
fact NoOrphanRoles { all r: Role | some roles.r }

// Assertion: a property the design must uphold.
assert EveryUserHasSomePermission { all u: User | some u.roles.grants }

// Small scope hypothesis: most bugs show up with few atoms; justify the scope.
check EveryUserHasSomePermission for 4
