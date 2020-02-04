catlearn.optimize package
=========================

Submodules
----------

catlearn.optimize.constraints module
------------------------------------

.. automodule:: catlearn.optimize.constraints
    :members:
    :undoc-members:
    :show-inheritance:

catlearn.optimize.convergence module
------------------------------------

.. automodule:: catlearn.optimize.convergence
    :members:
    :undoc-members:
    :show-inheritance:

catlearn.optimize.functions\_calc module
----------------------------------------

.. automodule:: catlearn.optimize.functions_calc
    :members:
    :undoc-members:
    :show-inheritance:

catlearn.optimize.get\_real\_values module
------------------------------------------

.. automodule:: catlearn.optimize.get_real_values
    :members:
    :undoc-members:
    :show-inheritance:

catlearn.optimize.io module
---------------------------

.. automodule:: catlearn.optimize.io
    :members:
    :undoc-members:
    :show-inheritance:

catlearn.optimize.mlneb module
------------------------------

.. automodule:: catlearn.optimize.mlneb
    :members:
    :undoc-members:
    :show-inheritance:
    Parameters
        ----------
        start: Trajectory file (in ASE format) or Atoms object.
            Initial end-point of the NEB path or Atoms object.
        end: Trajectory file (in ASE format).
            Final end-point of the NEB path.
        n_images: int or float
            Number of images of the path (if not included a path before).
             The number of images include the 2 end-points of the NEB path.
        k: float or list
            Spring constant(s) in eV/Ang.
        interpolation: string or Atoms list or Trajectory
            Automatic interpolation can be done ('idpp' and 'linear' as
            implemented in ASE).
            See https://wiki.fysik.dtu.dk/ase/ase/neb.html.
            Manual: Trajectory file (in ASE format) or list of Atoms.
            Atoms trajectory or list of Atoms containing the images along the
            path.
        neb_method: string
            NEB method as implemented in ASE. ('aseneb', 'improvedtangent'
            or 'eb').
            See https://wiki.fysik.dtu.dk/ase/ase/neb.html.
        ase_calc: ASE calculator Object.
            ASE calculator as implemented in ASE.
            See https://wiki.fysik.dtu.dk/ase/ase/calculators/calculators.html
        prev_calculations: Atoms list or Trajectory file (in ASE format).
            (optional) The user can feed previously calculated data for the
            same hypersurface. The previous calculations must be fed as an
            Atoms list or Trajectory file.
        restart: boolean
            Only useful if you want to continue your ML-NEB in the same
            directory. The file "evaluated_structures.traj" from the
            previous run, must be located in the same run directory.
        force_consistent: boolean or None
            Use force-consistent energy calls (as opposed to the energy
            extrapolated to 0 K). By default (force_consistent=None) uses
            force-consistent energies if available in the calculator, but
            falls back to force_consistent=False if not.

catlearn.optimize.tools module
------------------------------

.. automodule:: catlearn.optimize.tools
    :members:
    :undoc-members:
    :show-inheritance:

catlearn.optimize.warnings module
---------------------------------

.. automodule:: catlearn.optimize.warnings
    :members:
    :undoc-members:
    :show-inheritance:


Module contents
---------------

.. automodule:: catlearn.optimize
    :members:
    :undoc-members:
    :show-inheritance:
