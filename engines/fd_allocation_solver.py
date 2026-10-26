"""Exact fixed-tenure comparison model for the existing simulation tab."""
from math import ceil, floor, isfinite


def solve_fixed_allocation(amount, candidates, caps, minimum, max_banks,
                           depositors, months, step, maturity, bank_key):
    """Solve minimum-ticket / maximum-bank choices jointly, without greedy fill.

    This helper compares fixed-tenure gross interest. The full-page family
    planner additionally models funding, tax, liquidity and official rates.
    """
    if not isfinite(amount) or amount < 0 or not isfinite(minimum) or minimum <= 0 or max_banks < 1:
        raise ValueError("Enter valid nonnegative money and positive bank/minimum limits.")
    if not candidates or amount < minimum:
        return [0.0] * len(candidates)
    try:
        import numpy as np
        from scipy.optimize import milp, Bounds, LinearConstraint
    except ImportError as exc:
        raise RuntimeError("FD optimization requires scipy. Install requirements.txt.") from exc
    n=len(candidates)
    objective=np.zeros(2*n)
    upper=np.ones(2*n)
    rows=[]; lo=[]; hi=[]
    def add(coefficients,lower=-np.inf,higher=np.inf):
        row=np.zeros(2*n)
        for index,value in coefficients.items():
            row[index]=value
        rows.append(row); lo.append(lower); hi.append(higher)
    for i,(rate,owner,bank) in enumerate(candidates):
        limit=floor(min(caps[i],amount)/step)
        upper[i]=limit
        objective[i]=-(maturity(1_000_000,rate,months,"Quarterly")/1_000_000-1)*step
        add({i:1,n+i:-limit},higher=0)
        add({i:1,n+i:-ceil(minimum/step)},lower=0)
    add({i:step for i in range(n)},higher=amount)
    for owner in range(len(depositors)):
        indices=[i for i,(_,pid,_) in enumerate(candidates) if pid==owner]
        add({n+i:1 for i in indices},higher=max_banks)
        available=depositors[owner].get("cash_available",amount)
        if not isfinite(available) or available < 0:
            raise ValueError("Review each owner's cash budget.")
        add({i:step for i in indices},higher=available)
        # Normalized aliases of a bank share one insurance bucket. The best
        # quote per legal bank is selected upstream, so one row is sufficient.
    result=milp(objective,integrality=np.ones(2*n),bounds=Bounds(np.zeros(2*n),upper),
                constraints=LinearConstraint(np.array(rows),lo,hi),
                options={"time_limit":15,"mip_rel_gap":0.00001})
    if result.x is None or result.status!=0:
        raise RuntimeError("Fixed-tenure solver did not prove a solution within tolerance; reduce the comparison size.")
    solution=np.rint(result.x)
    audit=np.array(rows)@solution
    if np.any(audit>np.array(hi)+.01) or np.any(audit<np.array(lo)-.01):
        raise RuntimeError("Fixed-tenure allocation failed its constraint audit.")
    return [float(solution[i]*step) for i in range(n)]
