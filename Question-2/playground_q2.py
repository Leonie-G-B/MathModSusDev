
## Question 2: Climate modelling 

# Equation: dh/dt = P - (r(To + delT(T) - Tm)^2)/h - Fh

# Set equal to zero and rearrange, then find discriminant etc 

## Imports

import sympy as sym 



# symbols
P, r, T0, dT, Tm, h, F = sym.symbols('P, r, T0, dT, Tm, h, F') #, positive = True)

dh_dt = P - (( r *(T0 + dT - Tm) **2 )/h) - (F*h)
func = sym.simplify(dh_dt * h)

discr = sym.discriminant(func, h) 
#dont be alarmed, this is just expanded form of:
# P^2 -4Fr(T0 + dT -Tm)^2

# Find real roots: 
rl_rts = sym.real_root(discr)

t_cond = sym.solve(discr, dT)


print(discr)

