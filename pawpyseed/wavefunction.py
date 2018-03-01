"""
Base class containing Python classes for parsing files
and storing and analyzing wavefunction data.
"""

from pymatgen.io.vasp.inputs import Potcar, Poscar
from pymatgen.io.vasp.outputs import Vasprun
from pymatgen.core.structure import Structure
import numpy as np
from ctypes import *
from utils import *
import os
import numpy as np
import json

import sys
sys.stdout.flush()

class Pseudopotential:
	"""
	Contains important attributes from a VASP pseudopotential files. POTCAR
	"settings" can be read from the pymatgen POTCAR object

	Note: for the following attributes, 'index' refers to an energy
	quantum number epsilon and angular momentum quantum number l,
	which define one set consisting of a projector function, all electron
	partial waves, and pseudo partial waves.

	Attributes:
		rmaxstr (str): Maximum radius of the projection operators, as string
			of double precision float
		grid (np.array): radial grid on which partial waves are defined
		aepotential (np.array): All electron potential defined radially on grid
		aecorecharge (np.array): All electron core charge defined radially
			on grid (i.e. charge due to core, and not valence, electrons)
		kinetic (np.array): Core kinetic energy density, defined raidally on grid
		pspotential (np.array): pseudopotential defined on grid
		pscorecharge (np.array): pseudo core charge defined on grid
		ls (list): l quantum number for each index
		pswaves (list of np.array): pseudo partial waves for each index
		aewaves (list of np.array): all electron partial waves for each index
		projgrid (np.array): radial grid on which projector functions are defined
		recipprojs (list of np.array): reciprocal space projection operators
			for each index
		realprojs (list of np.array): real space projection operators
			for each index
	"""

	def __init__(self, data, rmax):
		nonradial, radial = data.split("PAW radial sets", 1)
		partial_waves = radial.split("pseudo wavefunction")
		gridstr, partial_waves = partial_waves[0], partial_waves[1:]
		self.rmax = rmax
		self.pswaves = []
		self.aewaves = []
		self.recipprojs = []
		self.realprojs = []
		self.nonlocalprojs = []
		self.ls = []
		self.rmaxstrs = []

		auguccstr, gridstr = gridstr.split("grid", 1)
		gridstr, aepotstr = gridstr.split("aepotential", 1)
		aepotstr, corechgstr = aepotstr.split("core charge-density", 1)
		corechgstr, kenstr = corechgstr.split("kinetic energy-density", 1)
		kenstr, pspotstr = kenstr.split("pspotential", 1)
		pspotstr, pscorechgstr = pspotstr.split("core charge-density (pseudized)", 1)
		self.grid = self.make_nums(gridstr)
		self.aepotential = self.make_nums(aepotstr)
		self.aecorecharge = self.make_nums(corechgstr)
		self.kinetic = self.make_nums(kenstr)
		self.pspotential = self.make_nums(pspotstr)
		self.pscorecharge = self.make_nums(pscorechgstr)

		augstr, uccstr = auguccstr.split('uccopancies in atom', 1)
		head, augstr = augstr.split('augmentation charges (non sperical)', 1)
		self.augs = self.make_nums(augstr)

		for pwave in partial_waves:
			lst = pwave.split("ae wavefunction", 1)
			self.pswaves.append(self.make_nums(lst[0]))
			self.aewaves.append(self.make_nums(lst[1]))

		projstrs = nonradial.split("Non local Part")
		topstr, projstrs = projstrs[0], projstrs[1:]
		self.T = float(topstr[-22:-4])
		topstr, atpschgstr = topstr[:-22].split("atomic pseudo charge-density", 1)
		topstr, corechgstr = topstr.split("core charge-density (partial)", 1)
		settingstr, localstr = topstr.split("local part", 1)
		localstr, self.gradxc = localstr.split("gradient corrections used for XC", 1)
		self.gradxc = int(self.gradxc)
		self.localpart = self.make_nums(localstr)
		self.localnum = self.localpart[0]
		self.localpart = self.localpart[1:]
		self.coredensity = self.make_nums(corechgstr)
		self.atomicdensity = self.make_nums(atpschgstr)

		for projstr in projstrs:
			lst = projstr.split("Reciprocal Space Part")
			nonlocalvals, projs = lst[0], lst[1:]
			self.rmaxstr = c_char_p()
			self.rmaxstr.value = nonlocalvals.split()[2].encode('utf-8')
			nonlocalvals = self.make_nums(nonlocalvals)
			l = nonlocalvals[0]
			count = nonlocalvals[1]
			self.nonlocalprojs.append(nonlocalvals[2:])
			for proj in projs:
				recipproj, realproj = proj.split("Real Space Part")
				self.recipprojs.append(self.make_nums(recipproj))
				self.realprojs.append(self.make_nums(realproj))
				self.ls.append(l)

		settingstr, projgridstr = settingstr.split("STEP   =")
		self.ndata = int(settingstr.split()[-1])
		projgridstr = projgridstr.split("END")[0]
		self.projgrid = self.make_nums(projgridstr)
		self.step = (self.projgrid[0], self.projgrid[1])

		self.projgrid = np.linspace(0,rmax/1.88973,self.ndata,False,dtype=np.float64)

	def make_nums(self, numstring):
		return np.array([float(num) for num in numstring.split()])

class CoreRegion:
	"""
	List of Pseudopotential objects to describe the core region of a structure.

	Attributes:
		pps (dict of Pseudopotential): keys are element symbols,
			values are Pseudopotential objects
	"""

	def __init__(self, potcar):
		self.pps = {}
		for potsingle in potcar:
			self.pps[potsingle.element] = Pseudopotential(potsingle.data[:-15], potsingle.rmax)
		

class PseudoWavefunction:
	"""
	Class for storing pseudowavefunction from WAVECAR file. Most important attribute
	is wf_ptr, a C pointer used in the C portion of the program for storing
	plane wave coefficients

	Attributes:
		kpts (np.array): nx3 array of fractional kpoint vectors,
			where n is the number of kpoints
		kws (np.array): weight of each kpoint
		wf_ptr (ctypes POINTER): c pointer to pswf_t object
	"""

	def __init__(self, filename="WAVECAR", vr="vasprun.xml"):
		if type(vr) == str:
			vr = Vasprun(vr)
		weights = vr.actual_kpoints_weights
		kws = (c_double * len(weights))()
		for i in range(len(weights)):
			kws[i] = weights[i]
		self.kws = weights
		self.kpts = vr.actual_kpoints
		self.wf_ptr = PAWC.read_wavefunctions(filename.encode('utf-8'), byref(kws))

	def pseudoprojection(self, band_num, basis):
		"""
		Computes <psibt_n1k|psit_n2k> for all n1 and k
		and a given n2, where psibt are basis structures
		pseudowavefunctions and psit are self pseudowavefunctions

		Arguments:
			band_num (int): n2 (see description)
			basis (Pseudowavefunction): pseudowavefunctions onto whose bands
				the band of self is projected
		"""
		nband = PAWC.get_nband(c_void_p(self.wf_ptr))
		nwk = PAWC.get_nwk(c_void_p(self.wf_ptr))
		nspin = PAWC.get_nspin(c_void_p(self.wf_ptr))

		res = PAWC.pseudoprojection(c_void_p(basis.wf_ptr), c_void_p(self.wf_ptr), band_num)
		return cdouble_to_numpy(res, 2*nband*nwk*nspin)

class Wavefunction:
	"""
	Class for storing and manipulating all electron wave functions in the PAW
	formalism.

	Attributes:
		structure (pymatgen.core.structure.Structure): stucture of the material
			that the wave function describes
		pwf (PseudoWavefunction): Pseudowavefunction componenet
		cr (CoreRegion): Contains the pseudopotentials, with projectors and
			partials waves, for the structure
		projector: ctypes object for interfacing with C code
	"""

	def __init__(self, struct, pwf, cr, dim):
		"""
		Arguments:
			struct (pymatgen.core.Structure): structure that the wavefunction describes
			pwf (PseudoWavefunction): Pseudowavefunction componenet
			cr (CoreRegion): Contains the pseudopotentials, with projectors and
				partials waves, for the structure
		Returns:
			Wavefunction object
		"""
		self.structure = struct
		self.pwf = pwf
		self.cr = cr
		self.projector = PAWC
		self.dim = np.array(dim);
		self.projector_list = None

	def from_files(self, struct="CONTCAR", pwf="WAVECAR", cr="POTCAR", vr="vasprun.xml"):
		"""
		Construct a Wavefunction object from file paths.
		Arguments:
			struct (str): VASP POSCAR or CONTCAR file path
			pwf (str): VASP WAVECAR file path
			vr (str): VASP vasprun file path
		Returns:
			Wavefunction object
		"""
		return Wavefunction(Poscar.from_file(struct), PseudoWavefunction(pwf, vr), Potcar.from_file(cr))

	def make_site_lists(self, basis):
		"""
		Organizes sites into sets for use in the projection scheme. M_R and M_S contain site indices
		of sites which are identical in structures R (basis) and S (self). N_R and N_S contain all other
		site indices, and N_RS contains pairs of indices in R and S with overlapping augmentation
		spheres in the PAW formalism.

		Arguments:
			basis (Wavefunction object): Wavefunction in the same lattice as self.
				The bands in self will be projected onto the bands in basis
		Returns:
			M_R (numpy array): Indices of sites in basis which have an identical site in
				S (self) (same element and position to within tolerance of 0.02 Angstroms).
			M_S (numpy array): Indices of sites in self which match sites in M_R
				(i.e. M_R[i] is an identical site to M_S[i])
			N_R (numpy array): Indices of sites in basis but not in M_R
			N_S (numpy array): Indices of sites in self but not in M_S
			N_RS (numpy array): Pairs of indices (one in basis and one in self) which
				are not identical but have overlapping augmentation regions
		"""
		ref_sites = basis.structure.sites
		sites = self.structure.sites
		M_R = []
		M_S = []
		for i in range(len(ref_sites)):
			for j in range(len(sites)):
				if ref_sites[i].distance(sites[j]) <= 0.02 and el(ref_sites[i]) == el(sites[j]):
					M_R.append(i)
					M_S.append(j)
		N_R = []
		N_S = []
		for i in range(len(ref_sites)):
			if not i in M_R:
				N_R.append(i)
			for j in range(len(sites)):
				if (not j in N_S) and (not j in M_S):
					N_S.append(j)
		N_RS = []
		for i in N_R:
			for j in N_S:
				if ref_sites[i].distance(sites[j]) < self.cr.pps[el(ref_sites[i])].rmax + self.cr.pps[el(sites[j])].rmax:
					N_RS.append((i,j))
		return M_R, M_S, N_R, N_S, N_RS

	def setup_projection(self, basis):
		"""
		Evaluates projectors <p_i|psi>, as well
		as <(phi-phit)|psi> and <(phi_i-phit_i)|(phi_j-phit_j)>,
		when needed

		Arguments:
			basis (Wavefunction): wavefunction onto which bands of self
			will be projected.
		"""

		projector_list, selfnums, selfcoords, basisnums, basiscoords = self.make_c_projectors(basis)
		print(selfnums, selfcoords, basisnums, basiscoords)
		print(hex(projector_list), hex(self.pwf.wf_ptr))
		sys.stdout.flush()
		self.projector.setup_projections(c_void_p(self.pwf.wf_ptr), c_void_p(projector_list), len(self.cr.pps),
			len(self.structure), numpy_to_cint(self.dim), numpy_to_cint(selfnums),
			numpy_to_cdouble(selfcoords))
		self.projector.setup_projections(c_void_p(basis.pwf.wf_ptr), c_void_p(projector_list), len(self.cr.pps),
			len(basis.structure), numpy_to_cint(self.dim), numpy_to_cint(basisnums),
			numpy_to_cdouble(basiscoords))
		self.projection_data = [projector_list, selfnums, selfcoords, basisnums, basiscoords]
		M_R, M_S, N_R, N_S, N_RS = self.make_site_lists(basis)
		num_N_RS = len(N_RS)
		if num_N_RS > 0:
			N_RS_R, N_RS_S = zip(*N_RS)
		else:
			N_RS_R, N_RS_S = [], []
		self.site_cat = [M_R, M_S, N_R, N_S, N_RS_R, N_RS_S]
		self.projector.overlap_setup(c_void_p(basis.pwf.wf_ptr), c_void_p(self.pwf.wf_ptr), c_void_p(projector_list),
			numpy_to_cint(basisnums), numpy_to_cint(selfnums),
			numpy_to_cdouble(basiscoords), numpy_to_cdouble(selfcoords),
			numpy_to_cint(N_R), numpy_to_cint(N_S),
			numpy_to_cint(N_RS_R), numpy_to_cint(N_RS_S), len(N_R), len(N_S), len(N_RS_R));
			#numpy_to_cint(M_R), numpy_to_cint(M_S),
                        #numpy_to_cint(M_R), numpy_to_cint(M_S), len(M_R), len(M_R), len(M_R));

	def single_band_projection(self, band_num, basis):
		"""
		All electron projection of the band_num band of self
		onto all the bands of basis. Returned as a numpy array,
		with the overlap operator matrix elements ordered as follows:
		loop over band
			loop over spin
				loop over kpoint

		Arguments:
			band_num (int): band which is projected onto basis
			basis (Wavefunction): basis Wavefunction object

		Returns:
			res (np.array): overlap operator expectation values
				as described above
		"""

		res = self.projector.pseudoprojection(c_void_p(basis.pwf.wf_ptr), c_void_p(self.pwf.wf_ptr), band_num)
		nband = self.projector.get_nband(c_void_p(basis.pwf.wf_ptr))
		nwk = self.projector.get_nwk(c_void_p(basis.pwf.wf_ptr))
		nspin = self.projector.get_nspin(c_void_p(basis.pwf.wf_ptr))
		res = cdouble_to_numpy(res, 2*nband*nwk*nspin)
		print("datsa", nband, nwk, nspin)
		sys.stdout.flush()
		projector_list, selfnums, selfcoords, basisnums, basiscoords = self.projection_data
		M_R, M_S, N_R, N_S, N_RS_R, N_RS_S = self.site_cat
		
		ct = self.projector.compensation_terms(band_num, c_void_p(self.pwf.wf_ptr), c_void_p(basis.pwf.wf_ptr), c_void_p(projector_list), 
			len(self.cr.pps), len(M_R), len(N_R), len(N_S), len(N_RS_R), numpy_to_cint(M_R), numpy_to_cint(M_S),
			numpy_to_cint(N_R), numpy_to_cint(N_S), numpy_to_cint(N_RS_R), numpy_to_cint(N_RS_S),
			numpy_to_cint(selfnums), numpy_to_cdouble(selfcoords),
			numpy_to_cint(basisnums), numpy_to_cdouble(basiscoords),
			numpy_to_cint(self.dim))
		"""
		ct = self.projector.compensation_terms(band_num, c_void_p(self.pwf.wf_ptr), c_void_p(basis.pwf.wf_ptr), c_void_p(projector_list), 
			len(self.cr.pps), 0, len(M_R), len(M_S), len(M_S), numpy_to_cint([]), numpy_to_cint([]),
			numpy_to_cint(M_R), numpy_to_cint(M_S), numpy_to_cint(M_R), numpy_to_cint(M_S),
			numpy_to_cint(selfnums), numpy_to_cdouble(selfcoords),
			numpy_to_cint(basisnums), numpy_to_cdouble(basiscoords),
			numpy_to_cint(self.dim))
		"""
		ct = cdouble_to_numpy(ct, 2*nband*nwk*nspin)
		res += ct
		return res[::2] + 1j * res[1::2]

	def make_c_projectors(self, basis=None):
		"""
		Uses the CoreRegion objects in self and basis (if not None)
		to construct C representations of the projectors and partial waves
		for a structure. Also assigns numerical labels for each element and
		returns a list of indices and positions which can be easily converted
		to C lists for projection functions.

		Arguments:
			basis (None or Wavefunction): an additional structure from which
				to include pseudopotentials. E.g. can be useful if a basis contains
				some different elements than self.
		Returns:
			projector_list (C pointer): describes the pseudopotential data in C
			selfnums (int32 numpy array): numerical element label for each site in
				the structure
			selfcoords (float64 numpy array): flattened list of coordinates of each site
				in self
			basisnums (if basis != None): same as selfnums, but for basis
			basiscoords (if basis != None): same as selfcoords, but for basis
		"""
		pps = {}
		labels = {}
		label = 0
		for e in self.cr.pps:
			pps[label] = self.cr.pps[e]
			labels[e] = label
			label += 1
		print (pps, labels)
		if basis != None:
			for e in basis.cr.pps:
				if not e in labels:
					pps[label] = basis.cr.pps[e]
					labels[e] = label
					label += 1
		clabels = np.array([], np.int32)
		ls = np.array([], np.int32)
		projectors = np.array([], np.float64)
		aewaves = np.array([], np.float64)
		pswaves = np.array([], np.float64)
		wgrids = np.array([], np.float64)
		pgrids = np.array([], np.float64)
		augs = np.array([], np.float64)
		rmaxstrs = (c_char_p * len(pps))()
		num_els = 0

		for num in pps:
			pp = pps[num]
			clabels = np.append(clabels, [num, len(pp.ls), pp.ndata, len(pp.grid)])
			rmaxstrs[num_els] = pp.rmaxstr
			ls = np.append(ls, pp.ls)
			wgrids = np.append(wgrids, pp.grid)
			pgrids = np.append(pgrids, pp.projgrid)
			augs = np.append(augs, pp.augs)
			num_els += 1
			for i in range(len(pp.ls)):
				proj = pp.realprojs[i]
				aepw = pp.aewaves[i]
				pspw = pp.pswaves[i]
				projectors = np.append(projectors, proj)
				aewaves = np.append(aewaves, aepw)
				pswaves = np.append(pswaves, pspw)

		projector_list = self.projector.get_projector_list(num_els, numpy_to_cint(clabels),
			numpy_to_cint(ls), numpy_to_cdouble(pgrids), numpy_to_cdouble(wgrids),
			numpy_to_cdouble(projectors), numpy_to_cdouble(aewaves), numpy_to_cdouble(pswaves),
			rmaxstrs)
		selfnums = np.array([labels[el(s)] for s in self.structure], dtype=np.int32)
		basisnums = np.array([labels[el(s)] for s in basis.structure], dtype=np.int32)
		selfcoords = np.array([], np.float64)
		basiscoords = np.array([], np.float64)

		for s in self.structure:
			selfcoords = np.append(selfcoords, s.frac_coords)
		if basis != None:
			for s in basis.structure:
				basiscoords = np.append(basiscoords, s.frac_coords)
			return projector_list, selfnums, selfcoords, basisnums, basiscoords
		return projector_list, selfnums, selfcoords

	def proportion_conduction(self, band_num, bulk, pseudo = False):
		"""
		Calculates the proportion of band band_num in self
		that projects onto the valence states and conduction
		states of bulk. Designed for analysis of point defect
		wavefunctions.

		Arguments:
			band_num (int): number of defect band in self
			bulk (Wavefunction): wavefunction of bulk crystal
				with the same lattice and basis set as self

		Returns:
			v, c (int, int): The valence (v) and conduction (c)
				proportion of band band_num
		"""

		nband = self.projector.get_nband(c_void_p(bulk.pwf.wf_ptr))
		nwk = self.projector.get_nwk(c_void_p(bulk.pwf.wf_ptr))
		nspin = self.projector.get_nspin(c_void_p(bulk.pwf.wf_ptr))
		occs = cdouble_to_numpy(self.projector.get_occs(c_void_p(bulk.pwf.wf_ptr)), nband*nwk*nspin)
		if pseudo:
			res = self.pwf.pseudoprojection(band_num, bulk.pwf)
		else:
			res = self.single_band_projection(band_num, bulk)

		c, v = 0, 0
		for i in range(nband*nwk*nspin):
			if occs[i] > 0.5:
				v += np.absolute(res[i]) ** 2 * self.pwf.kws[i%nwk] / nspin
			else:
				c += np.absolute(res[i]) ** 2 * self.pwf.kws[i%nwk] / nspin
		if pseudo:
			v /= v+c
			c /= v+c
		return v, c

	def defect_band_analysis(self, bulk, bound = 0.05):
		"""
		Identifies a set of 'interesting' bands in a defect structure
		to analyze by choosing any band that is more than bound conduction
		and more than bound valence in the pseudoprojection scheme,
		and then fully analyzing these bands using single_band_projection
		"""
		nband = self.projector.get_nband(c_void_p(bulk.pwf.wf_ptr))
		nwk = self.projector.get_nwk(c_void_p(bulk.pwf.wf_ptr))
		nspin = self.projector.get_nspin(c_void_p(bulk.pwf.wf_ptr))
		totest = set()

		for b in range(nband):
			v, c = self.proportion_conduction(b, bulk, pseudo = True)
			if v > bound and c > bound:
				totest.add(b)
				totest.add(b-1)
				totest.add(b+1)
		print("NUM TO TEST", len(totest))

		results = {}
		for b in totest:
			results[b] = self.proportion_conduction(b, bulk, pseudo = False)

		return results

	def free_all(self):
		"""
		Frees all of the C structures associated with the Wavefunction object.
		After being called, this object is not usable.
		"""
		self.projector.free_pswf(c_void_p(self.pwf.wf_ptr))
		if self.projector_list != None:
			self.projector.free_ppot_list(c_void_p(self.projector_list), len(self.cr.pps))

if __name__ == '__main__':
	posb = Poscar.from_file("bulk/CONTCAR").structure
	posd = Poscar.from_file("charge_0/CONTCAR").structure
	pot = Potcar.from_file("bulk/POTCAR")
	pwf1 = PseudoWavefunction("bulk/WAVECAR", "bulk/vasprun.xml")
	pwf2 = PseudoWavefunction("charge_0/WAVECAR", "charge_0/vasprun.xml")

	wf1 = Wavefunction(posb, pwf1, CoreRegion(pot), (120,120,120))
	wf2 = Wavefunction(posd, pwf2, CoreRegion(pot), (120,120,120))
	wf2.setup_projection(wf1)
	print(wf2.defect_band_analysis(wf1))
	#for i in range(253,254):
	#	wf2.single_band_projection(i, wf1)

	wf1.free_all()
	wf2.free_all()
