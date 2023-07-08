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

    output.console_log(f'Starting {measurement_name}')
    # Run command in the background
    if background:
        stdin, stdout, stderr = con.exec_command(command, get_pty=True)
        err = stderr.read()
        if err != b'':
            output.console_log(err)
        output.console_log(f'{measurement_name} successfully executed in the background')
    # Run command
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
    name:                       str             = "LOCAL_tts-stressing"

    """The path in which Experiment Runner will create a folder with the name `self.name`, in order to store the
    results from this experiment. (Path does not need to exist - it will be created if necessary.)
    Output path defaults to the config file's path, inside the folder 'experiments'"""
    results_output_path:        Path            = ROOT_DIR / 'experiments'

    """Experiment operation type. Unless you manually want to initiate each run, use `OperationType.AUTO`."""
    operation_type:             OperationType   = OperationType.AUTO

    """The time Experiment Runner will wait after a run completes.
    This can be essential to accommodate for cooldown periods on some systems."""
    time_between_runs_in_ms:    int             = 1000 * 60 * 5

    # System Under Test (SUT)
    SUT:                        str             = "eguiwow"
    # Logging server
    LOGGING_GL:                 str             = "GLX"
    # Testing mode
    testing:                    bool            = True

    if testing:
        time_between_runs_in_ms = 2000

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
     
        output.console_log("Connection successful")
        pass_eguiwow = os.getenv(f"PASS_EGUIWOW")
        workload = context.run_variation['workload']
        output.console_log(f"Running TTS with {workload} workload")

        execute_command(f"cd ~/THESIS/tts-thesis-master; echo {pass_eguiwow} | sudo -S docker-compose up -d", False)

        output.console_log("Waiting for Train Ticket System to start up")

        # wait for system to start up
        output.console_log("Sleep 10 minutes...")
        if self.testing:
            time.sleep(1 * 60)
        else:
            time.sleep(10 * 60)
        exit()
        # counting number of lines, so 1 line = 0 containers, 68 lines equals 67 containers 
        _, number_of_containers_buf, _ = con.exec_command(f"echo {password} | sudo -S docker ps | wc -l")
        number_of_containers = int(number_of_containers_buf.read().strip())
        output.console_log(f"Found {number_of_containers} running after sleeping")

        # TODO 45 containers running, Madalina's 68 why?
        if number_of_containers < 44:
            output.console_log("Sleep for 3 more minutes...")
            time.sleep(3 * 60)

            _, number_of_containers_buf, _ = con.exec_command(f"echo {password} | sudo -S docker ps | wc -l")
            number_of_containers = int(number_of_containers_buf.read().strip())
            output.console_log(f"Found {number_of_containers} running after sleeping")

            if number_of_containers < 44:
                output.console_log(f"Not enough containers running: {number_of_containers}/68")
                # cleanup
                self.interrupt_run(context, "Not all expected containers are running")

        output.console_log("Benchmark system initialized")

    def interrupt_run(self, context, msg):
        self.stop_measurement(context)
        self.stop_run(context)
        output.console_log_FAIL(msg)
        raise Exception(msg)

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        output.console_log("Config.start_measurement() called!")
        ################################################## START_MEASUREMENT
        # start Wattsup profiler on LOGGING_SERVER
        timeout = 10
        workload = context.run_variation['workload']

        _, _, passwordGL5 = get_credentials(self.LOGGING_GL)
        watssup_command = f"echo {passwordGL5} | sudo -S ~/scripts/start_wattsuppro.sh {self.SUT} {timeout}"
        remote_command(self.LOGGING_GL, watssup_command, "Wattsup meter start", background=True)

        # start monitor.sh on SUT
        monitor_command = f"cd ~/scripts/experiment-runner && nohup ./monitor-er.sh {self.SUT} {workload}"
        remote_command(self.SUT, monitor_command, "Monitor CPU & MEM started", background=True)        

    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here, or block here until the target finishes."""
        output.console_log("Config.interact() called!")
        ################################################## INTERACT
        stress_time = 10
        workload = context.run_variation['workload']
        #workload_value = Workload[context.run_variation['workload']].value
        output.console_log(f"Load testing with K6 - {context.run_variation['workload']} workload: {workload}")

        os.system(f"for i in $(ls ~/THESIS/tts-thesis-master/k6-test); "
                  f"do k6 run --http-debug - <~/THESIS/tts-thesis-master/k6-test/$i/script.js --vus {workload} --duration 20s ; done")

        output.console_log('Finished load testing')

    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        output.console_log("Config.stop_measurement called!")
        ################################################## STOP_MEASUREMENT
        # stop wattsuppro.sh
        _, _, passwordLogging = get_credentials(self.LOGGING_GL)
        stop_wa_command = f"echo {passwordLogging} | sudo -S ~/scripts/stop_wattsuppro.sh {self.SUT}"
        remote_command(self.LOGGING_GL, stop_wa_command, "wattsuppro stopped")
        # stop monitor-er.sh
        stop_monitor_command = "pgrep -f \"monitor-er.sh\" | xargs kill"
        remote_command(self.SUT, stop_monitor_command, "monitor stopped")


    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run.
        Activities after stopping the run should also be performed here."""
        output.console_log("Config.stop_run() called!")
        ################################################## STOP_RUN
        host, username, password = get_credentials(self.SUT)

        output.console_log(f"Stopping TTS")

        command = (f"cd ~/tts-thesis; echo {password} | sudo -S docker-compose down")
        remote_command(self.SUT, command, "STOP TTS", False)


    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, SupportsStr]]:
        """Parse and process any measurement data here.
        You can also store the raw measurement data under `context.run_dir`
        Returns a dictionary with keys `self.run_table_model.data_columns` and their values populated"""
        output.console_log("Config.populate_run_data() called!")
        ################################################## POPULATE_RUN
        context.run_dir
        
        return None

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""
        output.console_log("Config.after_experiment() called!")
        ################################################## AFTER_EXPERIMENT
        
        # retrieve output from LOGGING_server
        execute_command(f"cd {self.ROOT_DIR} && mkdir -p results/energy", True)
        hostLOG, userLOG, passwordLog = get_credentials(self.LOGGING_GL)
        retrieve_data_energy_command = f'sshpass -p "{passwordLog}" scp -r {userLOG}@{hostLOG}:/home/ander/results/* {self.ROOT_DIR}/results/energy/'
        execute_command(retrieve_data_energy_command, False)
        output.console_log(f'Energy data successfully retrieved')

        # retrieve output from SUT
        execute_command(f"cd {self.ROOT_DIR} && mkdir -p results/cpu_mem", True)
        hostSUT, userSUT, passwordSUT = get_credentials(self.SUT)
        retrieve_data_cpu_command = f'sshpass -p "{passwordSUT}" scp -r {userSUT}@{hostSUT}:/home/ander/results/* {self.ROOT_DIR}/results/cpu_mem/' 
        execute_command(retrieve_data_cpu_command, False)
        output.console_log(f'CPU & mem data successfully retrieved')

        # TESTING MODE !!! 
        if self.testing:
            remove_output_folders = f'rm -r {self.results_output_path} & rm -r {self.ROOT_DIR}/__pycache__'
            execute_command(remove_output_folders , False)
            
        
    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
