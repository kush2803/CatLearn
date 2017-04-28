""" Functions to build a graph based on the neighbor list. """
from __future__ import absolute_import
from __future__ import division

import numpy as np
from mendeleev import element

from ase.data import covalent_radii


def get_neighborlist(atoms, dx=0.2, neighbor_number=1):
    """ Make dict of neighboring atoms. Possible to return neighbors from
        defined neighbor shell e.g. 1st, 2nd, 3rd.

        Parameters
        ----------
        atoms : object
            Target ase atoms object on which to get neighbor list.
        dx : float
            Buffer to calculate nearest neighbor pairs.
        neighbor_number : int
            NOT IMPLEMENTED YET.
    """
    conn = {}
    for atomi in atoms:
        conn_this_atom = []
        for atomj in atoms:
            if atomi.index != atomj.index:
                pi = np.asarray(atomi.position)
                pj = np.asarray(atomj.position)
                d = np.linalg.norm(pi - pj)
                cri = covalent_radii[atomi.number]
                crj = covalent_radii[atomj.number]
                if neighbor_number == 1:
                    d_max1 = 0.
                else:
                    d_max1 = ((neighbor_number - 1) * (crj + cri)) + dx
                d_max2 = (neighbor_number * (crj + cri)) + dx
                if d > d_max1 and d < d_max2:
                    conn_this_atom.append(atomj.index)
        conn[atomi.index] = conn_this_atom
    return conn


def connection_matrix(atoms, dx=0.2):
    """ Helper function to generate a connections matrix from an atoms object.

        Parameters
        ----------
        atoms : object
            Target ase atoms object on which to build the connections matrix.
        dx : float
            Buffer to calculate nearest neighbor pairs.
    """
    # Use ase.ga neighbor list generator.
    if 'neighborlist' in atoms.info['key_value_pairs']:
        nl = atoms.info['key_value_pairs']['neighborlist']
    else:
        nl = get_neighborlist(atoms, dx=dx)

    cm = []
    r = range(len(atoms))
    # Create binary matrix denoting connections.
    for i in r:
        x = []
        for j in r:
            if j in nl[i]:
                x.append(1.)
            else:
                x.append(0.)
        cm.append(x)

    return np.asarray(cm)


def element_list(an, no):
    """ Function to transform list of atom numbers into binary list with one
        for given type, zero for all others. Maps homoatomic interactions.

        Parameters
        ----------
        an : list
            List of atom numbers.
        no : int
            Select atom number.
    """
    hm = []
    for n in an:
        if n == no:
            hm.append(1.)
        else:
            hm.append(0.)

    return hm


def heteroatomic_matrix(an, el):
    """ Function to transform list of atom numbers into binary list with one
        for interactions between two different types, zero for all others. Maps
        heteroatomic interactions.

        Parameters
        ----------
        an : list
            List of atom numbers.
        el : list
            List of two atom numbers on which to map interactions.
    """
    hm = []
    for i in an:
        if i == el[0]:
            x = []
            for j in an:
                if j != el[0]:
                    x.append(1.)
                else:
                    x.append(0.)
        else:
            x = [0] * len(an)
        hm.append(x)

    return np.asarray(hm)


def generalized_matrix(cm):
    """ Get the generalized coordination matrix.

        Parameters
        ----------
        cm : array
            The connections matrix.
    """
    gm = []
    for i in cm:
        tot = 0.
        for j in range(len(i)):
            if i[j] != 0.:
                tot += sum(i)
        gm.append(tot / 12.)

    return np.asarray(gm)


def property_matrix(atoms, property):
    """ Generate a property matrix based on the atomic types.

        Parameters
        ----------
        atoms : object
            The target ase atoms opject.
        property : str
            The target property from mendeleev.
    """
    sy = atoms.get_chemical_symbols()
    ce = {}
    for s in set(sy):
        ce[s] = eval('element("' + s + '").' + property)

    x = []
    for s in sy:
        x.append(ce[s])
    pm = [x] * len(atoms)

    return np.asarray(np.float64(pm))


def get_features(an, cm, sum_cm, gen_cm):
    """ Function to generate the actual feature vector.

        Parameters
        ----------
        an : list
            Ordered list of atomic numbers.
        cm : array
            The coordination matrix.
        sum_cm : list
            The summed vectors of the coordination matrix.
        gen_cm : array
            The generalized coordination matrix.
    """
    fp = []
    # Get level one fingerprint. Sum of coordination for each atom type.
    done = []
    for e in set(an):
        el = element_list(an, e)
        x = np.array(sum_cm) * np.array(el)
        fp.append(np.sum(x))
        fp.append(np.sum(x ** 2))
        fp.append(np.sum(x ** 0.5))

        # Get level two fingerprint. Total AA, AB, BB etc bonds.
        pt = np.array(([el] * len(an)))
        em = np.sum(np.sum(pt * np.array(cm), axis=1))
        fp.append(em)
        if e not in done:
            done.append(e)
        for eo in set(an):
            if eo not in done:
                hm = heteroatomic_matrix(an, [e, eo])
                fp.append(np.sum(np.sum(np.array(hm) * np.array(cm),
                                        axis=1)))

        # Get level three fingerprint. Generalized coordination number.
        x = np.array(gen_cm) * np.array(el)
        fp.append(np.sum(x))
        fp.append(np.sum(x ** 2))
        fp.append(np.sum(x ** 0.5))

    return fp


def base_f(atoms, property=None):
    """ Function to generate features from atoms objects.

        Parameters
        ----------
        atoms : object
            The target ase atoms object.
        property : list
            List of the target properties from mendeleev.
    """
    fp = []

    # Generate the required data from atoms object.
    an = atoms.get_atomic_numbers()
    cm_store = connection_matrix(atoms, dx=0.2)
    sum_cm = np.sum(cm_store, axis=1)
    gen_cm = generalized_matrix(cm_store)

    fp += get_features(an=an, cm=cm_store, sum_cm=sum_cm, gen_cm=gen_cm)

    if property is not None:
        for p in property:
            pm = property_matrix(atoms=atoms, property=p)
            cm = cm_store * pm
            sum_cm = np.sum(cm, axis=1)
            gen_cm = generalized_matrix(cm)

            fp += get_features(an=an, cm=cm, sum_cm=sum_cm, gen_cm=gen_cm)

    return np.asarray(fp)
