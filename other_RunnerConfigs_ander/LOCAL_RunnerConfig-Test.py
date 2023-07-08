import enum
import os
import paramiko
import subprocess

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

processes = {}
server = 'GL2'

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

def remote_command(connection_name, command, measurement_name):
    con = get_paramiko_connection(connection_name)

    output.console_log(f'Starting {measurement_name} meter')
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
    time_between_runs_in_ms:    int             = 1000 * 5 # TODO this is 5s


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
                {factor1: ['example_treatment1']},                   # all runs having treatment "example_treatment1" will be excluded
                {factor1: ['example_treatment2'], factor2: [True]},  # all runs having the combination ("example_treatment2", True) will be excluded
            ],
            data_columns=['avg_cpu', 'avg_mem']
        )
        return self.run_table_model

    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here
        Invoked only once during the lifetime of the program."""

        output.console_log("Config.before_experiment() called!")

    def before_run(self) -> None:
        """Perform any activity required before starting a run.
        No context is available here as the run is not yet active (BEFORE RUN)"""

        output.console_log("Config.before_run() called!")

    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here.
        For example, starting the target system to measure.
        Activities after starting the run should also be performed here."""
        
        output.console_log("Config.start_run() called!")
        #host, username, password = get_credentials(server)

        # connect to server
        # con = paramiko.SSHClient()
        # con.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # con.connect(host, username=username, password=password)
                

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        output.console_log("Config.start_measurement() called!")
        workload = context.run_variation['workload']
        process = execute_command(f"cd ~/master-project-def/scripts/experiment-runner && nohup ./monitor-er.sh {server} {workload}", False)
        processes["monitor"] = process
        output.console_log("Command executed with return code:", process.returncode)

        #process = execute_command(f"cd ~/master-project-def/scripts/experiment-runner && ./stress-er.sh {workload} {stress_time}")
        #output.console_log("Command executed with return code:", process.returncode)



    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here, or block here until the target finishes."""

        output.console_log("Config.interact() called!")

        stress_time = 10
        workload = context.run_variation['workload']
        process = execute_command(f"cd ~/master-project-def/scripts/experiment-runner && ./stress-er.sh {workload} {stress_time}", True)
        processes["stress"] = process
        output.console_log("Command executed with return code:", process.returncode)


    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        output.console_log("Config.stop_measurement called!")
        
        process = processes["monitor"]
        process.terminate()
        

    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run.
        Activities after stopping the run should also be performed here."""
        
        for process in processes.items():
            process.terminate()
        output.console_log("Config.stop_run() called!")

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, SupportsStr]]:
        """Parse and process any measurement data here.
        You can also store the raw measurement data under `context.run_dir`
        Returns a dictionary with keys `self.run_table_model.data_columns` and their values populated"""

        output.console_log("Config.populate_run_data() called!")
        return None

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""

        output.console_log("Config.after_experiment() called!")

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
