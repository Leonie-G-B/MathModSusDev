
# Just having a play around with the practice codes and understanding the logic 


# we know lambda can VARY between 8 and 16 - how do we want to approach this information? 
# eiither way, lambda needs to be a value that can easily be varied (and iterated upon?)

# to iterate, should the entire process be repeatable and results independent of number of trials? 


### Nomenclature: inputs ###

# Standard inputs
import numpy as np
import pandas as pd
from typing import Literal, TypedDict, Sequence
from enum import StrEnum

# Simulation specifics
from collections import deque

# Plots
import seaborn as sbn


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
    
    def calc_workload(self):
        shift_length = self.shift_end - self.shift_start
        workload = (shift_length - self.total_downtime) / shift_length
        self.workload = workload

class ClinicSim: 
    def __init__(sim, lambda_base: int, appointment_time: int, 
                 service_method: ServiceMethods = "exponential",
                 peak_multiplier: int = None, #should be 2,4,8 - use checking?
                 open_close: tuple[float, float] = (8.0, 17.5),
                 peak_hrs: tuple[float, float] = (10.0, 14.0), 
                 peak_normal_shape: bool = False, #if True, then creates a normal curve within the peak with max value peak_multiplier. Otherwise uses other default methods.
                 **kwargs):
        
        sim.lambda_base = lambda_base
        sim.lambdas_t = []
        
        sim.peak_multiplier: int = peak_multiplier
        sim.normal_peak: bool = peak_normal_shape
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
        mean_serv_hrs = 1 /sim.mu
        if method == "exponential": 
            sim._service_func = lambda: np.random.exponential(mean_serv_hrs)
        elif method == "lognormal": 
            sigma = kwargs.get("logn_sigma", 0.5)
            mu_log = np.log(mean_serv_hrs) - 0.5 * sigma**2
            sim._service_func = lambda: np.random.lognormal(mean= mu_log, sigma = sigma)
        elif method == "normal": 
            sim._service_func = lambda: max(0, np.random.normal(
                loc = mean_serv_hrs,
                scale= kwargs.get("norm_scale", 0.2) * mean_serv_hrs
                ))

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
        if sim.peak_start <= sim.clock <= sim.peak_end: #if during peak time
            if sim.peak_multiplier is not None: 
                multiplier = sim.peak_multiplier
                if sim.normal_peak: 
                    t = sim.clock 
                    centre = (sim.peak_start + sim.peak_end) /2
                    half_width = (sim.peak_end - sim.peak_start)/ 2
                    x = (t - centre) / half_width
                    k = 3 #steepness - should this be an input? 

                    shape = np.exp(-k * x ** 2)
                    edge = np.exp(-k) #normalise
                    shape = (shape - edge) / (1- edge)
                    multiplier = 1 + (sim.peak_multiplier - 1) * shape
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

# np.random.seed(64) #my fave number

# simulation_1 = ClinicSim(
#     lambda_base=8,
#     appointment_time=30, #mins
#     peak_multiplier=4
# )


#### CONFIG #####
sim_kwargs : ClinicSim = {
    "lambda_base" : 8,
    "appointment_time" : 30,
    "service_method" : "lognormal",
    "peak_multiplier" : 4,
    "peak_normal_shape" : True
}


simulation_1 = ClinicSim(**sim_kwargs)

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

simulation_1.create_clinicians(
    n_clinicians= 6, 
    config= {
        "shift_pattern" : (8.0, 17.5),
        "appointment_length" : 30
    }
)

# simulation_1.create_clinicians(
#     n_clinicians= 4, 
#     config= {
#         "shift_pattern" : (8.0, 14.0),
#         "appointment_length" : 10
#     }
# )

# simulation_1.create_clinicians(
#     n_clinicians= 3, 
#     config= {
#         "shift_pattern" : (11.5, 17.5),
#         "appointment_length" : 10
#     }
# )

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

    lambdas, times = zip(*sim.lambdas_t)
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.step(times, lambdas, where='post', linewidth=2, label="λ(t) arrival rate")

    mean_lambda = np.mean(lambdas)
    ax.axhline(mean_lambda, color='red', linestyle='--', linewidth=1.5,
               label=f"Mean λ = {mean_lambda:.2f}")

    if hasattr(sim, "peak_start") and hasattr(sim, "peak_end"): #if provided, plot the peak hrs
        ax.axvspan(sim.peak_start, sim.peak_end, color='yellow', alpha=0.2,
                   label="Peak hours")

    ax.set_xlabel("Time of Day")
    ax.set_ylabel("Arrival Rate λ(t)")
    ax.set_title("Arrival Rate Over Time")

    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc="upper left")
    fig.tight_layout()

    print("completed plot")


def plot_service_distribution_actual(sim: ClinicSim, n_samples: int = 500):

    samples = [sim.generate_service() * 60 for _ in range(n_samples)]

    fig, ax = plt.subplots(figsize=(12, 6))

    #gonna convert things from mu to times (in minutes)
    ax.hist(samples, bins=40, density=True, alpha=0.6, color="steelblue",
            edgecolor="black", label="Sampled service times")

    try: 
        sbn.kdeplot(samples, ax=ax, color="darkred", linewidth=2,
                    label="KDE (smooth density)")
    except Exception: 
        print("failed to plot seaborn kde bounds")

    ax.set_xlabel("Service time")
    ax.set_ylabel("Density")
    ax.set_title(f"Service Time Distribution. N_samples = {n_samples}")

    mean_val = np.mean(samples)
    ax.axvline(mean_val, color="green", linestyle="--", linewidth=2,
               label=f"Mean = {mean_val:.2f}")

    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xlim(left = 0)
    ax.legend()

    fig.tight_layout()
    print("completed plot")



# plot_arrival_depart(simulation_1)
# plot_lamda_t(simulation_1)
# plot_service_distribution_actual(simulation_1, n_samples=500)

########################################################################################

#### Want to now run n sims with the same inputs, but getting a better view of things bc of averagine from the random nature of the model 

class SimMetrics(StrEnum): 
    MEAN_WAIT = "mean_wait"
    P95_WAIT = "p95_wait"
    STD_WAIT = "std_wait"
    UTILISATION = "utilisation"
    THROUGHPUT = "throughput"

# compute metrics method for one sim result
def compute_sim_result_metrics(sim: ClinicSim) -> dict[str, float]:
    waits = np.array(sim.waits)

    peaks = [n for (_, n) in sim.sys_state]

    eod_patients = sim.num_in_system # this is EOD value by defualt if sim is complete

    patients_served = len(sim.departure_times) #every departure is a patient served

    #return a dict of each clinician and their %workload
    for clinician in sim.clinicians:
        clinician.calc_workload()
    workloads = np.array([clinician.workload for clinician in sim.clinicians])

    return {
        "avg_wait" : waits.mean(),
        "peak" : max(peaks),
        "eod_patients" : eod_patients,
        "patients_served" : patients_served,
        "avg_clinician_workload" : workloads.mean()
    }

metrics = compute_sim_result_metrics(sim = simulation_1)
print(metrics)
print("done")

# run a load of sims

#first we make a class that mimics ClinicSim but is more suitable for our averaged data
#should still be able to use the regular plotting methods on it tho
class AveragedSim: 
    def __init__(self, sims: list):
        self.sims= sims

        ref = sims[0]
        self.open_time = ref.open_time
        self.close_time = ref.close_time
        self.peak_start = ref.peak_start
        self.peak_end = ref.peak_end

        self.waits = np.concatenate([s.waits for s in sims])
        self.arrival_times = np.concatenate([s.arrival_times for s in sims])
        self.departure_times = np.concatenate([s.departure_times for s in sims])

        self.sys_state = self._average_series("sys_state")
        self.lambdas_t = self._average_series("lambdas_t")

    def _average_series(self, attr, dt=0.01):
        #interpolate because the time series are all different (time stamps only occuur at an event, which differs between sim)
        time_grid = np.arange(self.open_time, self.close_time, dt)
        all_interp = []

        for sim in self.sims:
            series = getattr(sim, attr, None)
            if not series:
                continue

            times, values = zip(*series)
            interp = np.interp(time_grid, times, values)
            all_interp.append(interp)

        if not all_interp:
            return []

        mean_values = np.mean(all_interp, axis=0)
        return list(zip(time_grid, mean_values))

def run_multisim_avg(n_sims: int, metric_sweep: tuple = None, additional_clinicians: bool = False, additional_shift_pattern: tuple[float, float] =(10.0, 14.0), **kwargs): 
    """
    Run n simulations and compute and return the average metrics. 
    Allows for a sweep - if sweep metric given then it runs n_sims at for each value in the sweep.

    Inputs: 
        n_sims(int) = Number of sims to run. 
        metric_sweep: tuple = ("parameter name", [values])
        **kwargs = simulation input args (for all sims). 

    Output: 
        result_dict contains:
        {
            "aggregate_sim": AveragedSim,
            "metrics": {metric: {mean, std, p95}},
            "raw_metrics": [...]
        }
    """

    def run_single_config(config_kwargs):
        sims = []
        metrics_list = []

        for i in range(n_sims):
            np.random.seed(i)

            sim = ClinicSim(**config_kwargs)
            sim.create_clinicians( #THIS IS MANUAL AND BAD!!!
                n_clinicians= 6, 
                config= {
                    "shift_pattern" : (8.0, 18.0),
                    "appointment_length" : 30
                }
            )
            if additional_clinicians: 
                sim.create_clinicians( #THIS IS MANUAL AND BAD!!!
                    n_clinicians= 2, 
                    config= {
                        "shift_pattern" : additional_shift_pattern,
                        "appointment_length" : 30
                    }
                )

            while sim.clock < sim.close_time:
                sim.step()

            sims.append(sim)
            metrics_list.append(compute_sim_result_metrics(sim))

        agg_sim = AveragedSim(sims)

        agg_metrics = {}
        keys = metrics_list[0].keys()

        for k in keys:
            vals = [m[k] for m in metrics_list]
            agg_metrics[k] = {
                "mean": np.mean(vals),
                "std": np.std(vals),
                "p95": np.percentile(vals, 95)
            }

        return {
            "aggregate_sim": agg_sim,
            "metrics": agg_metrics,
            "raw_metrics": metrics_list
        }
    
    if metric_sweep is None: 
        return run_single_config(kwargs)
    else: 
        param, values = metric_sweep
        results = {}
        for val in values:
            config_kwargs = kwargs.copy()
            config_kwargs[param] = val

            results[val] = run_single_config(config_kwargs)

        return results  


# run n sims with varying base lambda

# sim_kwargs = {
#     "lambda_base" : 8,
#     "appointment_time" : 30,
#     "service_method" : "lognormal",
#     "peak_multiplier" : 3
# }

# results = run_multisim_avg(
#     n_sims=20,
#     **sim_kwargs
# )


def print_sweep_results_quick(results, sweep_metric: tuple[str, list], sim_inputs: dict,metric: str = "avg_wait", calc: str = "mean"):

    print(f"\nSweep results: {metric} for swept vals of {sweep_metric[0]}")
    print(f"Constant sim metrics: \n{sim_inputs}")

    x = []
    y = []
    for item in results: 
        y_val = results[item]["metrics"][metric][calc]
        print(f"{str(item)} = {y_val}")
        x.append(item)
        y.append(y_val)
    return x,y



def sweep_metrics_4_peaks(sweep_metric , appointment_time: float= 30 , run_n_sims:int  = 30, imp_1: bool = False):
    
    sim_kwargs_1 = {
        # "lambda_base" : 8,
        "appointment_time" : appointment_time,
        "service_method" : "lognormal",
        "peak_multiplier" : 1
    }

    results_1 = run_multisim_avg(
        n_sims=run_n_sims,
        metric_sweep= sweep_metric,
        additional_clinicians=imp_1,
        **sim_kwargs_1
    )


    x1, y1 = print_sweep_results_quick(results_1, sweep_metric = sweep_metric, sim_inputs=sim_kwargs_1)


    ########## Do all above again, but have the normal peak relationship - do once each for double, triple, and quadruple

    sim_kwargs_2 = {
        # "lambda_base" : 8,
        "appointment_time" : appointment_time,
        "service_method" : "lognormal",
        "peak_multiplier" : 2,
        "peak_normal_shape" : True
    }

    results_2 = run_multisim_avg(
        n_sims=run_n_sims,
        metric_sweep= sweep_metric,
        additional_clinicians=imp_1,
        **sim_kwargs_2
    )

    ##

    sim_kwargs_3 = {
        # "lambda_base" : 8,
        "appointment_time" : appointment_time,
        "service_method" : "lognormal",
        "peak_multiplier" : 3,
        "peak_normal_shape" : True
    }

    results_3 = run_multisim_avg(
        n_sims=run_n_sims,
        metric_sweep= sweep_metric,
        additional_clinicians=imp_1,
        **sim_kwargs_3
    )

    ##

    sim_kwargs_4 = {
        # "lambda_base" : 8,
        "appointment_time" : appointment_time,
        "service_method" : "lognormal",
        "peak_multiplier" : 4,
        "peak_normal_shape" : True
    }

    results_4 = run_multisim_avg(
        n_sims=run_n_sims,
        metric_sweep= sweep_metric,
        additional_clinicians=imp_1,
        **sim_kwargs_4
    )


    x2, y2 = print_sweep_results_quick(results_2, sweep_metric = sweep_metric, sim_inputs=sim_kwargs_2)
    x3, y3 = print_sweep_results_quick(results_3, sweep_metric = sweep_metric, sim_inputs=sim_kwargs_3)
    x4, y4 = print_sweep_results_quick(results_4, sweep_metric = sweep_metric, sim_inputs=sim_kwargs_4)

    return results_1, results_2, results_3, results_4


def build_df_for_plot(
    results_dicts: Sequence[dict[float, dict]],
    labels: Sequence[str],
    sweep_metric: tuple[str, Sequence[float]],
    metric: str = "avg_wait",
    calc: str = "mean"
) -> pd.DataFrame:
    
    param_name, values = sweep_metric
    rows: list[dict[str, float | str]] = []
    for res, label in zip(results_dicts, labels):
        for val in sorted(values):
            rows.append({
                param_name: val,
                "value": res[val]["metrics"][metric][calc],
                "std": res[val]["metrics"][metric]["std"],
                "label": label
            })

    return pd.DataFrame(rows)


sweep_metric = (
    "lambda_base", np.linspace(8,16,5))


def format_time_hours(val: float) -> str:
    "Convert decimal hr numbers into something human readable and clear."
    if val >= 1.0:
        hours = int(val)
        minutes = int(round((val - hours) * 60))
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    else:
        minutes = int(round(val * 60))
        return f"{minutes}mins"


def sweep_plot(df: pd.DataFrame, 
               plot_shaded_regions: bool = True,
               y_axis_in_time: bool = True, y_axis_in_perc: bool = False):
    plt.figure(figsize=(10,6))

    # sbn.set_palette("colorblind")
    plt.rcParams.update({'font.size': 14})

    labels = df["label"].unique()
    palette = sbn.color_palette("colorblind", n_colors=len(labels))
    colour_dict = dict(zip(labels, palette))

    ax = sbn.lineplot(
        data=df,
        x="lambda_base",
        y="value",
        hue="label",
        marker="o",
        palette=colour_dict
    )
    
    annotated_values = set()# tracking to avoid duplicate labels

    # lines = plt.gca().get_lines()
    for label, subdf in df.groupby("label"):
        colour = colour_dict[label]
        if plot_shaded_regions:
            plt.fill_between(
                subdf["lambda_base"],
                subdf["value"] - subdf["std"],
                subdf["value"] + subdf["std"],
                color = colour, #american spelling :(
                alpha=0.2
            )
        left_row = subdf.iloc[0] #lowest vals
        y_val_left = left_row["value"]
        if y_axis_in_time and not y_axis_in_perc:
            annotext = format_time_hours(y_val_left)
        elif y_axis_in_perc: 
            annotext = f"{round(y_val_left *100)}%" 
        else: 
            annotext = y_val_left
        
        if annotext not in annotated_values:
            plt.text(
                left_row["lambda_base"] - 0.2,#shift slightly left
                left_row["value"],
                annotext,
                fontsize=14,
                ha="right",
                va="center"
            )
            annotated_values.add(annotext)

        max_idx = subdf["value"].idxmax()
        max_row = subdf.loc[max_idx] #highest value, dont assume its the last tho 
        y_val_max = max_row["value"]
        if y_axis_in_time and not y_axis_in_perc:
            annotext = format_time_hours(y_val_max)
        elif y_axis_in_perc:
            annotext = f"{round(y_val_max*100)}%"
        else:
            annotext = y_val_max

        if annotext not in annotated_values:
            plt.text(
                max_row["lambda_base"] + 0.2,
                y_val_max,
                annotext,
                fontsize=14,
                ha="left",
                va="center"
            )
            annotated_values.add(annotext)

    x_min, x_max = df["lambda_base"].min(), df["lambda_base"].max()
    plt.xlim(x_min - 1.5, x_max + 1.5) 
    
    ax.grid(True, which="major", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.legend(title="Peak hour behaviour scenario", loc = 'lower right')

    return ax, plt


# results_1, results_2, results_3, results_4 = sweep_metrics_4_peaks(sweep_metric=sweep_metric, run_n_sims=100)

# lamda_sweep_df = build_df_for_plot(
#     [results_1, results_2, results_3, results_4],
#     ["No peak modifier", "Normal peak up to 2x", "Normal peak up to 3x", "Normal peak up to 4x"],
#     sweep_metric
# )

# ax, plot = sweep_plot(df = lamda_sweep_df)
# plot.xlabel("Base arrival rate, λ")
# plot.ylabel("Average wait (hrs)")
# plot.title("Average Wait Time vs Base λ for varying peak hour effects.")

# ### Now plot the same sweep plot but for clinician workload

# workload_sweep_metrics_4_peaks_df = build_df_for_plot(
#     results_dicts = [results_1, results_2, results_3, results_4],
#     labels = ["No peak modifier", "Normal peak up to 2x", "Normal peak up to 3x", "Normal peak up to 4x"],
#     sweep_metric= sweep_metric,
#     metric = "avg_clinician_workload")

# ax, plot = sweep_plot(df = workload_sweep_metrics_4_peaks_df , plot_shaded_regions=False,y_axis_in_perc = True)
# vals = plt.gca().get_yticks()
# plot.gca().set_yticklabels([f"{v*100:.0f}%" for v in vals])
# plot.axhline(1.0, color = "black", linestyle="--", linewidth= 1.5)
# plot.xlabel("Base arrival rate, λ")
# plot.ylabel("Average Clinician Workload")
# plot.title("Average Clinician Workload vs Base λ for varying peak hour effects.")


################### Now to begin trying to improve the conditions ##################

# Improvement 1: Hire 2 additional 'peak clinicians'

# plots: avg wait time

results_1, results_2, results_3, results_4 = sweep_metrics_4_peaks(sweep_metric=sweep_metric, run_n_sims=100,imp_1=True)
lamda_sweep_df = build_df_for_plot(
    [results_1, results_2, results_3, results_4],
    ["No peak modifier", "Normal peak up to 2x", "Normal peak up to 3x", "Normal peak up to 4x"],
    sweep_metric
)
ax, plot = sweep_plot(df = lamda_sweep_df)
plot.xlabel("Base arrival rate, λ")
plot.ylabel("Average wait (hrs)")
plot.title("Average Wait Time vs Base λ for varying peak hour effects. ADDITIONAL CLINICIANS.")

workload_sweep_metrics_4_peaks_df = build_df_for_plot(
    results_dicts = [results_1, results_2, results_3, results_4],
    labels = ["No peak modifier", "Normal peak up to 2x", "Normal peak up to 3x", "Normal peak up to 4x"],
    sweep_metric= sweep_metric,
    metric = "avg_clinician_workload")

ax, plot = sweep_plot(df = workload_sweep_metrics_4_peaks_df , plot_shaded_regions=False,y_axis_in_perc = True)
vals = plt.gca().get_yticks()
plot.gca().set_yticklabels([f"{v*100:.0f}%" for v in vals])
plot.axhline(1.0, color = "black", linestyle="--", linewidth= 1.5)
plot.xlabel("Base arrival rate, λ")
plot.ylabel("Average Clinician Workload")
plot.title("Average Clinician Workload vs Base λ for varying peak hour effects.")


# Improvement 2: Aim to reduce appointment times by n minutes 


results_1_20, results_2_20, results_3_20, results_4_20 = sweep_metrics_4_peaks(sweep_metric=sweep_metric, appointment_time=20, run_n_sims=20,imp_1=True)
results_1_25, results_2_25, results_3_25, results_4_25 = sweep_metrics_4_peaks(sweep_metric=sweep_metric, appointment_time=25, run_n_sims=20,imp_1=True)
results_1_30, results_2_30, results_3_30, results_4_30 = sweep_metrics_4_peaks(sweep_metric=sweep_metric, appointment_time=30, run_n_sims=20,imp_1=True)
results_1_35, results_2_35, results_3_35, results_4_35 = sweep_metrics_4_peaks(sweep_metric=sweep_metric, appointment_time=35, run_n_sims=20,imp_1=True)

results_dict_1 = {
    20: results_1_20,
    25: results_1_25,
    30: results_1_30,
    35: results_1_35
}

results_dict_2 = {
    20: results_2_20,
    25: results_2_25,
    30: results_2_30,
    35: results_2_35
}

results_dict_3 = {
    20: results_3_20,
    25: results_3_25,
    30: results_3_30,
    35: results_3_35
}

results_dict_4 = {
    20: results_4_20,
    25: results_4_25,
    30: results_4_30,
    35: results_4_35
}

# Sensitivity plot: affect of changing the appointment time aim by -10, -5, 0, +5 mins, for varying base lambda 

# seaborn plot lambda against average appointment time, colourplot: average wait time (in human readable 1h30 format, for example)


def plot_heatmap_from_results(
    results_by_appt: dict[int, dict],
    sweep_metric: tuple[str, list],
    metric_limits : tuple[float, float] | None =  None, 
    metric: str = "avg_wait",
    calc: str = "mean",
    title: str = ""
):
    """
    results_by_appt: {appointment_time (int): results_dict}

    results_dict: {lambda_value: {...metrics...}}
    """

    param_name, lambda_vals = sweep_metric

    data = []
    annot_data = []#formatted version
    appt_times = sorted(results_by_appt.keys())

    for appt in appt_times:
        row = []
        annot_row = []
        res = results_by_appt[appt]

        for lam in sorted(lambda_vals):
            val = res[lam]["metrics"][metric][calc]
            row.append(val)
            annot_row.append(format_time_hours(val))
        data.append(row)
        annot_data.append(annot_row)

    df = pd.DataFrame(
        data,
        index=appt_times,
        columns=sorted(lambda_vals)
    )

    annot_df = pd.DataFrame(
        annot_data,
        index=appt_times,
        columns=sorted(lambda_vals)
    )

    plt.figure(figsize=(10,6))

    if metric_limits:
        ax = sbn.heatmap(
            df,
            cmap="viridis",   
            # annot=True,#show numbers
            annot = annot_df, # formatted labels instead
            fmt="",
            vmin = metric_limits[0],
            vmax = metric_limits[1],
            cbar_kws={"label": f"{metric} ({calc})"}
        )
    else: 
        ax = sbn.heatmap(
            df,
            cmap="viridis",   
            # annot=True,#show numbers
            annot = annot_df, # formatted labels instead
            fmt="",
            cbar_kws={"label": f"{metric} ({calc})"}
        )

    cbar = ax.collections[0].colorbar
    ticks = cbar.get_ticks()
    cbar.set_ticks(ticks)
    cbar.set_ticklabels([format_time_hours(t) for t in ticks])

    plt.xlabel("Base λ")
    plt.ylabel("Appointment time (mins)")
    plt.title(title or f"{metric} heatmap")

    plt.tight_layout()
    plt.show()

    print("Plotted heatmap")

plot_heatmap_from_results(
    results_dict_1,
    sweep_metric,
    metric_limits= (0.0, 2.0),
    title="No peak modifier"
)

plot_heatmap_from_results(
    results_dict_2,
    sweep_metric,
    metric_limits= (0.0, 2.0),
    title="2x Peak modifier"
)

plot_heatmap_from_results(
    results_dict_3,
    sweep_metric,
    metric_limits= (0.0, 2.0),
    title="3x Peak modifier"
)

plot_heatmap_from_results(
    results_dict_4,
    sweep_metric,
    metric_limits= (0.0, 2.0),
    title="4x Peak modifier"
)


# Calculate the overal worst case (4x peak multiplier, 16 base lambda) improvement to baseline

baseline_params = {
    "lambda_base" : 16,
    "appointment_time" : 30,
    "service_method" : "lognormal",
    "peak_multiplier" : 4
}

improved_params = {
    "lambda_base" :16,
    "appointment_time" : 25,
    "service_method" : "lognormal",
    "peak_multiplier" : 4
}

baseline_worstcase = run_multisim_avg(n_sims = 100, **baseline_params)
improved_worstcase = run_multisim_avg(n_sims=100, additional_clinicians=True, **improved_params)

baseline_avg_wait = baseline_worstcase['metrics']['avg_wait']['mean']
improved_avg_wait = improved_worstcase['metrics']['avg_wait']['mean']

avg_wait_improvement = (baseline_avg_wait- improved_avg_wait) / baseline_avg_wait

print(f"Improved method resulted in a {np.round(avg_wait_improvement*100, decimals = 1)}% reduction in average wait times.")

# See clinician workload 

### Heatmap: plot clinician schedule against 

baseline_params_25 = {
    "lambda_base" : 16,
    "appointment_time" : 25,
    "service_method" : "lognormal",
    "peak_multiplier" : 4
}

baseline_params_30 = {
    "lambda_base" : 16,
    "appointment_time" : 25,
    "service_method" : "lognormal",
    "peak_multiplier" : 4
}

baseline_params_35 = {
    "lambda_base" : 16,
    "appointment_time" : 25,
    "service_method" : "lognormal",
    "peak_multiplier" : 4
}

# Now run each above for 3 scenarios: 10-14, 10-15, 10-16

short_shift_case1 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,14.0),**improved_params)
short_shift_case2 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,15.0),**improved_params)
short_shift_case3 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,16.0),**improved_params)

regular_shift_case1 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,14.0),**improved_params)
regular_shift_case2 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,15.0),**improved_params)
regular_shift_case3 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,16.0),**improved_params)

longer_shift_case1 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,14.0),**improved_params)
longer_shift_case2 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,15.0),**improved_params)
longer_shift_case3 = run_multisim_avg(n_sims=100, additional_clinicians=True, additional_shift_pattern=(10.0,16.0),**improved_params)


print("All done")