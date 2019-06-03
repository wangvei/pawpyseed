/** \file
Momentum matrix elements
*/

#ifndef MOMENTUM_H
#define MOMENTUM_H
#include <complex.h>
#include <math.h>

typedef struct transform_spline {
	double* transform;
	double** spline;
} transform_spline_t;

typedef struct density_ft {
	int n1;
	int l1;
	int m1;
	int n2;
	int l2;
	int m2;
	int size;
	double* ks;
	transform_spline_t* transforms; // size: sum(l1,l2)-diff(l1,l2)
} density_ft_t;

typedef struct density_ft_elem {
	int num_densities;
	int total_projs;
	density_ft_t* densities;
} density_ft_elem_t;

float complex pseudo_momentum(int* GP, int* G_bounds, double* lattice,
	int* G1s, float complex* C1s, int num_waves1,
	int* G2s, float complex* C2s, int num_waves2, int* fftg);

void mul_partial_waves(double* product, int size, double* r, double* f1, double* f2);

void make_rho(double* rho, int size, double* grid, double* aewave1, double* pswave1, double* aewave2, double* pswave2);

density_ft_t spher_transforms(int size, double* r, double* f, int l1, int m1, int l2, int m2, double encut);

double complex spher_momentum(density_ft_t densities, double* G, double* lattice);

density_ft_elem_t get_transforms(ppot_t pp, double encut);

density_ft_elem_t* get_all_transforms(pswf_t* wf, double encut);

double complex get_momentum_matrix_element(pswf_t* wf, int* labels, double* coords,
											int b1, int k1, int s1,
											int b2, int k2, int s2,
											int* GP, density_ft_elem_t* elems);

void get_momentum_matrix(double complex* matrix, int numg, int* igall,
						pswf_t* wf, int* labels, double* coords,
						int band1, int kpt1, int spin1,
						int band2, int kpt2, int spin2,
						density_ft_elem_t* transforms_list,
						double encut);

void momentum_grid_size(pswf_t* wf, double* nb1max, double* nb2max, double* nb3max,
						int* npmax, double encut);

int get_momentum_grid(int* igall, pswf_t* wf, double nb1max, double nb2max, double nb3max, double encut);

#endif
