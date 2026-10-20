import numpy as np
from scipy.integrate import solve_ivp
from scipy.special import erfc
D,KAP,GAM,V0=0.1,1.0,1.0,1.0
f=lambda x:0.1*(1-x**2); fp1=-0.2
R=lambda u:u*(1-u)
def cheb(N):
    x=np.cos(np.pi*np.arange(N+1)/N); c=np.hstack([2,np.ones(N-1),2])*(-1)**np.arange(N+1)
    X=np.tile(x,(N+1,1)).T; dX=X-X.T; Dm=np.outer(c,1/c)/(dX+np.eye(N+1)); Dm-=np.diag(Dm.sum(1)); return Dm,x
def solve(N,T,times):
    Dm,xc=cheb(N); x=(xc+1)/2  # x[0]=1 (boundary), x[N]=0
    Dx=2*Dm; D2=Dx@Dx
    # unknowns: interior u[1..N-1] and v ; boundary node 0 (x=1) algebraic via flux, node N (x=0) via Neumann
    def fill(ui,v):
        u=np.zeros(N+1); u[1:N]=ui
        # x=0 node N: Dx[N,:]@u=0
        # x=1 node 0: D*Dx[0,:]@u = KAP*(v-u0)
        A=np.array([[Dx[0,0],Dx[0,N]],[Dx[N,0],Dx[N,N]]]); 
        # unknowns u0,uN
        M=np.array([[D*Dx[0,0]+KAP, D*Dx[0,N]],[Dx[N,0],Dx[N,N]]])
        rhs=np.array([KAP*v-D*Dx[0,1:N]@ui, -Dx[N,1:N]@ui])
        u0,uN=np.linalg.solve(M,rhs); u[0]=u0;u[N]=uN; return u
    def rhs(t,y):
        ui=y[:-1]; v=y[-1]; u=fill(ui,v)
        du=D*(D2@u)+R(u)
        return np.hstack([du[1:N],KAP*(u[0]-v)-GAM*v**3])
    y0=np.hstack([f(x[1:N]),V0])
    s=solve_ivp(rhs,[0,T],y0,method='Radau',rtol=1e-12,atol=1e-14,t_eval=times)
    out=[]
    for k in range(len(times)):
        out.append((fill(s.y[:-1,k],s.y[-1,k]),s.y[-1,k]))
    return x,out
if __name__=="__main__":
    times=[1e-4,1e-3,0.05,0.1,0.25,0.5,1.0]
    x1,o1=solve(48,1,times); x2,o2=solve(96,1,times)
    xs=np.linspace(0,1,201)
    from numpy.polynomial import chebyshev as C
    def interp(x,u,xs):
        # barycentric via polyfit in cheb
        p=C.Chebyshev.fit(2*x-1,u,len(x)-1); return p(2*xs-1)
    for k,t in enumerate(times):
        print(t, np.max(np.abs(interp(x1,o1[k][0],xs)-interp(x2,o2[k][0],xs))), o2[k][0][0], f(1.0), o2[k][1])
    # sqrt(t) coefficient check
    dy=KAP*(f(1.0)-V0)+D*fp1  # Delta_y
    pred=-2*dy/np.sqrt(np.pi*D)
    for k,t in enumerate(times[:3]): print('coef',t,(o2[k][0][0]-f(1.0))/np.sqrt(t),pred)
