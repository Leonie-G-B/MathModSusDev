
# Just having a play around with the practice codes and understanding the logic 


# we know lambda can VARY between 8 and 16 - how do we want to approach this information? 
# eiither way, lambda needs to be a value that can easily be varied (and iterated upon?)

# to iterate, should the entire process be repeatable and results independent of number of trials? 


### Nomenclature: inputs ###

# Standard inputs
import numpy as np

# Simulation specifics
from collections import deque




# BLAH BLAH BLAH 


class ClinicSim: 
    def __init__(sim, lambda_base: int, appointment_time: int, num_clinicians: int, 
                 peak_multiplier: int = None, #should be 2,4,8 - use checking?
                 open_close: tuple[float, float] = (8.0, 17.5),
                 peak_hrs: tuple[float, float] = (10.0, 14.0)):
        sim.lambda_base = lambda_base
        sim.mu = 60/appointment_time #hourly rate
        sim.num_clinicians = num_clinicians

        sim.peak_multiplier = peak_multiplier
        sim.peak_start = peak_hrs[0]
        sim.peak_end = peak_hrs[1]

        sim.open_time = open_close[0]
        sim.close_time = open_close[1]

        # sim.clock = 0  #time stepping log
        sim.clock = sim.open_time # start at the start!
        
        sim.queue = deque()
        sim.waits = []# list of the waiting times

        sim.num_in_system = 0
        sim.sys_state = [(sim.clock,0)] #tuples, (time, no. patients in queue) 

        sim.arrival_times = []
        sim.departure_times = [] #just for data logging reasons

        sim.servers = [None] * sim.num_clinicians #none indicates free server

        sim.t_arrival = sim.clock + sim.generate_interarrival()


    ####################################################################

    def get_lambda(sim):
        if sim.peak_start <= sim.clock <= sim.peak_end:
            if sim.peak_multiplier is not None: 
                multiplier = sim.peak_multiplier
            else:
                multiplier = np.random.choice([2,3,4]) #" the number of patient arrivals can douple, triple, or even quadruple"
            return sim.lambda_base * multiplier
        return sim.lambda_base

    def generate_interarrival(sim):
        lam = sim.get_lambda()
        return np.random.exponential(1 / lam)

    def generate_service(sim):
        return np.random.exponential(1 / sim.mu)
    
    ####################################################################

    def arrival(sim):
        sim.num_in_system += 1
        sim.queue.append(sim.clock)
        sim.arrival_times.append(sim.clock)

        # check for free clinician
        for i in range(sim.num_clinicians):
            if sim.servers[i] is None:
                arrival_time = sim.queue.popleft()
                service_time = sim.generate_service()
                sim.servers[i] = sim.clock + service_time

                wait = sim.clock - arrival_time
                sim.waits.append(wait)
                break

        sim.t_arrival = sim.clock + sim.generate_interarrival()

    def departure(sim, clinician_id):
        sim.num_in_system -= 1
        sim.departure_times.append(sim.clock)

        if sim.queue:
            arrival_time = sim.queue.popleft()

            service_time = sim.generate_service()
            sim.servers[clinician_id] = sim.clock + service_time

            wait = sim.clock - arrival_time
            sim.waits.append(wait)
        else:
            sim.servers[clinician_id] = None


    ####################################################################

    def step(sim): #discrete time event - we just jump to the next time where *something* happens
        active_departures = [t for t in sim.servers if t is not None] #find NEXT departure
        next_depart = min(active_departures) if active_departures else float('inf')

        if sim.t_arrival <= next_depart and sim.t_arrival <= sim.close_time: #if arrival happens next (before available server) and its before closing
            sim.clock = sim.t_arrival
            sim.arrival() #jump to arrival time and initiate arrival 
        else:
            sim.clock = next_depart
            clinician_id = sim.servers.index(next_depart)
            sim.departure(clinician_id) 

        # Record system state (queue length OR total system)
        sim.sys_state.append((sim.clock, sim.num_in_system))


# use a random seed to allow reproducibility! 

np.random.seed(64) #my fave number

simulation = ClinicSim(
    lambda_base=8,
    appointment_time=30, #mins
    num_clinicians= 6,
    peak_multiplier=4
)

while simulation.clock < simulation.close_time: 
    simulation.step()


print("Sim finished")



##########################################################################################

# Plotting 


import matplotlib.pyplot as plt
import numpy as np



def plot_simulation_1(sim):

    fig, ax = plt.subplots(figsize=(12,6))

    times, values = zip(*sim.sys_state)

    ax.step(times, values, where='post', label="Patients in system")

    arrival_sorted = np.sort(sim.arrival_times)
    departure_sorted = np.sort(sim.departure_times)

    ax.step(arrival_sorted, np.arange(1, len(arrival_sorted)+1),
            where='post', linestyle='--', label="Cumulative arrivals")

    ax.step(departure_sorted, np.arange(1, len(departure_sorted)+1),
            where='post', linestyle=':', label="Cumulative departures")

    ax.axvspan(sim.peak_start, sim.peak_end, alpha=0.2) # peak hours

    ax.set_xticks(np.arange(sim.open_time, sim.close_time + 0.5, 0.5)) #grid (30min intervals)
    ax.grid(True, which='both', axis='x', linestyle='--', alpha=0.5)

    ax.legend()

    ax.set_title(f"Patient arrival, departures, and total system capacity for flat rate peak multiplier = {simulation.peak_multiplier}.")

    print("Finished plotting")

########################################################################################

#### Want to now run n sims with the same inputs, but getting a better view of things bc of averagine from the random nature of the model 



# compute metrics method for one sim result
def compute_sim_result_metrics(sim: ClinicSim) -> dict[str, float]:
    waits = np.array(sim.waits)

    peaks = [n for (_, n) in sim.sys_state]

    eod_patients = sim.num_in_system # this is EOD value by defualt if sim is complete

    patients_served = len(sim.departure_times) #every departure is a patient served

    return {
        "avg_wait" : waits.mean(),
        "peak" : max(peaks),
        "eod_patients" : eod_patients,
        "patients_served" : patients_served
    }


# run a load of sims

def run_multisim_avg(n_sims: int, **kwargs): 
    """
    Run n simulations and compute and return the average metrics. All inputs are the same.

    Inputs: 
        n_sims(int) = Number of sims to run. 
        **kwargs = simulation input args (for all sims). 
    """

    results = {}

    for i in range(n_sims): 
        np.random.seed(i)

        sim = ClinicSim(**kwargs)
        
        while sim.clock < sim.close_time:
            sim.step()

        metrics = compute_sim_result_metrics(sim)
        results[i] = metrics 

    return results


# run n sims with 