import enum
import os
import paramiko
import subprocess
import time
import datetime

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.Output.OutputProcedure import OutputProcedure as output
from ConnectionHandler import ConnectionHandler

from typing import Dict, List, Any, Optional
from pathlib import Path
from os.path import dirname, realpath

# LOCAL SCOPE
def get_local_pass():
    return os.getenv(f"LOCAL_P")

def get_Rittal_credentials():
    username = os.getenv("RITTAL_U_3")
    password = os.getenv("RITTAL_P_3")
    if not password or not username:
        raise Exception('No environment variables set for credentials')
    return username, password  

# Open a terminal and execute a command in the local machine
def execute_local_command(command, wait, mssg=""):
    process = subprocess.Popen(command, shell=True, executable='/bin/bash')
    output.console_log(f'Running {command}')
    if wait: 
        process.communicate()        
    return process

def write_to_log(mssg, sut, add_timestamp=False):
    with open(f'logfile{sut}.log', 'a') as file:
        if add_timestamp:
            timestamp = datetime.datetime.now()
            file.write(f"{mssg} at {timestamp}\n")
        else:
            file.write(f"{mssg}\n")

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))

    # ================================ USER SPECIFIC CONFIG ================================
    """The name of the experiment."""
    name:                       str             = "def-stress-ng-GL6"

    """The path in which Experiment Runner will create a folder with the name `self.name`, in order to store the
    results from this experiment. (Path does not need to exist - it will be created if necessary.)
    Output path defaults to the config file's path, inside the folder 'experiments'"""
    results_output_path:        Path            = ROOT_DIR / 'experiments'

    """Experiment operation type. Unless you manually want to initiate each run, use `OperationType.AUTO`."""
    operation_type:             OperationType   = OperationType.AUTO

    """The time Experiment Runner will wait after a run completes.
    This can be essential to accommodate for cooldown periods on some systems."""
    time_between_runs_in_ms:    int             = 1000 * 60 * 5
    # USER VARIABLES:
    # Path for local scripts
    scripts_path:               Path            = "~/THESIS/master-project-def/scripts"
    # System Under Test (SUT)
    SUT:                        str             = "GL6"
    # Logging server
    LOGGING_GL:                 str             = "GL3"
    # Connections with GLs
    con_SUT:                    ConnectionHandler = ConnectionHandler(SUT)
    con_LOG:                    ConnectionHandler = ConnectionHandler(LOGGING_GL)
    # Discard run
    discard_run:                bool            = False
    # GL specific
    VUs_dict:                   Dict            = {'50': '15', '75': '25', '100': '50' }
    wait_time:                  int             = 3 * 60
    # Testing mode
    testing:                    bool            = False
    if testing:
        time_between_runs_in_ms = 10000 # 10 seconds sleep between runs when testing

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
        #factor1 = FactorModel("runs", ['r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10'])
        factor1 = FactorModel("runs", ['r1', 'r2', 'r3', 'r4', 'r5'])
        #factor2 = FactorModel("workload", ['50', '75', '100'])
        factor2 = FactorModel("workload", ['0'])
        self.run_table_model = RunTableModel(
            factors=[factor1, factor2],
            data_columns=['avg_cpu', 'avg_mem']
        )
        return self.run_table_model

    def interrupt_run(self, context, msg):
        self.stop_measurement(context)
        self.stop_run(context)
        output.console_log_FAIL(msg)
        raise Exception(msg)

    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here
        Invoked only once during the lifetime of the program."""
        output.console_log("Config.before_experiment() called!")
        ################################################## BEFORE_EXPERIMENT
        os.environ.update() # For the environment variables to be loaded
        execute_local_command(f"cd {self.ROOT_DIR} && mkdir -p results/energy", True)
        write_to_log(f"[{self.name}] New experiment started from scratch", self.SUT, True)

    def before_run(self) -> None:
        """Perform any activity required before starting a run.
        No context is available here as the run is not yet active."""
        output.console_log("Config.before_run() called!")
        ################################################## BEFORE_RUN
        self.discard_run = False
        self.con_SUT.execute_remote_command("tmux kill-server", "Kill tmux sessions in case there were any left (SUT).")
        self.con_LOG.execute_remote_command("tmux kill-server", "Kill tmux sessions in case there were any left (LOG).")
        execute_local_command("tmux kill-server", "Kill tmux sessions (local).")

    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here.
        Activities after starting the run should also be performed here."""
        output.console_log("Config.start_run() called!")
        ################################################## START_RUN
        # SSH port forwarding for Rittal system
        hostLog, usernameLog, passwordLog = self.con_LOG.get_credentials()
        ssh_port_forwarding_command = f"tmux new -s portforwarding -d \"sshpass -p {passwordLog} ssh -L 8080:192.168.0.200:80 {usernameLog}@{hostLog}\""
        execute_local_command(ssh_port_forwarding_command, False)

        time.sleep(3)


    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        output.console_log("Config.start_measurement() called!")
        ################################################## START_MEASUREMENT
        # start Rittal system on LOGGING_SERVER for 15' = 900s (average run is 16')
        timeout = 880
        userRittal, passwordRittal = get_Rittal_credentials()
        rittal_command = f"{self.scripts_path}/experiment-runner/logging/start_Rittal.sh {self.SUT} {timeout} {self.ROOT_DIR}/results/energy {userRittal} {passwordRittal}"
        execute_local_command(rittal_command, False)
        time.sleep(12)
        workload = context.run_variation['workload']
        # check whether Rittal worked:
        file_path = os.path.join(f"{self.ROOT_DIR}/results/energy/", f"energy{self.SUT}.log")
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        if not os.path.exists(file_path):
            error_msg = "Rittal could not start successfully. Stopping the run."
            # log if not working
            write_to_log(f"[{context.run_variation['runs']}] [{context.run_variation['workload']}] RITTAL FAILED", self.SUT, True)
            self.discard_run = True
            self.interrupt_run(context, error_msg)
        else:
            # log if working
            write_to_log(f"[{context.run_variation['runs']}-{timestamp}] [{context.run_variation['workload']}] OK", self.SUT, False)

        # start monitor.sh on SUT
        try:
            VUs = self.VUs_dict[workload]
            monitor_start_command = f"tmux new -s monitor -d 'cd /home/ander/scripts && ./monitor-er.sh {self.SUT} {workload} {VUs}'"
        except:
            monitor_start_command = f"tmux new -s monitor -d 'cd /home/ander/scripts && ./monitor-er.sh {self.SUT} {workload}'"
        self.con_SUT.execute_remote_command(monitor_start_command, "Monitor CPU & MEM started")        

    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here, or block here until the target finishes."""
        output.console_log("Config.interact() called!")
        ################################################## INTERACT
        timestamp_ini = time.time()
        stress_time = 898
        workload = context.run_variation['workload']
        stress_command = f"cd ~/scripts && ./stress-er.sh {workload} {stress_time}"
        self.con_SUT.execute_remote_command(stress_command, "stressing started")
        output.console_log('Finished stress testing')
        if time.time() - timestamp_ini < 120:
            print(time.time() - timestamp_ini)
            self.discard_run = True

            write_to_log(f"[{context.run_variation['runs']}] [{workload}] FAILED during K6-test", self.SUT, True)

    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        output.console_log("Config.stop_measurement called!")
        ################################################## STOP_MEASUREMENT
        # stop Rittal if still running, process the .log and generate csv in results if the run is valid
        if self.discard_run:
            self.con_SUT.execute_remote_command("pgrep -f \"start_Rittal.sh\" | xargs kill ; tmux kill-window", "Kill Rittal script and tmux session.")
        else:
            try:
                VUs = self.VUs_dict[context.run_variation['workload']]
                execute_local_command(f"{self.scripts_path}/experiment-runner/logging/stop_Rittal.sh {self.SUT} {self.ROOT_DIR}/results/energy {context.run_variation['workload']} {VUs}", True)
            except:
                output.console_log("VUs not being treated as a factor")
                execute_local_command(f"{self.scripts_path}/experiment-runner/logging/stop_Rittal.sh {self.SUT} {self.ROOT_DIR}/results/energy {context.run_variation['workload']}", True)
        # stop monitor-er.sh
        self.con_SUT.execute_remote_command("tmux kill-session -t monitor", "Kill tmux monitor session")
        if self.discard_run: 
            # remove mem and cpu files from incompleted run
            self.con_SUT.execute_remote_command("~/scripts/remove_2_last_files.sh ~/results/", "Delete 2 extra files")

    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run.
        Activities after stopping the run should also be performed here."""
        output.console_log("Config.stop_run() called!")
        ################################################## STOP_RUN
        stop1 = "pgrep -f \"stress-er.sh\" | xargs kill"
        stop2 = "pgrep -f \"monitor-er.sh\" | xargs kill"
        self.con_SUT.execute_remote_command(stop1, "Kill stress if still running.")
        self.con_LOG.execute_remote_command(stop2, "Kill monitor if still running.")

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

        # retrieve output from SUT (generated with monitor-er.sh)
        execute_local_command(f"cd {self.ROOT_DIR} && mkdir -p results/cpu_mem", True)
        hostSUT, userSUT, passwordSUT = self.con_SUT.get_credentials()
        retrieve_data_cpu_command = f'sshpass -p "{passwordSUT}" scp -r {userSUT}@{hostSUT}:/home/ander/results/* {self.ROOT_DIR}/results/cpu_mem/'
        execute_local_command(retrieve_data_cpu_command, True)
        time.sleep(60)
        if self.testing:
            command = (f"echo {passwordSUT} | sudo -S rm -r /home/ander/results/*")
            self.con_SUT.execute_remote_command(command, f"Remove files from {self.SUT}")

        output.console_log(f'CPU & mem data successfully retrieved')

        # move to 0_RESULTS
        timestamp = datetime.datetime.now().strftime("%m%d-%H%M")
        execute_local_command(f"{self.scripts_path}/analysis/analyse_files.sh {self.ROOT_DIR}/results", True)
        execute_local_command(f"cd ~/THESIS/0_RESULTS/STRESS-NG && mkdir -p {self.SUT}-{timestamp} && cp -r {self.ROOT_DIR}/results/* ~/THESIS/0_RESULTS/STRESS-NG/{self.SUT}-{timestamp}", True)        

        write_to_log(f"[{self.name}] Experiment completed", self.SUT, True)

        output.console_log(f'Experiment completed and data pre-analysed, find the results on ~/THESIS/0_RESULTS/{self.SUT}-{timestamp}')

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
