# PAWpySeed

PAWpySeed is a parallelized Python and C tool for reading and
analyzing the optimized band structure and wave functions
of VASP DFT calculations. The code is written for the PAW
formalism developed by P.E. Blochl and implemented
in VASP.

## Installation

In the future, PAWpySeed will be installable with pip.
For the time being, installation should be performed
by cloning this repository and running the `setup.py` script
in the root directory of the repository.

```
python setup.py build
python setup.py install
```

The `build` command, in addition to the standard distutils setup,
compiles the C code in the `pawpyseed.core` module into a shared
object in the core module, `pawpy.so`. Currently, compiling the
C code requires the Intel C compiler, `icc`, as well as the Intel
Math Kernel Library. When the `build` command is run, an environment
variable `MKLROOT` must be present and point to the Math Kernel Library.

# Dependencies

Python requirements:
```
python>=3.6 or python>=2.7
numpy>=1.14
scipy>=1.0
pymatgen>=2018.2.13
```

C requirements\*:
```
Intel C Compiler >= 16.0.4
Intel Math Kernel Library >= 11.3.4
```
\*In the future, it will be possible to compile the C
code with the GNU compiler.

Optional Python dependencies:
```
sympy>=1.1.1
matplotlib>=0.2.5
```

## Theory and Input

# PAW

The projector augmented wave (PAW) method is a technique
used in plane wave density functional theory to simplify
the description of the wavefunctions near the nuclei
of a system. The strong Coulombic forces near an atomic
nucleus creates quickly oscillating wavefunctions that are
not well described by plane waves without prohibitively
large basis sets, so a "pseudopotential" is introduced
near the atomic nuclei which results in smooth 
"pseudowavefunctions" well described by plane waves. The
full wavefunctions can be recovered by a linear transform
of the pseudowavefunctions. The PAW method requires
three sets of functions: projector functions, onto which
pseudowavefunctions are projected to probe their character;
full partial waves, which describe atomic valence states
derived from the true potential; and pseudo partial waves,
which are derived from the full partial waves and
pseudopotential.

# Files

The projector functions and partial waves are unique
to each element and stored in the POTCAR file
used in a VASP calculation. The pseudowavefunction
is the part of the wavefunction optimized during a DFT
calculation and is stored in the WAVECAR output file
in VASP. PAWpySeed parses both files to retrieve
all parts of the full Kohn Sham wavefunctions.

## The Code

The main purpose of PAWpySeed is to evaluate overlap
operators between Kohn-Sham wavefunctions from different
structures, which is not done by standard plane-wave DFT codes.
Such functionality can be useful for analyzing the composition
of defect levels in solids, which is main application for which
the code is currently focused.

# Implementation

* Python Interface
* Computationally intensive tasks in C
* Parallelized with openmp

# Current Functionality

* Read pseudowavefunctions
* Read projectors and partial waves from VASP POTCAR
* Evaluate overlap operators between bands,
including when bands belong to different structures
with the same lattice
* Project point defect levels onto bulk valence
and conduction bands
* Convenient pycdt interface

# Future Functionality

* Localize orbitals with SCDM-k
* Atomic Hartree Fock and GGA DFT
database for use in charge corrections
and other applications
* Read noncollinear pseudowavefunctions
* Convert PAW wavefunctions to NC wavefunctions
(for use in GW calculations)
* Perturbative charge corrections
* Read pseudopotential, atomic charge
density, and other POTCAR data
* Perform general operator
expectation values on full wavefunctions
