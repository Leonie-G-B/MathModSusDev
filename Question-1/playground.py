
# Just having a play around with the practice codes and understanding the logic 


# we know lambda can VARY between 8 and 16 - how do we want to approach this information? 
# eiither way, lambda needs to be a value that can easily be varied (and iterated upon?)

# to iterate, should the entire process be repeatable and results independent of number of trials? 


### Nomenclature: inputs ###

# Standard inputs
import numpy as np
from typing import Literal, TypedDict
from enum import StrEnum

# Simulation specifics
from collections import deque


class ServiceMethods(StrEnum): 
    EXPONENTIAL = "exponential"
    LOGNORMAL = "lognormal"    
    NORMAL = "normal"

class ClinicianConfig(TypedDict): # define a type of shift for n number of clinicians
    shift_pattern : tuple[float, float] # list of (start, end)
    appointment_length : float # in minutes, list must match 


class Clinician: 
    def __init__(self, id, appointment_time: int, 
                 shift_start: float,
                 shift_end: float):
        self.id : int = id
        self.mu : float = 60/appointment_time
        
        self.shift_start : float = shift_start
        self.shift_end   : float = shift_end

        self.available : bool = True
        self.next_available: float = None #float time of when they are next free

        self.total_appointment_time : float = 0.0
        self.total_downtime : float = 0.0
        self.last_event_time : float = shift_start #to calculate downtime between appointments

    def generate_service(self):
        return np.random.exponential(1 / self.mu)
    
    def appointment_start(self, current_time: float): 
        self.total_downtime += current_time - self.last_event_time #assuming last event is finihsing an appointment

        self.available = False
        self.last_event_time = current_time

    def appointment_end(self, current_time: float):
        self.total_appointment_time += current_time - self.last_event_time #we could assume apppointment length but this is more foolproof incase of different EOD behaviour

        self.available = True
        self.last_event_time = current_time

class ClinicSim: 
    def __init__(sim, lambda_base: int, appointment_time: int, 
                 service_method: ServiceMethods = "exponential",
                 peak_multiplier: int = None, #should be 2,4,8 - use checking?
                 open_close: tuple[float, float] = (8.0, 17.5),
                 peak_hrs: tuple[float, float] = (10.0, 14.0), **kwargs):
        
        sim.lambda_base = lambda_base
        sim.lambdas_t = []
        
        sim.peak_multiplier = peak_multiplier
        sim.peak_start = peak_hrs[0]
        sim.peak_end = peak_hrs[1]

        sim.mu = 60/appointment_time #hourly rate
        # sim.num_clinicians = num_clinicians

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

        sim.self_set_service_method(service_method, **kwargs) #can pass in "logn_simga" for example

        # sim.servers = [None] * sim.num_clinicians #none indicates free server
        sim.clinicians: list[Clinician] = []

        sim.t_arrival = sim.clock + sim.generate_interarrival()


    def self_set_service_method(sim, method: ServiceMethods, **kwargs): 
        if method == "exponential": 
            sim._service_func = lambda: np.random.exponential(1 / sim.mu)
        elif method == "lognormal": 
            sim._service_func = lambda: np.random.lognormal(mean= np.log(60/sim.mu), sigma=kwargs.get("logn_sigma", 0.5))
        elif method == "normal": 
            sim._service_func = lambda: max(0, np.random.normal(loc=60/sim.mu, scale= kwargs.get("norm_scale", 0.5)*(60/sim.mu)))

    ####################################################################

    def create_clinicians(sim, n_clinicians: int, config: ClinicianConfig):
        cur_in_list = len(sim.clinicians)
        for i in range(n_clinicians):
            sim.clinicians.append(
                Clinician(
                    id = i + cur_in_list,
                    appointment_time=config["appointment_length"],
                    shift_start=config["shift_pattern"][0],
                    shift_end=config["shift_pattern"][1]
                )
            )

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
        sim.lambdas_t. append((lam, sim.clock))
        return np.random.exponential(1 / lam)

    def generate_service(sim):
        return sim._service_func()
    
    def get_free_clinician(sim): 
        for c in sim.clinicians: 
            if c.available and sim.clock >= c.shift_start and sim.clock <= c.shift_end:
                return c
        return None #i.e. no one is free!
    
    ####################################################################

    def arrival(sim):
        sim.num_in_system += 1
        sim.queue.append(sim.clock)
        sim.arrival_times.append(sim.clock)

        clinician = sim.get_free_clinician()

        if clinician is not None:
            arrival_time = sim.queue.popleft()

            clinician.appointment_start(sim.clock)

            # service_time = clinician.generate_service()
            service_time = sim.generate_service()
            clinician.next_available = sim.clock + service_time

            wait = sim.clock - arrival_time
            sim.waits.append(wait)

        sim.t_arrival = sim.clock + sim.generate_interarrival()

    def departure(sim, clinician: Clinician): #any mutation to clinician here will modify the original sim.clinician object 
        sim.num_in_system -= 1
        sim.departure_times.append(sim.clock)

        clinician.appointment_end(sim.clock)

        if sim.queue:
            arrival_time = sim.queue.popleft()

            clinician.appointment_start(sim.clock)

            service_time = sim.generate_service()
            # service_time = clinician.generate_service()
            clinician.next_available = sim.clock + service_time

            wait = sim.clock - arrival_time
            sim.waits.append(wait)
        else:
            clinician.next_available = None

        if sim.clock > clinician.shift_end: #enforce end of shift?
            clinician.next_available = None
            clinician.available = False

    def get_next_departure(sim): #helper function
        active = [
            (c.next_available, c)
            for c in sim.clinicians if c.next_available is not None
        ]
        return min(active, default=(float('inf'), None), key=lambda x:x[0])
        #return next availabe and clinician object (find smallest first element in list and replace with a default value of 'inf' if none)


    ####################################################################

    def step(sim): #discrete time event - we just jump to the next time where *something* happens
        # active_departures = [t for t in sim.servers if t is not None] #find NEXT departure
        # next_depart = min(active_departures) if active_departures else float('inf')
        assert len(sim.clinicians) >= 1, "No clinicians created. Call create_clinicians()."
        next_depart_time, clinician = sim.get_next_departure()

        if sim.t_arrival <= next_depart_time and sim.t_arrival <= sim.close_time: #if arrival happens next (before available server) and its before closing
            sim.clock = sim.t_arrival
            sim.arrival() #jump to arrival time and initiate arrival 
        else:
            sim.clock = next_depart_time
            if clinician is not None: 
                sim.departure(clinician)

        # Record system state (queue length OR total system)
        sim.sys_state.append((sim.clock, sim.num_in_system))


# use a random seed to allow reproducibility! 

np.random.seed(64) #my fave number

# simulation_1 = ClinicSim(
#     lambda_base=8,
#     appointment_time=30, #mins
#     peak_multiplier=4
# )


#### CONFIG #####
service_dist : ServiceMethods = "exponential"


simulation_1 = ClinicSim(
    lambda_base=8,
    appointment_time=30, #mins
    service_method = service_dist, 
    peak_multiplier= 3
)

# simulation_1 = ClinicSim(
#     lambda_base=8,
#     appointment_time=30, #mins
#     service_method = "lognormal", 
#     peak_multiplier= 4,
#     logn_sigma = 0.5
# )

# simulation_1 = ClinicSim(
#     lambda_base=8,
#     appointment_time=30, #mins
#     service_method = "normal", 
#     peak_multiplier= 4,
#     norm_scale = 0.5
# )

# simulation_1.create_clinicians(
#     n_clinicians= 6, 
#     config= {
#         "shift_pattern" : (8.0, 17.5),
#         "appointment_length" : 30
#     }
# )

simulation_1.create_clinicians(
    n_clinicians= 4, 
    config= {
        "shift_pattern" : (8.0, 14.0),
        "appointment_length" : 10
    }
)

simulation_1.create_clinicians(
    n_clinicians= 3, 
    config= {
        "shift_pattern" : (11.5, 17.5),
        "appointment_length" : 10
    }
)

# simulation_1.create_clinicians(
#     n_clinicians= 10, 
#     config= {
#         "shift_pattern" : (10.0, 14.0),
#         "appointment_length" : 30
#     }
# )


while simulation_1.clock < simulation_1.close_time: 
    simulation_1.step()


print("Sim finished")



##########################################################################################

# Plotting 


import matplotlib.pyplot as plt
import numpy as np



def plot_arrival_depart(sim: ClinicSim):

    _, ax = plt.subplots(figsize=(12,6))

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

    ax.set_title(f"Patient arrival, departures, and total system capacity for flat rate peak multiplier = {simulation_1.peak_multiplier}.")

    print("Finished plotting")

def plot_lamda_t(sim: ClinicSim): 

    times, lambdas = zip(*sim.lambdas_t)

    _, ax = plt.subplots(figsize=(12,6))

    ax.step(times, lambdas)
    ax.xlabel("Time")
    ax.ylabel("Lambda (arrival rate)")
    ax.title("Arrival Rate Over Time")
    print("completed plot")

def plot_mu_distribution_actual(sim: ClinicSim, n_samples: int = 100): 
    samples = [sim.generate_service() for _ in range(n_samples)]

    _, ax = plt.subplots(figsize=(12,6))

    ax.hist(samples, bins=100, density=True)
    ax.xlabel("Service time")
    ax.ylabel("Density")
    ax.title("Service Time Distribution")
    print("completed plot")


plot_arrival_depart(simulation_1)
plot_lamda_t(simulation_1)
plot_mu_distribution_actual(simulation_1)

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

metrics = compute_sim_result_metrics(sim = simulation_1)
print(metrics)
print("done")

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