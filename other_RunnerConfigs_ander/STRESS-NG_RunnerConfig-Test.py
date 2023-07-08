import enum
import os
import paramiko
import subprocess
import time

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.Output.OutputProcedure import OutputProcedure as output

from typing import Dict, List, Any, Optional
from pathlib import Path
from os.path import dirname, realpath


# Some of this code has been adjusted from a previous version developed by Madalina Dinga
class Workload(enum.Enum):
    W_LOW = 25
    W_MEDIUM = 50
    W_HIGH = 100

def extract_level(level):
    # We remove the prefix and make it lowecase F_LOW -> low
    return level.lower()[2:]

def get_credentials(host_name):
    # declare credentials
    host = os.getenv(f"{host_name}_H")
    username = os.getenv(f"{host_name}_U")
    password = os.getenv(f"{host_name}_P")

    if not password or not username or not host:
        raise Exception('No environment variables set for credentials')

    return host, username, password

def get_paramiko_connection(connection_name):
    host, username, password = get_credentials(connection_name)
    # connect to server
    con = paramiko.SSHClient()
    con.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    con.connect(host, username=username, password=password)
    output.console_log(f"Connection successful to {connection_name}")

    return con

def remote_command(connection_name, command, measurement_name, background=False):
    con = get_paramiko_connection(connection_name)

    output.console_log(f'Starting {measurement_name} meter')
    if background:
        stdin, stdout, stderr = con.exec_command(command, get_pty=True)
        err = stderr.read()
        if err != b'':
            output.console_log(err)
        output.console_log(f'{measurement_name} successfully executed in the background')

    else:
        stdin, stdout, stderr = con.exec_command(command)
        err = stderr.read()
        if err != b'':
            output.console_log(err)
        output.console_log(f'{measurement_name} successfully executed')


# Open a terminal and execute a command in the local machine
def execute_command(command, wait):
    process = subprocess.Popen(command, shell=True, executable='/bin/bash')
    if wait: 
        process.communicate()
    return process

def get_results_path():
    return Path()

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))

    # ================================ USER SPECIFIC CONFIG ================================
    """The name of the experiment."""
    name:                       str             = "tts-stressing"

    """The path in which Experiment Runner will create a folder with the name `self.name`, in order to store the
    results from this experiment. (Path does not need to exist - it will be created if necessary.)
    Output path defaults to the config file's path, inside the folder 'experiments'"""
    results_output_path:        Path            = ROOT_DIR / 'experiments'

    """Experiment operation type. Unless you manually want to initiate each run, use `OperationType.AUTO`."""
    operation_type:             OperationType   = OperationType.AUTO

    """The time Experiment Runner will wait after a run completes.
    This can be essential to accommodate for cooldown periods on some systems."""
    time_between_runs_in_ms:    int             = 1000 * 2 # TODO in ms


    # Dynamic configurations can be one-time satisfied here before the program takes the config as-is
    # e.g. Setting some variable based on some criteria
    def __init__(self):
        """Executes immediately after program start, on config load"""

        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN       , self.before_run       ),
            (RunnerEvents.START_RUN        , self.start_run        ),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT         , self.interact         ),
            (RunnerEvents.STOP_MEASUREMENT , self.stop_measurement ),
            (RunnerEvents.STOP_RUN         , self.stop_run         ),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT , self.after_experiment )
        ])
        self.run_table_model = None  # Initialized later

        output.console_log("Custom config loaded")

    def create_run_table_model(self) -> RunTableModel:
        """Create and return the run_table model here. A run_table is a List (rows) of tuples (columns),
        representing each run performed"""
        factor1 = FactorModel("runs", ['r1', 'r2', 'r3'])
        factor2 = FactorModel("workload", ['0', '25', '50', '75', '100'])
        self.run_table_model = RunTableModel(
            factors=[factor1, factor2],
            exclude_variations=[
                # {factor1: ['example_treatment1']},                   # all runs having treatment "example_treatment1" will be excluded
                # {factor1: ['example_treatment2'], factor2: [True]},  # all runs having the combination ("example_treatment2", True) will be excluded
            ],
            data_columns=['avg_cpu', 'avg_mem']
        )
        return self.run_table_model

    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here
        Invoked only once during the lifetime of the program."""
        output.console_log("Config.before_experiment() called!")
        ################################################## BEFORE_EXPERIMENT

    def before_run(self) -> None:
        """Perform any activity required before starting a run.
        No context is available here as the run is not yet active (BEFORE RUN)"""
        output.console_log("Config.before_run() called!")
        ################################################## BEFORE_RUN

    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here.
        For example, starting the target system to measure.
        Activities after starting the run should also be performed here."""
        output.console_log("Config.start_run() called!")
        ################################################## START_RUN
     
        host, username, password = get_credentials('GL2')

        # connect to server
        con = paramiko.SSHClient()
        con.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        con.connect(host, username=username, password=password)
                

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        output.console_log("Config.start_measurement() called!")
        ################################################## START_MEASUREMENT
        # workload = context.run_variation['workload']
        # process = execute_command(f"cd ~/master-project-def/scripts/experiment-runner && nohup ./monitor-er.sh {server} {workload}", False)
        # processes["monitor"] = process
        # output.console_log("Command executed with return code:", process.returncode)

        # start Wattsup profiler on GL5
        logging_server = "GL5"
        sut_server = "GL2"
        timeout = 10
        _, _, passwordGL5 = get_credentials(logging_server)
        watssup_command = f"echo {passwordGL5} | sudo -S ~/scripts/start_wattsuppro.sh {sut_server} {timeout}"
        remote_command(logging_server, watssup_command, "Wattsup meter start", background=True)

    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here, or block here until the target finishes."""
        output.console_log("Config.interact() called!")
        ################################################## INTERACT
        stress_time = 10
        sut_server = "GL2"
        workload = context.run_variation['workload']
        #stress_command = f"cd ~/scripts && ./stress-er.sh {workload} {stress_time}"
        experiment_command = f"cd ~/scripts/experiment-runner && ./experiment-er.sh {workload} {stress_time} {sut_server}"
        remote_command("GL2", experiment_command, "experiment started")

    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        output.console_log("Config.stop_measurement called!")
        ################################################## STOP_MEASUREMENT
        logging_server = "GL5"
        sut_server = "GL2"

        _, _, passwordGL5 = get_credentials(logging_server)
        stop_wa_command = f"echo {passwordGL5} | sudo -S ~/scripts/stop_wattsuppro.sh {sut_server}"
        remote_command("GL5", stop_wa_command, "wattsuppro stopped")

    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run.
        Activities after stopping the run should also be performed here."""
        output.console_log("Config.stop_run() called!")
        ################################################## STOP_RUN
        

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, SupportsStr]]:
        """Parse and process any measurement data here.
        You can also store the raw measurement data under `context.run_dir`
        Returns a dictionary with keys `self.run_table_model.data_columns` and their values populated"""
        output.console_log("Config.populate_run_data() called!")
        ################################################## POPULATE_RUN
        return None

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""
        output.console_log("Config.after_experiment() called!")
        ################################################## AFTER_EXPERIMENT
        # retrieve output from GL5
        execute_command("cd ~/experiment-runner/ander/testing-stress && mkdir -p results/energy", True)
        _, _, passwordGL5 = get_credentials("GL5")
        retrieve_data_energy_command = f'sshpass -p "{passwordGL5}" scp -r ander@145.108.225.16:/home/ander/results/* /home/eguiwow/experiment-runner/ander/testing-stress/results/energy/' #TODO get path via method
        execute_command(retrieve_data_energy_command, False)
        output.console_log(f'Energy data successfully retrieved')

        # retrieve output from SUT
        sut = "GL2"
        execute_command("cd ~/experiment-runner/ander/testing-stress && mkdir -p results/cpu_mem", True)
        hostSUT, _, passwordSUT = get_credentials(sut)
        retrieve_data_cpu_command = f'sshpass -p "{passwordSUT}" scp -r ander@{hostSUT}:/home/ander/results/* /home/eguiwow/experiment-runner/ander/testing-stress/results/cpu_mem/' #TODO get path via method
        execute_command(retrieve_data_cpu_command, False)
        output.console_log(f'CPU & mem data successfully retrieved')


        # TESTING MODE
        testing = True
        if testing:
            remove_output_folders = f'rm -r /home/eguiwow/experiment-runner/ander/testing-stress/experiments & rm -r /home/eguiwow/experiment-runner/ander/testing-stress/__pycache__' #TODO get path via method
            execute_command(remove_output_folders , False)
            
        

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
